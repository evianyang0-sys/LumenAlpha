import { createServer } from "node:http";
import { createReadStream, existsSync, readFileSync, statSync, watch } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { extname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { createAuthStore, isUniqueConstraintError, validatePassword, validateUsername } from "./auth_store.mjs";

const root = resolve(fileURLToPath(new URL(".", import.meta.url)));
const repoRoot = resolve(root, "../..");
const aiCacheRoot = resolve(repoRoot, "data/sector_rotation/ai_analysis");

function loadLocalEnv() {
  const envFiles = [
    resolve(repoRoot, ".env.local"),
    resolve(repoRoot, ".env"),
    resolve(root, ".env.local"),
    resolve(root, ".env"),
  ];
  for (const file of envFiles) {
    if (!existsSync(file)) continue;
    const lines = readFileSync(file, "utf-8").split(/\r?\n/);
    for (const raw of lines) {
      const line = raw.trim();
      if (!line || line.startsWith("#") || !line.includes("=")) continue;
      const index = line.indexOf("=");
      const key = line.slice(0, index).trim();
      let value = line.slice(index + 1).trim();
      if (!key || process.env[key] !== undefined) continue;
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      process.env[key] = value;
    }
  }
}

loadLocalEnv();

const portArgIndex = process.argv.indexOf("--port");
const port = Number(process.env.PORT || (portArgIndex >= 0 ? process.argv[portArgIndex + 1] : 8765));
const host = process.env.HOST || "127.0.0.1";
const clients = new Set();
const deepseekModel = process.env.DEEPSEEK_MODEL || "deepseek-v4-pro";
const configuredUserDbPath = process.env.USER_DB_PATH || "data/lumenalpha_users.sqlite";
const userDbPath = configuredUserDbPath.startsWith("/") ? configuredUserDbPath : resolve(repoRoot, configuredUserDbPath);
const authStore = await createAuthStore(userDbPath);
const sessionCookieName = "lumenalpha_session";
const authRateLimits = new Map();
const configuredPython = resolve(repoRoot, ".venv/bin/python");
const pythonBin = process.env.PYTHON_BIN || (existsSync(configuredPython) ? configuredPython : "python3");
const stockCalculationScript = resolve(repoRoot, "scripts/on_demand_stock.py");
const requestedLiveStockCacheSeconds = Number(process.env.LIVE_STOCK_CACHE_SECONDS || 1800);
const liveStockCacheSeconds = Number.isFinite(requestedLiveStockCacheSeconds)
  ? Math.round(Math.max(0, Math.min(86400, requestedLiveStockCacheSeconds)))
  : 1800;
const requestedMaxStockCalculations = Number(process.env.MAX_LIVE_STOCK_PROCESSES || 2);
const maxStockCalculations = Number.isFinite(requestedMaxStockCalculations)
  ? Math.round(Math.max(1, Math.min(4, requestedMaxStockCalculations)))
  : 2;
const stockCalculationInflight = new Map();

const mime = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
};

const liveReloadSnippet = `
<script>
(() => {
  const source = new EventSource("/__events");
  source.onmessage = event => {
    if (event.data === "reload") window.location.reload();
  };
})();
</script>`;

function safePath(urlPath) {
  const clean = decodeURIComponent(urlPath.split("?")[0]).replace(/^\/+/, "") || "index.html";
  const candidate = resolve(join(root, clean));
  return candidate === root || candidate.startsWith(`${root}${sep}`) ? candidate : join(root, "index.html");
}

async function serveHtml(path, res) {
  let html = await readFile(path, "utf-8");
  html = html.replace("</body>", `${liveReloadSnippet}\n</body>`);
  res.writeHead(200, { "Content-Type": mime[".html"], "Cache-Control": "no-store" });
  res.end(html);
}

function sendJson(res, status, payload, headers = {}) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers });
  res.end(JSON.stringify(payload));
}

function readJsonBody(req, maxBytes = 1_200_000) {
  return new Promise((resolveBody, rejectBody) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (Buffer.byteLength(body) > maxBytes) {
        rejectBody(new Error("request_body_too_large"));
        req.destroy();
      }
    });
    req.on("end", () => {
      try {
        resolveBody(body ? JSON.parse(body) : {});
      } catch (error) {
        rejectBody(error);
      }
    });
    req.on("error", rejectBody);
  });
}

function safeId(value) {
  return String(value || "unknown").replace(/[^\w.-]+/g, "_").slice(0, 80) || "unknown";
}

function tradeDateFromContext(context) {
  const raw = context?.generatedAt || context?.date || new Date().toISOString();
  const match = String(raw).match(/\d{4}-\d{2}-\d{2}/);
  return match ? match[0].replaceAll("-", "") : new Date().toISOString().slice(0, 10).replaceAll("-", "");
}

function stableHash(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex").slice(0, 16);
}

function parseCookies(req) {
  const cookies = {};
  for (const part of String(req.headers.cookie || "").split(";")) {
    const index = part.indexOf("=");
    if (index < 0) continue;
    try {
      cookies[part.slice(0, index).trim()] = decodeURIComponent(part.slice(index + 1).trim());
    } catch (_error) {
      // Ignore malformed cookies instead of failing the whole request.
    }
  }
  return cookies;
}

function sessionToken(req) {
  return parseCookies(req)[sessionCookieName] || "";
}

function requestIsSecure(req) {
  return String(req.headers["x-forwarded-proto"] || "").split(",")[0].trim() === "https";
}

function authTransportAllowed(req) {
  if (requestIsSecure(req)) return true;
  const host = String(req.headers.host || "").split(":")[0];
  return host === "127.0.0.1" || host === "localhost" || host === "::1";
}

function sessionCookie(req, token, maxAge = 30 * 24 * 60 * 60) {
  const secure = requestIsSecure(req) || process.env.COOKIE_SECURE === "1";
  return `${sessionCookieName}=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${secure ? "; Secure" : ""}`;
}

function sameOrigin(req) {
  const origin = String(req.headers.origin || "");
  if (!origin) return true;
  try {
    return new URL(origin).host === String(req.headers.host || "");
  } catch (_error) {
    return false;
  }
}

function clientIp(req) {
  return String(req.headers["x-real-ip"] || req.headers["x-forwarded-for"] || req.socket.remoteAddress || "unknown").split(",")[0].trim();
}

function consumeRateLimit(req, scope, limit, windowMs) {
  const key = `${scope}:${clientIp(req)}`;
  const now = Date.now();
  if (authRateLimits.size > 5000) {
    for (const [entryKey, entry] of authRateLimits) {
      if (entry.resetAt <= now) authRateLimits.delete(entryKey);
    }
  }
  const current = authRateLimits.get(key);
  if (!current || current.resetAt <= now) {
    authRateLimits.set(key, { count: 1, resetAt: now + windowMs });
    return true;
  }
  if (current.count >= limit) return false;
  current.count += 1;
  return true;
}

function normalizedStockCode(value) {
  const digits = String(value || "").replace(/\D/g, "");
  if (!digits) return "";
  const code = digits.slice(-6).padStart(6, "0");
  return /^\d{6}$/.test(code) ? code : "";
}

function authUser(req) {
  return authStore.sessionUser(sessionToken(req));
}

function watchlistPayload(userId) {
  const items = authStore.watchlistEntries(userId);
  return { ok: true, codes: items.map((item) => item.code), items };
}

async function handleAccountRequest(req, res) {
  const url = new URL(req.url || "/", "http://localhost");
  const path = url.pathname;
  if (!path.startsWith("/api/auth/") && !path.startsWith("/api/watchlist")) return false;

  if (req.method !== "GET" && !sameOrigin(req)) {
    sendJson(res, 403, { ok: false, error: "请求来源无效" });
    return true;
  }

  if (path === "/api/auth/me" && req.method === "GET") {
    sendJson(res, 200, {
      ok: true,
      user: authUser(req),
      authAvailable: authTransportAllowed(req),
      httpsRequired: !authTransportAllowed(req),
    });
    return true;
  }

  if ((path === "/api/auth/register" || path === "/api/auth/login") && !authTransportAllowed(req)) {
    sendJson(res, 426, { ok: false, error: "登录功能需要 HTTPS。请先完成域名解析和证书配置。" });
    return true;
  }

  if (path === "/api/auth/register" && req.method === "POST") {
    if (!consumeRateLimit(req, "register", 5, 60 * 60 * 1000)) {
      sendJson(res, 429, { ok: false, error: "注册尝试过于频繁，请稍后再试" });
      return true;
    }
    const payload = await readJsonBody(req).catch(() => null);
    if (!payload) {
      sendJson(res, 400, { ok: false, error: "请求格式无效" });
      return true;
    }
    const username = validateUsername(payload.username);
    const password = validatePassword(payload.password);
    if (!username.ok || !password.ok) {
      sendJson(res, 400, { ok: false, error: username.error || password.error });
      return true;
    }
    try {
      const account = await authStore.register(username.value, password.value);
      sendJson(res, 201, { ok: true, user: account.user }, { "Set-Cookie": sessionCookie(req, account.token) });
    } catch (error) {
      const duplicate = isUniqueConstraintError(error);
      sendJson(res, duplicate ? 409 : 500, { ok: false, error: duplicate ? "用户名已被使用" : "注册失败，请稍后重试" });
    }
    return true;
  }

  if (path === "/api/auth/login" && req.method === "POST") {
    if (!consumeRateLimit(req, "login", 10, 15 * 60 * 1000)) {
      sendJson(res, 429, { ok: false, error: "登录尝试过于频繁，请15分钟后再试" });
      return true;
    }
    const payload = await readJsonBody(req).catch(() => null);
    const username = validateUsername(payload?.username);
    const password = validatePassword(payload?.password);
    if (!username.ok || !password.ok) {
      sendJson(res, 401, { ok: false, error: "用户名或密码错误" });
      return true;
    }
    const account = await authStore.login(username.value, password.value);
    if (!account) {
      sendJson(res, 401, { ok: false, error: "用户名或密码错误" });
      return true;
    }
    sendJson(res, 200, { ok: true, user: account.user }, { "Set-Cookie": sessionCookie(req, account.token) });
    return true;
  }

  if (path === "/api/auth/logout" && req.method === "POST") {
    authStore.logout(sessionToken(req));
    sendJson(res, 200, { ok: true }, { "Set-Cookie": sessionCookie(req, "", 0) });
    return true;
  }

  const user = authUser(req);
  if (!user) {
    sendJson(res, 401, { ok: false, error: "请先登录" });
    return true;
  }

  if (path === "/api/watchlist" && req.method === "GET") {
    sendJson(res, 200, watchlistPayload(user.id));
    return true;
  }

  if (path === "/api/watchlist" && req.method === "POST") {
    const payload = await readJsonBody(req).catch(() => null);
    const code = normalizedStockCode(payload?.code);
    if (!code) {
      sendJson(res, 400, { ok: false, error: "股票代码无效" });
      return true;
    }
    authStore.addWatch(user.id, code);
    sendJson(res, 200, watchlistPayload(user.id));
    return true;
  }

  if (path.startsWith("/api/watchlist/") && req.method === "DELETE") {
    const code = normalizedStockCode(decodeURIComponent(path.slice("/api/watchlist/".length)));
    if (!code) {
      sendJson(res, 400, { ok: false, error: "股票代码无效" });
      return true;
    }
    authStore.removeWatch(user.id, code);
    sendJson(res, 200, watchlistPayload(user.id));
    return true;
  }

  sendJson(res, 405, { ok: false, error: "不支持的操作" });
  return true;
}

function analysisSystemPrompt() {
  return [
    "你是A股科技板块轮动研究助手，只负责解释用户已提供的数据。",
    "不要编造实时行情，不要把自己当成交易指令源，不要承诺收益。",
    "必须区分：本地量化信号、LumenAlpha技术信号、人气信号、板块趋势、数据质量限制。",
    "输出必须是JSON对象，字段为 summary, bullish_points, risk_points, signal_conflicts, watch_levels, next_day_plan, confidence, data_quality_notes。",
    "不要把完整JSON对象作为字符串塞进summary；summary只能是一段中文摘要。",
    'JSON示例: {"summary":"一句中文摘要","bullish_points":["依据1"],"risk_points":["风险1"],"signal_conflicts":[],"watch_levels":[],"next_day_plan":["计划1"],"confidence":"medium","data_quality_notes":[]}',
    "summary不超过100个汉字；每个数组字段最多3条，每条不超过70个汉字，语言简洁，具体到股票或板块。",
  ].join("\n");
}

function analysisUserPrompt(type, context) {
  return [
    `分析类型: ${type}`,
    "请基于下面JSON数据做末端解释性分析。",
    "如果数据不足，明确说不足；如果信号冲突，优先指出冲突。",
    JSON.stringify(context).slice(0, 60000),
  ].join("\n\n");
}

function normalizeAnalysis(raw, fallbackSummary = "AI分析已返回。") {
  const parsed = typeof raw === "string" ? tryParseJson(raw) : raw;
  const recovered = typeof raw === "string" ? recoverJsonLikeAnalysis(raw) : null;
  let source = parsed && typeof parsed === "object"
    ? parsed
    : recovered || { summary: String(raw || fallbackSummary) };
  const nested = typeof source.summary === "string"
    ? tryParseJson(source.summary) || recoverJsonLikeAnalysis(source.summary)
    : null;
  if (nested && typeof nested === "object" && (nested.summary || nested.bullish_points || nested.risk_points)) {
    source = { ...source, ...nested };
  }
  const arrayOfText = (value) => Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean).slice(0, 5) : [];
  return {
    summary: String(source.summary || fallbackSummary),
    bullish_points: arrayOfText(source.bullish_points),
    risk_points: arrayOfText(source.risk_points),
    signal_conflicts: arrayOfText(source.signal_conflicts),
    watch_levels: arrayOfText(source.watch_levels),
    next_day_plan: arrayOfText(source.next_day_plan),
    confidence: String(source.confidence || "medium"),
    data_quality_notes: arrayOfText(source.data_quality_notes),
  };
}

function recoverJsonLikeAnalysis(text) {
  const source = String(text || "").trim();
  if (!source.startsWith("{") && !source.includes('"summary"')) return null;
  const readString = (key) => {
    const match = source.match(new RegExp(`"${key}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)`));
    if (!match) return "";
    try {
      return JSON.parse(`"${match[1].replace(/"$/, "")}"`);
    } catch (_error) {
      return match[1].replaceAll('\\"', '"').replaceAll("\\n", "\n");
    }
  };
  const readArray = (key) => {
    const start = source.search(new RegExp(`"${key}"\\s*:\\s*\\[`));
    if (start < 0) return [];
    const tail = source.slice(start).replace(new RegExp(`^.*?"${key}"\\s*:\\s*\\[`), "");
    const end = tail.indexOf("]");
    const body = end >= 0 ? tail.slice(0, end) : tail;
    const values = [];
    for (const match of body.matchAll(/"((?:\\.|[^"\\])*)"/g)) {
      try {
        values.push(JSON.parse(`"${match[1]}"`));
      } catch (_error) {
        values.push(match[1]);
      }
      if (values.length >= 5) break;
    }
    return values;
  };
  const summary = readString("summary");
  if (!summary) return null;
  return {
    summary,
    bullish_points: readArray("bullish_points"),
    risk_points: readArray("risk_points"),
    signal_conflicts: readArray("signal_conflicts"),
    watch_levels: readArray("watch_levels"),
    next_day_plan: readArray("next_day_plan"),
    confidence: readString("confidence") || "medium",
    data_quality_notes: readArray("data_quality_notes"),
  };
}

function tryParseJson(text) {
  try {
    return JSON.parse(text);
  } catch (_error) {
    const match = String(text || "").match(/\{[\s\S]*\}/);
    if (!match) return null;
    try {
      return JSON.parse(match[0]);
    } catch (_innerError) {
      return null;
    }
  }
}

function runStockCalculation(query) {
  return new Promise((resolveCalculation, rejectCalculation) => {
    const child = spawn(
      pythonBin,
      [stockCalculationScript, "--query", query, "--max-age", String(liveStockCacheSeconds)],
      { cwd: repoRoot, env: { ...process.env, PYTHONUNBUFFERED: "1" }, stdio: ["ignore", "pipe", "pipe"] },
    );
    const outputLimit = 2_000_000;
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    let outputExceeded = false;

    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
      if (Buffer.byteLength(stdout) > outputLimit) {
        outputExceeded = true;
        child.kill("SIGKILL");
      }
    });
    child.stderr.on("data", (chunk) => {
      stderr = `${stderr}${chunk}`.slice(-8000);
    });

    const timeout = setTimeout(() => {
      timedOut = true;
      child.kill("SIGKILL");
    }, 75_000);

    child.once("error", (error) => {
      clearTimeout(timeout);
      rejectCalculation(error);
    });
    child.once("close", () => {
      clearTimeout(timeout);
      if (timedOut) {
        rejectCalculation(new Error("现场计算超时，请稍后重试"));
        return;
      }
      if (outputExceeded) {
        rejectCalculation(new Error("现场计算输出异常"));
        return;
      }
      const payload = tryParseJson(stdout);
      if (payload && typeof payload === "object") {
        resolveCalculation(payload);
        return;
      }
      rejectCalculation(new Error(stderr.trim() || "现场计算没有返回有效结果"));
    });
  });
}

async function calculateStock(query) {
  const key = String(query).toLowerCase();
  let calculation = stockCalculationInflight.get(key);
  if (!calculation) {
    if (stockCalculationInflight.size >= maxStockCalculations) {
      const error = new Error("现场计算任务较多，请稍后重试");
      error.code = "STOCK_CALCULATION_BUSY";
      throw error;
    }
    calculation = runStockCalculation(query);
    stockCalculationInflight.set(key, calculation);
  }
  try {
    return await calculation;
  } finally {
    if (stockCalculationInflight.get(key) === calculation) stockCalculationInflight.delete(key);
  }
}

async function handleStockAnalyze(req, res) {
  if (!sameOrigin(req)) {
    sendJson(res, 403, { ok: false, error: "请求来源无效" });
    return;
  }
  if (!consumeRateLimit(req, "stock-calculate", 12, 10 * 60 * 1000)) {
    sendJson(res, 429, { ok: false, error: "现场计算过于频繁，请十分钟后再试" });
    return;
  }

  const body = await readJsonBody(req, 4096).catch(() => null);
  const query = String(body?.query || "").trim();
  if (!query || query.length > 20 || (query.length < 2 && !/^\d{6}$/.test(query))) {
    sendJson(res, 400, { ok: false, error: "请输入完整股票名称或6位代码" });
    return;
  }

  try {
    const payload = await calculateStock(query);
    if (payload.ok) {
      sendJson(res, 200, payload);
      return;
    }
    const status = payload.errorCode === "AMBIGUOUS" ? 409 : payload.errorCode === "NOT_FOUND" ? 404 : 502;
    sendJson(res, status, payload);
  } catch (error) {
    sendJson(res, error.code === "STOCK_CALCULATION_BUSY" ? 503 : 502, { ok: false, error: error.message || "现场计算失败，请稍后重试" });
  }
}

async function handleStockAnalyzeBatch(req, res) {
  if (!sameOrigin(req)) {
    sendJson(res, 403, { ok: false, error: "请求来源无效" });
    return;
  }
  if (!consumeRateLimit(req, "stock-calculate-batch", 4, 10 * 60 * 1000)) {
    sendJson(res, 429, { ok: false, error: "自选信号同步过于频繁，请十分钟后再试" });
    return;
  }

  const body = await readJsonBody(req, 8192).catch(() => null);
  const requested = Array.isArray(body?.codes) ? body.codes : [];
  if (!requested.length || requested.length > 12) {
    sendJson(res, 400, { ok: false, error: "每次可同步1-12只股票" });
    return;
  }
  const normalized = requested.map(normalizedStockCode);
  if (normalized.some((code) => !code)) {
    sendJson(res, 400, { ok: false, error: "股票代码无效" });
    return;
  }

  const codes = [...new Set(normalized)];
  const items = [];
  for (const code of codes) {
    try {
      const payload = await calculateStock(code);
      items.push(payload.ok ? payload : { ok: false, code, error: payload.error || "计算失败" });
    } catch (error) {
      items.push({ ok: false, code, error: error.message || "计算失败" });
    }
  }
  sendJson(res, 200, { ok: true, items });
}

function mockAnalysis(type, context) {
  const subject = context?.stock?.name || context?.board?.board_path || "当前日报";
  return normalizeAnalysis({
    summary: `模拟分析：${subject} 的本地信号已汇总，配置 DEEPSEEK_API_KEY 后会返回 DeepSeek 实时解释。`,
    bullish_points: ["本地综合分、人气或板块趋势中存在可观察强项。"],
    risk_points: ["当前为模拟结果，不应用于真实判断。"],
    signal_conflicts: ["需要真实模型读取上下文后判断 LumenAlpha 与人气信号是否冲突。"],
    watch_levels: ["关注最近5日显著信号和30日K线关键位置。"],
    next_day_plan: ["配置 API key 后重新点击 AI分析。"],
    confidence: "mock",
    data_quality_notes: [`type=${type}; context keys=${Object.keys(context || {}).join(",")}`],
  });
}

async function handleAiAnalyze(req, res) {
  let payload;
  try {
    payload = await readJsonBody(req);
  } catch (error) {
    sendJson(res, 400, { ok: false, error: `请求JSON无效: ${error.message}` });
    return;
  }
  const type = safeId(payload.type || "daily");
  const id = safeId(payload.id || "latest");
  const context = payload.context || {};
  const cacheKey = stableHash({ type, id, model: deepseekModel, prompt: "sector-ai-v2", context });
  const day = tradeDateFromContext(context);
  const cacheDir = resolve(aiCacheRoot, day);
  const cachePath = resolve(cacheDir, `${type}_${id}_${cacheKey}.json`);

  if (existsSync(cachePath) && !payload.refresh) {
    try {
      const cached = JSON.parse(await readFile(cachePath, "utf-8"));
      cached.analysis = normalizeAnalysis(cached.analysis, "缓存AI分析已读取。");
      sendJson(res, 200, { ok: true, cached: true, ...cached });
      return;
    } catch (_error) {
      // fall through and regenerate
    }
  }

  if (!process.env.DEEPSEEK_API_KEY) {
    if (process.env.DEEPSEEK_MOCK === "1") {
      const analysis = mockAnalysis(type, context);
      sendJson(res, 200, { ok: true, cached: false, mock: true, model: deepseekModel, analysis });
      return;
    }
    sendJson(res, 503, {
      ok: false,
      error: "DEEPSEEK_API_KEY 未配置。请复制项目根目录 .env.example 为 .env.local，填入 DEEPSEEK_API_KEY 后重启 npm start。",
    });
    return;
  }

  try {
    const response = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${process.env.DEEPSEEK_API_KEY}`,
      },
      body: JSON.stringify({
        model: deepseekModel,
        messages: [
          { role: "system", content: analysisSystemPrompt() },
          { role: "user", content: analysisUserPrompt(type, context) },
        ],
        thinking: { type: "enabled" },
        reasoning_effort: "medium",
        response_format: { type: "json_object" },
        max_tokens: 4000,
        temperature: 0.2,
        stream: false,
      }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      sendJson(res, response.status, { ok: false, error: result.error?.message || `DeepSeek request failed: ${response.status}` });
      return;
    }
    const content = result.choices?.[0]?.message?.content || "";
    const analysis = normalizeAnalysis(content, "DeepSeek 已返回分析。");
    const cachedPayload = {
      model: deepseekModel,
      generatedAt: new Date().toISOString(),
      analysis,
      usage: result.usage || null,
    };
    await mkdir(cacheDir, { recursive: true });
    await writeFile(cachePath, JSON.stringify(cachedPayload, null, 2), "utf-8");
    sendJson(res, 200, { ok: true, cached: false, ...cachedPayload });
  } catch (error) {
    sendJson(res, 502, { ok: false, error: `DeepSeek 请求失败: ${error.message}` });
  }
}

const server = createServer(async (req, res) => {
  try {
    if (await handleAccountRequest(req, res)) return;
  } catch (error) {
    sendJson(res, 500, { ok: false, error: `账号服务异常: ${error.message}` });
    return;
  }

  if (req.url === "/__events") {
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-store",
      Connection: "keep-alive",
    });
    res.write("event: open\ndata: ready\n\n");
    clients.add(res);
    req.on("close", () => clients.delete(res));
    return;
  }

  if (req.url === "/api/ai/analyze" && req.method === "POST") {
    await handleAiAnalyze(req, res);
    return;
  }

  if (req.url === "/api/stocks/analyze" && req.method === "POST") {
    await handleStockAnalyze(req, res);
    return;
  }

  if (req.url === "/api/stocks/analyze-batch" && req.method === "POST") {
    await handleStockAnalyzeBatch(req, res);
    return;
  }

  const path = safePath(req.url || "/");
  const filePath = existsSync(path) && statSync(path).isDirectory() ? join(path, "index.html") : path;
  if (!existsSync(filePath)) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Not found");
    return;
  }

  const ext = extname(filePath);
  if (ext === ".html") {
    try {
      await serveHtml(filePath, res);
    } catch (error) {
      res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      res.end(String(error));
    }
    return;
  }

  res.writeHead(200, { "Content-Type": mime[ext] || "application/octet-stream", "Cache-Control": "no-store" });
  createReadStream(filePath).pipe(res);
});

watch(root, { recursive: false }, (_event, filename) => {
  if (!filename || filename.startsWith(".")) return;
  if (!/\.(html|css|js|json|csv|md)$/.test(filename)) return;
  for (const client of clients) {
    client.write("data: reload\n\n");
  }
});

server.listen(port, host, () => {
  console.log(`Sector rotation dashboard running at http://${host}:${port}/`);
  console.log("Press Ctrl+C to stop.");
});
