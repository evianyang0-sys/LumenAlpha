import { createServer } from "node:http";
import { createReadStream, existsSync, statSync, watch } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL(".", import.meta.url)));
const repoRoot = resolve(root, "../..");
const aiCacheRoot = resolve(repoRoot, "data/sector_rotation/ai_analysis");
const portArgIndex = process.argv.indexOf("--port");
const port = Number(process.env.PORT || (portArgIndex >= 0 ? process.argv[portArgIndex + 1] : 8765));
const host = process.env.HOST || "127.0.0.1";
const clients = new Set();
const deepseekModel = process.env.DEEPSEEK_MODEL || "deepseek-v4-pro";

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
  return candidate.startsWith(root) ? candidate : join(root, "index.html");
}

async function serveHtml(path, res) {
  let html = await readFile(path, "utf-8");
  html = html.replace("</body>", `${liveReloadSnippet}\n</body>`);
  res.writeHead(200, { "Content-Type": mime[".html"], "Cache-Control": "no-store" });
  res.end(html);
}

function sendJson(res, status, payload) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
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

function analysisSystemPrompt() {
  return [
    "你是A股科技板块轮动研究助手，只负责解释用户已提供的数据。",
    "不要编造实时行情，不要把自己当成交易指令源，不要承诺收益。",
    "必须区分：本地量化信号、LumenAlpha技术信号、人气信号、板块趋势、数据质量限制。",
    "输出必须是JSON对象，字段为 summary, bullish_points, risk_points, signal_conflicts, watch_levels, next_day_plan, confidence, data_quality_notes。",
    "每个数组字段最多5条，语言简洁，具体到股票或板块。",
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
  const source = parsed && typeof parsed === "object" ? parsed : { summary: String(raw || fallbackSummary) };
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

function mockAnalysis(type, context) {
  const subject = context?.stock?.name || context?.board?.board_path || "当前日报";
  return normalizeAnalysis({
    summary: `模拟分析：${subject} 的本地信号已汇总，配置 DEEPSEEK_API_KEY 后会返回 DeepSeek 实时解释。`,
    bullish_points: ["本地综合分、人气或板块趋势中存在可观察强项。"],
    risk_points: ["当前为模拟结果，不应用于真实判断。"],
    signal_conflicts: ["需要真实模型读取上下文后判断 qlib、LumenAlpha、人气是否冲突。"],
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
  const cacheKey = stableHash({ type, id, model: deepseekModel, prompt: "sector-ai-v1", context });
  const day = tradeDateFromContext(context);
  const cacheDir = resolve(aiCacheRoot, day);
  const cachePath = resolve(cacheDir, `${type}_${id}_${cacheKey}.json`);

  if (existsSync(cachePath) && !payload.refresh) {
    try {
      const cached = JSON.parse(await readFile(cachePath, "utf-8"));
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
      error: "DEEPSEEK_API_KEY 未配置。请用 DEEPSEEK_API_KEY=... npm start 重启本地服务。",
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
