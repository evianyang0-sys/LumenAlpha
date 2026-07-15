(function () {
  const data = window.SECTOR_DASHBOARD_DATA || {};
  const factorCatalog = window.FACTOR_CATALOG || { items: [], stats: {}, notes: [] };
  const state = {
    board: "all",
    leaderCode: null,
    mode: "overview",
    view: "dashboard",
    section: "overviewSection",
    activeDashboardNav: "今日概览",
    signalSearch: "",
    boardWindow: 30,
    selectedBoard: null,
    factorProject: "all",
    factorFamily: "all",
    factorSearch: "",
    factorLimit: 24,
    stockSignalsExpanded: false,
    globalSearch: "",
    dailyReportText: "",
    dailyReportStatus: "读取中",
    dailyReportLoading: false,
    aiAnalyses: {},
    watchlist: readGuestWatchlist(),
    authUser: null,
    authReady: false,
    authAvailable: false,
    authMode: "login",
    authSubmitting: false,
  };

  const tones = [
    { key: "PCB", color: "#ef4444", soft: "#fff0f0", text: "#dc2626", tone: "red" },
    { key: "光模块", color: "#0891b2", soft: "#e6faff", text: "#087ea4", tone: "cyan" },
    { key: "铜缆", color: "#0891b2", soft: "#e6faff", text: "#087ea4", tone: "cyan" },
    { key: "算力", color: "#d97706", soft: "#fff7e7", text: "#c2410c", tone: "amber" },
    { key: "液冷", color: "#0f9f7a", soft: "#e9fbf4", text: "#059669", tone: "green" },
    { key: "半导体", color: "#ef4444", soft: "#fff0f0", text: "#dc2626", tone: "red" },
    { key: "AI", color: "#db2777", soft: "#fff0f7", text: "#db2777", tone: "pink" },
    { key: "机器人", color: "#7c3aed", soft: "#f4efff", text: "#7c3aed", tone: "purple" },
    { key: "智能汽车", color: "#7c3aed", soft: "#f4efff", text: "#7c3aed", tone: "purple" },
  ];

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function brandText(value) {
    return String(value ?? "")
      .replace(/qlib/gi, "LumenAlpha")
      .replace(/LumenAlpha\s*(?:[、,/]|and|与|和)\s*LumenAlpha(?:-style)?/gi, "LumenAlpha");
  }

  function num(value, digits = 1) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "--";
    return n.toFixed(digits);
  }

  function pct(value, digits = 1) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "--";
    return `${(n * 100).toFixed(digits)}%`;
  }

  function signedPct(value, digits = 1) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "--";
    return `${n >= 0 ? "+" : ""}${(n * 100).toFixed(digits)}%`;
  }

  function shortText(value, limit = 180) {
    const text = String(value || "").trim();
    return text.length > limit ? `${text.slice(0, limit).trim()}...` : text;
  }

  function readGuestWatchlist() {
    try {
      const stored = localStorage.getItem("lumenalpha-watchlist-guest") || localStorage.getItem("lumenalpha-watchlist") || "[]";
      const value = JSON.parse(stored);
      return Array.isArray(value) ? value.map(normalizeCode).filter(Boolean) : [];
    } catch (_) {
      return [];
    }
  }

  function saveGuestWatchlist() {
    localStorage.setItem("lumenalpha-watchlist-guest", JSON.stringify(state.watchlist));
  }

  function clearGuestWatchlist() {
    localStorage.removeItem("lumenalpha-watchlist-guest");
    localStorage.removeItem("lumenalpha-watchlist");
  }

  function isWatched(code) {
    return state.watchlist.includes(normalizeCode(code));
  }

  async function toggleWatch(code) {
    const normalized = normalizeCode(code);
    if (!normalized) return;
    const previous = [...state.watchlist];
    const removing = isWatched(normalized);
    state.watchlist = removing
      ? state.watchlist.filter((item) => item !== normalized)
      : [...state.watchlist, normalized];
    renderWatchCount();
    if (!state.authUser) {
      saveGuestWatchlist();
      return;
    }
    try {
      const payload = await apiRequest(removing ? `/api/watchlist/${normalized}` : "/api/watchlist", {
        method: removing ? "DELETE" : "POST",
        body: removing ? undefined : { code: normalized },
      });
      state.watchlist = (payload.codes || []).map(normalizeCode).filter(Boolean);
      renderWatchCount();
    } catch (error) {
      state.watchlist = previous;
      renderWatchCount();
      if ($("watchlistHint")) $("watchlistHint").textContent = `同步失败：${error.message}`;
      if (state.view === "dashboard") renderDashboard();
      if (state.view === "watchlist") renderWatchlist();
      if (state.view === "stock") renderStockPage();
    }
  }

  async function apiRequest(path, options = {}) {
    const headers = {};
    const request = { method: options.method || "GET", headers, credentials: "same-origin" };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      request.body = JSON.stringify(options.body);
    }
    const response = await fetch(path, request);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  function normalizeCode(value) {
    const digits = String(value ?? "").replace(/\D/g, "");
    return digits ? digits.slice(-6).padStart(6, "0") : "";
  }

  function clamp(value, min = 0, max = 100) {
    const n = Number(value);
    if (!Number.isFinite(n)) return min;
    return Math.max(min, Math.min(max, n));
  }

  function boardLabel(path) {
    const parts = String(path || "").split(">").filter(Boolean);
    if (!parts.length) return "未分类";
    if (parts[0] === "科技") return parts[2] || parts[1] || parts[0];
    return parts[0];
  }

  function boardSubLabel(path) {
    const parts = String(path || "").split(">").filter(Boolean);
    if (parts[0] === "科技") return parts[1] || "科技";
    return "一级行业";
  }

  function isClassifiedBoard(board) {
    const path = String(board?.board_path || "").trim();
    return Boolean(path && boardLabel(path) !== "未分类");
  }

  function toneFor(path) {
    const text = String(path || "");
    return tones.find((item) => text.includes(item.key)) || {
      color: "#2f7df6",
      soft: "#e8f1ff",
      text: "#1d4ed8",
      tone: "blue",
    };
  }

  function styleVars(path) {
    const tone = toneFor(path);
    return `--card:${tone.color};--card-soft:${tone.soft};--card-text:${tone.text};`;
  }

  function sourceClass(source) {
    if (source === "qlib") return "qlib";
    if (source === "LumenAlpha") return "lumen";
    if (source === "Eastmoney") return "eastmoney";
    return "sector";
  }

  function sourceName(source) {
    if (source === "Eastmoney") return "人气";
    if (source === "qlib" || source === "LumenAlpha") return "LumenAlpha";
    return source || "--";
  }

  function projectLabel(project) {
    if (project === "qlib" || project === "LumenAlpha") return "LumenAlpha";
    return project || "--";
  }

  function factorSourceLabel(item) {
    const source = item.source_file || item.family || "--";
    if (item.family === "PriceActionMarker") return "LumenAlpha 图表信号";
    if (item.project === "qlib" || /microsoft-qlib/i.test(source)) return "LumenAlpha 因子库";
    return brandText(source);
  }

  function aiKey(type, id) {
    return `${type}:${id || "latest"}`;
  }

  const modeSections = {
    overview: { section: "overviewSection", nav: "今日概览" },
    multi: { section: "trendsSection", nav: "板块行情" },
    list: { section: "signalsSection", nav: "触发信号" },
  };

  const sectionModes = {
    overviewSection: "overview",
    leadersSection: "overview",
    trendsSection: "multi",
    signalsSection: "list",
  };

  function syncModeButtons() {
    document.querySelectorAll(".mode").forEach((button) => {
      button.classList.toggle("active", state.view === "dashboard" && button.dataset.mode === state.mode);
    });
  }

  function compactLeader(leader) {
    if (!leader) return null;
    return {
      code: normalizeCode(leader.code),
      name: leader.name,
      board_path: leader.board_path,
      rank: leader.rank,
      rank_change: leader.rank_change,
      combined_score: leader.combined_score,
      qlib_factor_score: leader.qlib_factor_score,
      lumen_score: leader.lumen_score,
      popularity_score: leader.popularity_score,
      sector_trend_score: leader.sector_trend_score,
      ret_1d: leader.ret_1d,
      ret_5d: leader.ret_5d,
      ret_20d: leader.ret_20d,
      volume_ratio_20: leader.volume_ratio_20,
      top_signals: leader.top_signals,
    };
  }

  function compactSignal(signal) {
    return {
      code: normalizeCode(signal.code),
      name: signal.name,
      board_path: signal.board_path,
      source_project: signal.source_project,
      source_module: signal.source_module,
      signal_name: signal.signal_name,
      signal_score: signal.signal_score,
      direction: signal.direction,
      evidence: signal.evidence,
    };
  }

  function compactBoard(board) {
    if (!board) return null;
    return {
      board_path: board.board_path,
      board_l1: board.board_l1,
      board_l2: board.board_l2,
      board_l3: board.board_l3,
      is_tech: board.is_tech,
      stock_count: board.stock_count,
      best_rank: board.best_rank,
      avg_rank: board.avg_rank,
      sector_ret_5d: board.sector_ret_5d,
      sector_ret_20d: board.sector_ret_20d,
      sector_trend_score: board.sector_trend_score,
      curve_member_count: board.curve_member_count,
      top_stocks: board.top_stocks,
    };
  }

  function aiList(items) {
    const rows = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!rows.length) return "";
    return `<ul>${rows.map((item) => `<li>${escapeHtml(brandText(item))}</li>`).join("")}</ul>`;
  }

  function renderAiResult(key, title) {
    const item = state.aiAnalyses[key];
    if (!item) {
      return `
        <div class="ai-card">
          <div class="ai-card-head">
            <div>
              <strong>${escapeHtml(title)}</strong>
              <span>DeepSeek 只做末端解释，不参与本地打分</span>
            </div>
            <button class="ai-button" type="button" data-ai-key="${escapeHtml(key)}">AI分析</button>
          </div>
        </div>
      `;
    }
    if (item.status === "loading") {
      return `
        <div class="ai-card">
          <div class="ai-card-head">
            <div><strong>${escapeHtml(title)}</strong><span>正在请求 DeepSeek...</span></div>
            <button class="ai-button" type="button" disabled>分析中</button>
          </div>
        </div>
      `;
    }
    if (item.status === "error") {
      return `
        <div class="ai-card ai-card-error">
          <div class="ai-card-head">
            <div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(item.error || "AI分析失败")}</span></div>
            <button class="ai-button" type="button" data-ai-key="${escapeHtml(key)}">重试</button>
          </div>
        </div>
      `;
    }
    const analysis = item.analysis || {};
    const fullSummary = brandText(analysis.summary || "--");
    const opportunity = brandText((analysis.bullish_points || [])[0] || "暂无明确机会信号");
    const risk = brandText((analysis.risk_points || [])[0] || "暂无新增风险提示");
    const plan = brandText((analysis.next_day_plan || [])[0] || "继续观察量价与板块强弱");
    return `
      <div class="ai-card">
        <div class="ai-card-head">
          <div>
            <strong>${escapeHtml(title)}</strong>
            <span>${item.cached ? "缓存结果" : "实时结果"}  |  ${escapeHtml(item.model || "DeepSeek")}</span>
          </div>
          <button class="ai-button subtle" type="button" data-ai-key="${escapeHtml(key)}" data-refresh="1">刷新</button>
        </div>
        <p class="ai-summary">${escapeHtml(shortText(fullSummary))}</p>
        <div class="ai-action-list">
          <div class="ai-action opportunity"><span>机会</span><p>${escapeHtml(opportunity)}</p></div>
          <div class="ai-action risk"><span>风险</span><p>${escapeHtml(risk)}</p></div>
          <div class="ai-action observe"><span>观察</span><p>${escapeHtml(plan)}</p></div>
        </div>
        <details class="ai-details">
          <summary>查看完整依据与信号分歧</summary>
          ${fullSummary.length > 180 ? `<p class="ai-full-summary">${escapeHtml(fullSummary)}</p>` : ""}
          <div class="ai-grid">
            <div><span>看多依据</span>${aiList(analysis.bullish_points)}</div>
            <div><span>风险点</span>${aiList(analysis.risk_points)}</div>
            <div><span>信号分歧</span>${aiList(analysis.signal_conflicts)}</div>
            <div><span>观察计划</span>${aiList(analysis.next_day_plan)}</div>
          </div>
        </details>
        <div class="ai-foot">置信度 ${escapeHtml(analysis.confidence || "--")}</div>
      </div>
    `;
  }

  function attachAiButton(container, type, id, contextBuilder, rerender) {
    if (!container) return;
    const key = aiKey(type, id);
    container.querySelectorAll(`[data-ai-key="${CSS.escape(key)}"]`).forEach((button) => {
      button.addEventListener("click", () => {
        requestAiAnalysis(type, id, contextBuilder(), button.dataset.refresh === "1", rerender);
      });
    });
  }

  async function requestAiAnalysis(type, id, context, refresh, rerender) {
    const key = aiKey(type, id);
    state.aiAnalyses[key] = { status: "loading" };
    rerender();
    try {
      const response = await fetch("/api/ai/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, id, context, refresh }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      state.aiAnalyses[key] = {
        status: "ready",
        analysis: payload.analysis,
        cached: Boolean(payload.cached),
        model: payload.model,
        generatedAt: payload.generatedAt,
      };
    } catch (error) {
      state.aiAnalyses[key] = { status: "error", error: error.message || "AI分析失败" };
    }
    rerender();
  }

  function stockAiContext(leader, chart) {
    const code = normalizeCode(leader.code);
    const signals = (data.signals || [])
      .filter((item) => normalizeCode(item.code) === code)
      .slice(0, 16)
      .map(compactSignal);
    const peers = (data.leaders || [])
      .filter((item) => item.board_path === leader.board_path && normalizeCode(item.code) !== code)
      .slice(0, 10)
      .map(compactLeader);
    const board = (data.boards || []).find((item) => item.board_path === leader.board_path);
    return {
      generatedAt: data.generatedAt,
      review: data.review,
      stock: compactLeader(leader),
      board: compactBoard(board),
      recentSignals: signals,
      peerLeaders: peers,
      chart: {
        candles: (chart.candles || []).slice(-30),
        markers: (chart.markers || []).slice(-12),
      },
    };
  }

  function boardAiContext(board, chart) {
    const leaders = (data.leaders || [])
      .filter((item) => item.board_path === board.board_path)
      .slice(0, 16)
      .map(compactLeader);
    const signals = (data.signals || [])
      .filter((item) => item.board_path === board.board_path)
      .slice(0, 30)
      .map(compactSignal);
    return {
      generatedAt: data.generatedAt,
      review: data.review,
      board: compactBoard(board),
      leaders,
      recentSignals: signals,
      chart: {
        candles: (chart.candles || []).slice(-30),
        markers: (chart.markers || []).slice(-12),
        constituents: (chart.constituents || []).slice(0, 24),
      },
    };
  }

  function dailyAiContext() {
    const boards = [...(data.boards || [])]
      .filter(isClassifiedBoard)
      .sort((a, b) => Number(b.sector_trend_score || -1) - Number(a.sector_trend_score || -1))
      .slice(0, 12)
      .map(compactBoard);
    const leaders = [...(data.leaders || [])]
      .sort((a, b) => {
        const classDiff = Number(isClassifiedBoard(b)) - Number(isClassifiedBoard(a));
        if (classDiff) return classDiff;
        return Number(b.combined_score || -1) - Number(a.combined_score || -1);
      })
      .slice(0, 24)
      .map(compactLeader);
    return {
      generatedAt: data.generatedAt,
      review: data.review,
      dailyReport: state.dailyReportText.slice(0, 18000),
      boards,
      leaders,
      topSignals: (data.signals || []).slice(0, 40).map(compactSignal),
    };
  }

  function filteredLeaders() {
    const leaders = data.leaders || [];
    if (state.board !== "all") return leaders.filter((item) => item.board_path === state.board);
    return [...leaders].sort((a, b) => {
      const classDiff = Number(isClassifiedBoard(b)) - Number(isClassifiedBoard(a));
      if (classDiff) return classDiff;
      return Number(b.combined_score || -1) - Number(a.combined_score || -1);
    });
  }

  function filteredSignals() {
    const signals = data.signals || [];
    let scoped = state.board === "all" ? signals : signals.filter((item) => item.board_path === state.board);
    const keyword = state.signalSearch.trim().toLowerCase();
    if (keyword) {
      scoped = scoped.filter((item) => {
        const text = [
          item.code,
          item.name,
          item.board_path,
          item.source_project,
          item.source_module,
          item.signal_name,
          item.evidence,
        ].join(" ").toLowerCase();
        return text.includes(keyword);
      });
    }
    const order = ["qlib", "LumenAlpha", "Eastmoney"];
    const groups = order.map((source) => scoped.filter((item) => item.source_project === source));
    const others = scoped.filter((item) => !order.includes(item.source_project));
    groups.push(others);
    groups.forEach((group) => {
      group.sort((a, b) => {
        const aTotal = String(a.signal_name || "").includes("total_score") ? 1 : 0;
        const bTotal = String(b.signal_name || "").includes("total_score") ? 1 : 0;
        if (aTotal !== bTotal) return aTotal - bTotal;
        return Math.abs(Number(b.signal_score || 0)) - Math.abs(Number(a.signal_score || 0));
      });
    });
    const balanced = [];
    const max = Math.max(...groups.map((group) => group.length), 0);
    for (let i = 0; i < max; i += 1) {
      groups.forEach((group) => {
        if (group[i]) balanced.push(group[i]);
      });
    }
    const seen = new Set();
    const unique = [];
    for (const row of balanced) {
      const code = normalizeCode(row.code);
      if (!code || seen.has(code)) continue;
      seen.add(code);
      unique.push(row);
    }
    return unique;
  }

  function curvesByBoard() {
    const map = new Map();
    (data.curves || []).forEach((row) => {
      if (!map.has(row.board_path)) map.set(row.board_path, []);
      map.get(row.board_path).push(row);
    });
    for (const rows of map.values()) {
      rows.sort((a, b) => String(a.date).localeCompare(String(b.date)));
    }
    return map;
  }

  function renderGeneratedAt() {
    const review = data.review || {};
    const time = String(data.generatedAt || "--").replace("T", " ");
    $("generatedAt").textContent = `更新 ${time} · 历史覆盖 ${review.history_ok || 0}/${review.history_total || 0}`;
    $("briefTime").textContent = time;
    const health = Number(review.history_total) ? Math.round(Number(review.history_ok || 0) / Number(review.history_total) * 100) : 0;
    const healthPill = $("healthPill");
    healthPill.className = `health-pill ${health >= 90 ? "healthy" : health >= 75 ? "warning" : "danger"}`;
    healthPill.innerHTML = `<i></i>${health ? `数据覆盖 ${health}%` : "数据待检查"}`;
  }

  function renderMarketBrief() {
    const boards = [...(data.boards || [])]
      .filter(isClassifiedBoard)
      .filter((board) => Number.isFinite(Number(board.sector_trend_score)))
      .sort((a, b) => Number(b.sector_trend_score) - Number(a.sector_trend_score));
    const strongest = boards.slice(0, 3);
    const weakening = [...boards]
      .filter((board) => Number(board.sector_ret_5d) < 0 || Number(board.sector_trend_score) < 40)
      .sort((a, b) => Number(a.sector_trend_score) - Number(b.sector_trend_score))
      .slice(0, 2);
    const average = strongest.length
      ? strongest.reduce((sum, board) => sum + Number(board.sector_trend_score || 0), 0) / strongest.length
      : 0;
    const regime = average >= 75 ? "主线清晰，强势板块延续" : average >= 55 ? "轮动偏快，优先跟踪强势方向" : "市场分散，控制追高节奏";
    const riskLabel = weakening.length >= 2 ? "中等" : "偏低";
    $("marketBrief").innerHTML = `
      <div class="brief-regime">
        <span>市场状态</span>
        <strong>${escapeHtml(regime)}</strong>
        <p>结合板块趋势、人气排名与量价信号形成，不代表投资建议。</p>
      </div>
      <div class="brief-column">
        <span>强势 Top 3</span>
        ${strongest.map((board, index) => `<button type="button" data-brief-board="${escapeHtml(board.board_path)}"><em>${index + 1}</em><strong>${escapeHtml(boardLabel(board.board_path))}</strong><b>${num(board.sector_trend_score, 0)}</b></button>`).join("")}
      </div>
      <div class="brief-column weak">
        <span>降温关注</span>
        ${weakening.length ? weakening.map((board) => `<button type="button" data-brief-board="${escapeHtml(board.board_path)}"><strong>${escapeHtml(boardLabel(board.board_path))}</strong><b>${signedPct(board.sector_ret_5d)}</b></button>`).join("") : `<p>暂无明显退潮板块</p>`}
      </div>
      <div class="brief-risk"><span>风险等级</span><strong>${riskLabel}</strong><div class="risk-meter"><i style="--risk:${riskLabel === "中等" ? 54 : 28}%"></i></div></div>
    `;
    $("marketBrief").querySelectorAll("[data-brief-board]").forEach((button) => {
      button.addEventListener("click", () => {
        state.board = button.dataset.briefBoard;
        state.selectedBoard = state.board;
        state.section = "trendsSection";
        state.mode = "multi";
        state.activeDashboardNav = "板块行情";
        renderDashboard();
        renderViews();
      });
    });
  }

  function renderMetrics() {
    const review = data.review || {};
    const sourceCount = (data.signals || []).reduce((acc, row) => {
      acc[row.source_project] = (acc[row.source_project] || 0) + 1;
      return acc;
    }, {});
    const classifiedBoards = [...(data.boards || [])].filter(isClassifiedBoard);
    const curveMap = curvesByBoard();
    const curveBoards = classifiedBoards.filter((board) => curveMap.has(board.board_path)).length;
    const topBoard = classifiedBoards
      .filter((board) => Number.isFinite(Number(board.sector_trend_score)))
      .sort((a, b) => Number(b.sector_trend_score) - Number(a.sector_trend_score))[0];
    const lumenSignalCount = Number(sourceCount.qlib || 0) + Number(sourceCount.LumenAlpha || 0);
    const items = [
      ["最强板块", boardLabel(topBoard && topBoard.board_path), "查看板块行情"],
      ["入选股票", review.selected_stocks || "--", "今日有效样本"],
      ["统一信号", review.unified_signal_rows || "--", `${lumenSignalCount} 条 LumenAlpha 信号`],
      ["K线覆盖", `${curveBoards}/${classifiedBoards.length || 0}`, "明确分类板块"],
    ];
    $("metrics").innerHTML = items
      .map(([label, value, note]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></div>`)
      .join("");
  }

  function renderBoardChips() {
    const boards = [...(data.boards || [])].sort((a, b) => {
      const classDiff = Number(isClassifiedBoard(b)) - Number(isClassifiedBoard(a));
      if (classDiff) return classDiff;
      const trendDiff = Number(b.sector_trend_score || -1) - Number(a.sector_trend_score || -1);
      if (trendDiff) return trendDiff;
      return Number(a.best_rank || 9999) - Number(b.best_rank || 9999);
    });
    const allClass = state.board === "all" ? " active" : "";
    const chips = [
      `<button class="chip${allClass}" type="button" data-board="all"><span>全部</span><span class="count">${(data.leaders || []).length}</span></button>`,
      ...boards.map((board) => {
        const active = state.board === board.board_path ? " active" : "";
        const tone = toneFor(board.board_path);
        const label = boardLabel(board.board_path);
        const count = board.stock_count || 0;
        return `<button class="chip${active}" data-tone="${tone.tone}" type="button" data-board="${escapeHtml(board.board_path)}"><span>${escapeHtml(label)}</span><span class="count">${count}</span></button>`;
      }),
    ];
    $("boardChips").innerHTML = chips.join("");
    $("boardChips").querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        state.board = button.dataset.board || "all";
        if (state.board !== "all") state.selectedBoard = state.board;
        const leaders = filteredLeaders();
        state.leaderCode = leaders[0] && leaders[0].code;
        renderDashboard();
        renderViews();
      });
    });
  }

  const signalDisplayNames = {
    qlib_factor_score: "综合量价强度",
    momentum_20d: "20日动量",
    volume_ratio_20d: "20日量比",
    hot_rank_score: "市场人气",
    rank_change: "人气排名变化",
    lumen_total_score: "技术信号总分",
  };

  function signalDisplayName(value) {
    const name = String(value || "").replace(/^信号_/, "");
    return signalDisplayNames[name] || brandText(name).replaceAll("_", " ");
  }

  function signalCatalogQuery(value) {
    return String(value || "").replace(/^信号_/, "").replace(/^Q:/i, "");
  }

  function signalStrength(row) {
    const name = String(row.signal_name || "");
    const score = Number(row.signal_score);
    if (!Number.isFinite(score)) return { key: "neutral", label: "中性" };
    if (name === "qlib_factor_score" || name === "hot_rank_score") {
      if (score >= 70) return { key: "strong", label: "强势" };
      if (score < 45) return { key: "weak", label: "弱势" };
      return { key: "neutral", label: "中性" };
    }
    if (name === "rank_change") {
      if (score >= 5) return { key: "strong", label: "强势" };
      if (score <= -5) return { key: "weak", label: "弱势" };
      return { key: "neutral", label: "中性" };
    }
    const direction = String(row.direction || "").toLowerCase();
    if (direction === "bearish" || direction === "看空" || score <= -15) return { key: "weak", label: "弱势" };
    if ((direction === "bullish" || direction === "看多") && score >= 15) return { key: "strong", label: "强势" };
    return { key: "neutral", label: "中性" };
  }

  function signalScoreText(row) {
    const score = Number(row.signal_score);
    if (!Number.isFinite(score)) return "--";
    if (row.signal_name === "qlib_factor_score" || row.signal_name === "hot_rank_score") return score.toFixed(1);
    return `${score > 0 ? "+" : ""}${score.toFixed(1)}`;
  }

  function signalMeta(row) {
    const value = Number(row.signal_value);
    if (row.signal_name === "qlib_factor_score") return `量价综合 ${num(value, 1)}`;
    if (row.signal_name === "momentum_20d") return `20日涨跌 ${signedPct(value)}`;
    if (row.signal_name === "volume_ratio_20d") return `当前量比 ${num(value, 2)} 倍`;
    if (row.signal_name === "hot_rank_score") return `人气排名 #${Number.isFinite(value) ? Math.round(value) : "--"}`;
    if (row.signal_name === "rank_change") return `排名变化 ${Number.isFinite(value) && value > 0 ? "+" : ""}${num(value, 0)}`;
    if (row.signal_name === "lumen_total_score") return `技术总分 ${num(value, 1)}`;
    const evidence = shortText(brandText(row.evidence), 34);
    return evidence ? `${sourceName(row.source_project)} · ${evidence}` : sourceName(row.source_project);
  }

  function stockSignalRows(code) {
    const seen = new Set();
    return (data.signals || [])
      .filter((row) => normalizeCode(row.code) === normalizeCode(code))
      .filter((row) => {
        const key = `${row.source_project}:${row.signal_name}`;
        if (!row.signal_name || seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .sort((a, b) => Math.abs(Number(b.signal_score || 0)) - Math.abs(Number(a.signal_score || 0)));
  }

  function signalTriggerButton(row) {
    const strength = signalStrength(row);
    const name = signalDisplayName(row.signal_name);
    return `
      <button class="trigger-signal ${strength.key}" type="button" data-signal-query="${escapeHtml(signalCatalogQuery(row.signal_name))}" title="在信号台查看“${escapeHtml(name)}”的含义和计算方式">
        <span><strong>${escapeHtml(name)}</strong><small>${escapeHtml(signalMeta(row))}</small></span>
        <b>${escapeHtml(signalScoreText(row))}</b>
      </button>
    `;
  }

  function signalTriggerGroup(key, label, rows) {
    const visible = rows.slice(0, 3);
    const hidden = rows.slice(3);
    return `
      <div class="trigger-group ${key}">
        <div class="trigger-group-title"><span>${escapeHtml(label)}</span><b>${rows.length}</b></div>
        ${rows.length ? `<div class="trigger-list">${visible.map(signalTriggerButton).join("")}</div>` : `<div class="trigger-empty">暂无${escapeHtml(label)}</div>`}
        ${hidden.length ? `<details class="trigger-more"><summary>其余 ${hidden.length} 项</summary><div class="trigger-list">${hidden.map(signalTriggerButton).join("")}</div></details>` : ""}
      </div>
    `;
  }

  function renderTriggeredSignals(leader) {
    const rows = stockSignalRows(leader.code);
    const grouped = {
      strong: rows.filter((row) => signalStrength(row).key === "strong"),
      weak: rows.filter((row) => signalStrength(row).key === "weak"),
      neutral: rows.filter((row) => signalStrength(row).key === "neutral"),
    };
    return `
      <section class="triggered-signals">
        <div class="triggered-signals-head">
          <div><strong>今日触发信号</strong><span title="综合类分数不低于70为强势、低于45为弱势；普通信号按方向和相对强度分组。">共 ${rows.length} 项 · 相对强弱</span></div>
          <button type="button" data-open-stock-page="${escapeHtml(normalizeCode(leader.code))}">个股信号台 <span aria-hidden="true">→</span></button>
        </div>
        <div class="trigger-groups">
          ${signalTriggerGroup("strong", "强势信号", grouped.strong)}
          ${signalTriggerGroup("weak", "弱势信号", grouped.weak)}
          ${grouped.neutral.length ? signalTriggerGroup("neutral", "中性观察", grouped.neutral) : ""}
        </div>
      </section>
    `;
  }

  function openSignalStation(query = "") {
    state.view = "factor";
    state.factorProject = "all";
    state.factorFamily = "all";
    state.factorSearch = signalCatalogQuery(query);
    state.factorLimit = 24;
    if ($("factorSearch")) $("factorSearch").value = state.factorSearch;
    renderFactors();
    renderViews();
  }

  function bindSignalStationLinks(container) {
    if (!container) return;
    container.querySelectorAll("[data-signal-query]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        openSignalStation(button.dataset.signalQuery || "");
      });
    });
  }

  function renderMiniKline(chart, title = "K线缩略图") {
    const candles = (chart?.candles || []).slice(-18);
    if (!candles.length) return `<span class="mini-kline-empty">--</span>`;
    const width = 112;
    const height = 38;
    const highs = candles.map((c) => Number(c.high)).filter(Number.isFinite);
    const lows = candles.map((c) => Number(c.low)).filter(Number.isFinite);
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const span = Math.max(max - min, 0.01);
    const xStep = width / candles.length;
    const yOf = (value) => 3 + (max - Number(value)) / span * (height - 6);
    return `<svg class="mini-kline" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}">${candles.map((c, index) => {
      const x = index * xStep + xStep / 2;
      const open = Number(c.open);
      const close = Number(c.close);
      const up = close >= open;
      const yOpen = yOf(open);
      const yClose = yOf(close);
      const bodyY = Math.min(yOpen, yClose);
      return `<line class="${up ? "up" : "down"}" x1="${x.toFixed(1)}" y1="${yOf(c.high).toFixed(1)}" x2="${x.toFixed(1)}" y2="${yOf(c.low).toFixed(1)}"></line><rect class="${up ? "up" : "down"}" x="${(x - 1.7).toFixed(1)}" y="${bodyY.toFixed(1)}" width="3.4" height="${Math.max(1.2, Math.abs(yClose - yOpen)).toFixed(1)}"></rect>`;
    }).join("")}</svg>`;
  }

  function leaderCard(leader, index) {
    const active = state.leaderCode === leader.code ? " active" : "";
    const board = boardLabel(leader.board_path);
    const ret = Number(leader.ret_5d);
    const trend = Number(leader.sector_trend_score) >= 70 ? "强势" : Number(leader.sector_trend_score) >= 45 ? "轮动" : "观察";
    const chart = (data.stockCharts || {})[normalizeCode(leader.code)] || { candles: [] };
    return `
      <div class="leader-row${active}" data-code="${escapeHtml(leader.code)}" style="${styleVars(leader.board_path)}">
        <span class="leader-rank">${index + 1}</span>
        <button class="leader-stock" type="button" data-open-leader="${escapeHtml(leader.code)}"><strong>${escapeHtml(leader.name)}</strong><span>${escapeHtml(normalizeCode(leader.code))} · 人气 #${escapeHtml(leader.rank)}</span></button>
        <span class="board-tag">${escapeHtml(board)}</span>
        <strong class="leader-score">${num(leader.combined_score, 1)}</strong>
        <span class="return ${ret >= 0 ? "up" : "down"}">${signedPct(ret)}</span>
        <span class="trend-state ${trend === "强势" ? "strong" : trend === "轮动" ? "rotate" : "watch"}">${trend}</span>
        <span class="leader-chart">${renderMiniKline(chart, `${leader.name} 18日K线`)}</span>
        <button class="watch-toggle${isWatched(leader.code) ? " active" : ""}" type="button" data-watch="${escapeHtml(leader.code)}" aria-label="${isWatched(leader.code) ? "取消关注" : "加入自选"}">${isWatched(leader.code) ? "★" : "☆"}</button>
      </div>
    `;
  }

  function renderLeaderLadder() {
    const leaders = filteredLeaders();
    const title = state.board === "all" ? "综合强度排序，明确分类优先" : `${boardLabel(state.board)} · ${leaders.length} 只`;
    $("leaderSubhead").textContent = title;
    if (!leaders.length) {
      $("leaderLadder").innerHTML = `<div class="empty">当前板块暂无龙头样本</div>`;
      return;
    }
    if (!state.leaderCode || !leaders.some((leader) => leader.code === state.leaderCode)) {
      state.leaderCode = leaders[0].code;
    }
    const rows = leaders.slice(0, 24);
    $("leaderLadder").innerHTML = `
      <div class="leader-table-head"><span>#</span><span>股票</span><span>板块</span><span>综合</span><span>5日</span><span>趋势</span><span>18日K线</span><span></span></div>
      ${rows.map(leaderCard).join("")}
    `;
    $("leaderLadder").querySelectorAll(".leader-row").forEach((row) => {
      const select = () => {
        state.leaderCode = row.dataset.code;
        renderLeaderLadder();
        renderLeaderDetail();
      };
      row.addEventListener("click", (event) => {
        if (event.target.closest(".watch-toggle")) return;
        select();
      });
    });
    $("leaderLadder").querySelectorAll(".watch-toggle").forEach((button) => {
      button.addEventListener("click", () => {
        toggleWatch(button.dataset.watch);
        renderLeaderLadder();
        renderLeaderDetail();
      });
    });
  }

  function renderLeaderDetail() {
    const leader = (filteredLeaders().find((item) => item.code === state.leaderCode) || filteredLeaders()[0] || (data.leaders || [])[0]);
    if (!leader) {
      $("leaderDetail").innerHTML = `<div class="empty">暂无可展示股票</div>`;
      $("detailScore").textContent = "--";
      return;
    }
    const chart = (data.stockCharts || {})[normalizeCode(leader.code)] || { candles: [], markers: [] };
    const key = aiKey("stock", normalizeCode(leader.code));
    $("detailScore").textContent = num(leader.combined_score, 1);
    $("leaderDetail").innerHTML = `
      <div class="detail-title">
        <div><h3>${escapeHtml(leader.name)}</h3><p>${escapeHtml(normalizeCode(leader.code))} · 人气 #${escapeHtml(leader.rank)} · ${escapeHtml(boardLabel(leader.board_path))}</p></div>
        <button class="detail-watch${isWatched(leader.code) ? " active" : ""}" type="button" data-detail-watch="${escapeHtml(leader.code)}">${isWatched(leader.code) ? "★ 已关注" : "☆ 加自选"}</button>
      </div>
      <div class="score-bars">
        ${scoreLine("综合", leader.combined_score, "#ef4444")}
        ${scoreLine("量价强度", leader.qlib_factor_score, "#2f7df6")}
        ${scoreLine("技术形态", leader.lumen_score_norm, "#d97706")}
        ${scoreLine("板块动能", leader.sector_trend_score, "#059669")}
      </div>
      <div class="detail-kv">
        <div class="kv"><span>5日涨幅</span><strong>${pct(leader.ret_5d)}</strong></div>
        <div class="kv"><span>20日涨幅</span><strong>${pct(leader.ret_20d)}</strong></div>
        <div class="kv"><span>相对20日均线</span><strong>${signedPct(leader.ma20_bias)}</strong></div>
        <div class="kv"><span>量能变化</span><strong>${signedPct(leader.volume_ratio_20)}</strong></div>
      </div>
      <div class="kline-block">
        <div class="kline-head"><strong>30日K线</strong><span>近20日显著信号 ${chart.markers ? chart.markers.length : 0}</span></div>
        ${renderKlineChart(chart, `${leader.name} 30日K线`)}
      </div>
      ${renderTriggeredSignals(leader)}
      ${renderAiResult(key, "个股AI分析")}
    `;
    $("leaderDetail").querySelector("[data-detail-watch]")?.addEventListener("click", (event) => {
      toggleWatch(event.currentTarget.dataset.detailWatch);
      renderLeaderLadder();
      renderLeaderDetail();
    });
    bindSignalStationLinks($("leaderDetail"));
    $("leaderDetail").querySelector("[data-open-stock-page]")?.addEventListener("click", (event) => {
      openStockPage(event.currentTarget.dataset.openStockPage);
    });
    attachAiButton($("leaderDetail"), "stock", normalizeCode(leader.code), () => stockAiContext(leader, chart), renderLeaderDetail);
  }

  function scoreLine(label, value, color) {
    const width = clamp(value);
    return `
      <div class="score-line">
        <label><span>${escapeHtml(label)}</span><strong>${num(value, 1)}</strong></label>
        <div class="bar"><span style="--w:${width}%;--bar:${color};"></span></div>
      </div>
    `;
  }

  function markerTone(direction) {
    if (direction === "bearish") return "bearish";
    if (direction === "bullish") return "bullish";
    return "neutral";
  }

  function markerFill(direction) {
    if (direction === "bearish") return "#059669";
    if (direction === "bullish") return "#ef4444";
    return "#64748b";
  }

  function renderKlineChart(chart, title = "30日K线", windowSize = 30, options = {}) {
    const allCandles = (chart && chart.candles) || [];
    const candles = allCandles.slice(-windowSize);
    const markers = (chart && chart.markers) || [];
    const expanded = options.expanded === true;
    if (!candles.length) {
      return `<div class="empty">暂无 K 线数据</div>`;
    }
    const width = expanded ? 1350 : 560;
    const height = 300;
    const pad = expanded
      ? { left: 52, right: 18, top: 14, bottom: 22 }
      : { left: 42, right: 14, top: 24, bottom: 22 };
    const plotW = width - pad.left - pad.right;
    const priceH = expanded ? 170 : 184;
    const volumeTop = expanded ? 218 : 224;
    const volumeH = expanded ? 48 : 48;
    const highs = candles.map((c) => Number(c.high)).filter(Number.isFinite);
    const lows = candles.map((c) => Number(c.low)).filter(Number.isFinite);
    markers.forEach((m) => {
      const y = Number(m.y);
      if (Number.isFinite(y)) {
        highs.push(y);
        lows.push(y);
      }
    });
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const span = Math.max(max - min, 0.01);
    const yOf = (value) => pad.top + (max - Number(value)) / span * priceH;
    const xOf = (index) => pad.left + (index + 0.5) / candles.length * plotW;
    const bodyW = Math.max(3, Math.min(8, plotW / candles.length * 0.55));
    const dateToIndex = new Map(candles.map((c, index) => [c.date, index]));
    const candleSvg = candles.map((c, index) => {
      const x = xOf(index);
      const open = Number(c.open);
      const close = Number(c.close);
      const high = Number(c.high);
      const low = Number(c.low);
      const up = close >= open;
      const cls = up ? "kline-up" : "kline-down";
      const yOpen = yOf(open);
      const yClose = yOf(close);
      const bodyY = Math.min(yOpen, yClose);
      const bodyH = Math.max(1.5, Math.abs(yClose - yOpen));
      return `
        <line class="kline-wick ${cls}" x1="${x.toFixed(1)}" y1="${yOf(high).toFixed(1)}" x2="${x.toFixed(1)}" y2="${yOf(low).toFixed(1)}"></line>
        <rect class="kline-body ${cls}" x="${(x - bodyW / 2).toFixed(1)}" y="${bodyY.toFixed(1)}" width="${bodyW.toFixed(1)}" height="${bodyH.toFixed(1)}"></rect>
      `;
    }).join("");
    const maxVolume = Math.max(...candles.map((c) => Number(c.volume || 0)), 1);
    const volumeSvg = candles.map((c, index) => {
      const volume = Number(c.volume || 0);
      const barH = volume / maxVolume * volumeH;
      const up = Number(c.close) >= Number(c.open);
      return `<rect class="kline-volume ${up ? "up" : "down"}" x="${(xOf(index) - bodyW / 2).toFixed(1)}" y="${(volumeTop + volumeH - barH).toFixed(1)}" width="${bodyW.toFixed(1)}" height="${Math.max(1, barH).toFixed(1)}"></rect>`;
    }).join("");
    function movingAverage(size) {
      return candles.map((candle, index) => {
        if (index < size - 1) return null;
        const rows = candles.slice(index - size + 1, index + 1);
        return rows.reduce((sum, row) => sum + Number(row.close), 0) / size;
      });
    }
    function averagePath(size) {
      return movingAverage(size).map((value, index) => value == null ? null : `${index === size - 1 ? "M" : "L"}${xOf(index).toFixed(1)},${yOf(value).toFixed(1)}`).filter(Boolean).join(" ");
    }
    const visibleMarkers = markers.filter((m) => dateToIndex.has(m.date));
    const markerCounts = visibleMarkers.reduce((counts, marker) => {
      counts.set(marker.date, (counts.get(marker.date) || 0) + 1);
      return counts;
    }, new Map());
    const markerSlots = new Map();
    const labeledFrom = Math.max(0, visibleMarkers.length - 6);
    const markerSvg = visibleMarkers.map((m, markerIndex) => {
      const index = dateToIndex.get(m.date);
      const candle = candles[index];
      const slot = markerSlots.get(m.date) || 0;
      markerSlots.set(m.date, slot + 1);
      const dateCount = markerCounts.get(m.date) || 1;
      const x = xOf(index) + (slot - (dateCount - 1) / 2) * (expanded ? 11 : 5);
      const y = yOf(m.y || candle.close);
      const label = brandText(m.label || "").replace(/^Q:/i, "").slice(0, 12);
      const labelW = Math.max(34, Math.min(92, label.length * 8 + 10));
      const labelX = Math.max(4, Math.min(width - labelW - 4, x - labelW / 2));
      const labelY = Math.max(3, y - 18 - (markerIndex % 3) * 12);
      const tone = markerTone(m.direction);
      const score = Number(m.score);
      const markerTitle = `${m.date} · ${label}${Number.isFinite(score) ? ` · ${score > 0 ? "+" : ""}${score.toFixed(1)}` : ""}`;
      const showLabel = markerIndex >= labeledFrom;
      if (expanded) {
        return `
          <g class="kline-marker ${tone} expanded-marker">
            <title>${escapeHtml(markerTitle)}</title>
            <line class="signal-tick" x1="${x.toFixed(1)}" y1="${(y - 12).toFixed(1)}" x2="${x.toFixed(1)}" y2="${(y + 12).toFixed(1)}"></line>
            <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="7.4"></circle>
            <text class="marker-index" x="${x.toFixed(1)}" y="${(y + 3.2).toFixed(1)}" text-anchor="middle">${markerIndex + 1}</text>
          </g>
        `;
      }
      return `
        <g class="kline-marker ${tone}">
          <title>${escapeHtml(markerTitle)}</title>
          ${showLabel ? `<line x1="${x.toFixed(1)}" y1="${(labelY + 14).toFixed(1)}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${markerFill(m.direction)}" stroke-dasharray="2 2" opacity="0.65"></line>` : `<line class="signal-tick" x1="${x.toFixed(1)}" y1="${(y - 7).toFixed(1)}" x2="${x.toFixed(1)}" y2="${(y + 7).toFixed(1)}"></line>`}
          <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${showLabel ? "3.6" : "3.1"}"></circle>
          ${showLabel ? `<rect x="${labelX.toFixed(1)}" y="${labelY.toFixed(1)}" width="${labelW.toFixed(1)}" height="16"></rect><text x="${(labelX + 5).toFixed(1)}" y="${(labelY + 11).toFixed(1)}">${escapeHtml(label)}</text>` : ""}
        </g>
      `;
    }).join("");
    const start = candles[0]?.date?.slice(5) || "";
    const end = candles[candles.length - 1]?.date?.slice(5) || "";
    const dateTicks = expanded
      ? candles.map((candle, index) => {
        if (index % 5 !== 0 && index !== candles.length - 1) return "";
        const x = xOf(index);
        return `<line class="kline-date-tick" x1="${x.toFixed(1)}" y1="${volumeTop + volumeH}" x2="${x.toFixed(1)}" y2="${volumeTop + volumeH + 5}"></line><text class="kline-date-label" x="${x.toFixed(1)}" y="${height - 8}" text-anchor="middle">${escapeHtml(candle.date.slice(5))}</text>`;
      }).join("")
      : `<text x="${pad.left}" y="${height - 6}" font-size="9" fill="#94a3b8">${escapeHtml(start)}</text><text x="${width - pad.right - 28}" y="${height - 6}" font-size="9" fill="#94a3b8">${escapeHtml(end)}</text>`;
    const grid = [0, 0.5, 1].map((ratio) => {
      const y = pad.top + priceH * ratio;
      const value = max - span * ratio;
      return `<line class="kline-grid" x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}"></line><text class="kline-y-label" x="4" y="${y + 3}">${num(value, 2)}</text>`;
    }).join("");
    const chartChrome = options.hideChrome ? "" : `
      <text x="${pad.left}" y="14" font-size="10" fill="#64748b">${escapeHtml(title)}</text>
      <text class="kline-legend ma5" x="${width - 132}" y="14">MA5</text>
      <text class="kline-legend ma10" x="${width - 92}" y="14">MA10</text>
      <text class="kline-legend ma20" x="${width - 48}" y="14">MA20</text>
    `;
    return `
      <svg class="kline-chart${expanded ? " expanded-kline-chart" : ""}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}">
        ${grid}
        <line class="kline-axis" x1="${pad.left}" y1="${pad.top + priceH}" x2="${width - pad.right}" y2="${pad.top + priceH}"></line>
        ${chartChrome}
        ${dateTicks}
        ${candleSvg}
        <path class="ma-line ma5" d="${averagePath(5)}"></path>
        <path class="ma-line ma10" d="${averagePath(10)}"></path>
        <path class="ma-line ma20" d="${averagePath(20)}"></path>
        ${markerSvg}
        <line class="kline-axis" x1="${pad.left}" y1="${volumeTop + volumeH}" x2="${width - pad.right}" y2="${volumeTop + volumeH}"></line>
        <text class="kline-volume-label" x="4" y="${volumeTop + 10}">成交量</text>
        ${volumeSvg}
      </svg>
    `;
  }

  function stockChartMarkers(chart) {
    const dates = new Set((chart?.candles || []).map((candle) => candle.date));
    return (chart?.markers || []).filter((marker) => dates.has(marker.date));
  }

  function markerDisplayName(marker) {
    return brandText(marker?.label || "信号").replace(/^(?:Q|L|热):/i, "");
  }

  function markerCatalogQuery(marker) {
    const name = markerDisplayName(marker);
    const queries = {
      LumenAlpha因子: "qlib_factor_score",
      qlib因子: "qlib_factor_score",
      Lumen总分: "lumen_total_score",
      "20日动量": "momentum_20d",
      量比: "volume_ratio_20d",
      人气: "hot_rank_score",
    };
    return queries[name] || name;
  }

  function markerSourceName(marker) {
    if (marker?.source === "price") return "价格行为";
    return sourceName(marker?.source);
  }

  function markerScoreText(marker) {
    const score = Number(marker?.score);
    if (!Number.isFinite(score)) return "--";
    const name = markerDisplayName(marker);
    if (marker?.source === "price" && name === "放量上涨") return `${score.toFixed(2)} 倍量`;
    if (marker?.source === "price") return `${score > 0 ? "+" : ""}${score.toFixed(1)}%`;
    return score.toFixed(1);
  }

  function stockSignalGroups(markers) {
    const grouped = new Map();
    markers.forEach((marker, index) => {
      const row = { ...marker, markerIndex: index + 1 };
      if (!grouped.has(marker.date)) grouped.set(marker.date, []);
      grouped.get(marker.date).push(row);
    });
    return [...grouped.entries()].reverse().map(([date, rows]) => ({ date, rows }));
  }

  function visibleStockSignalGroups(groups) {
    if (state.stockSignalsExpanded) return groups;
    const visible = [];
    let rows = 0;
    for (const group of groups) {
      visible.push(group);
      rows += group.rows.length;
      if (rows >= 10) break;
    }
    return visible;
  }

  function signalStrengthLabel(direction) {
    if (direction === "bullish") return "强";
    if (direction === "bearish") return "弱";
    return "中性";
  }

  function renderStockSignalTable(markers) {
    if (!markers.length) return `<div class="empty">最近 20 个交易日暂无显著信号</div>`;
    const groups = stockSignalGroups(markers);
    const visibleGroups = visibleStockSignalGroups(groups);
    const rows = visibleGroups.map(({ date, rows: dateRows }) => dateRows.map((marker, rowIndex) => {
      const tone = markerTone(marker.direction);
      const name = markerDisplayName(marker);
      return `
        <tr>
          ${rowIndex === 0 ? `<th scope="rowgroup" rowspan="${dateRows.length}"><strong>${escapeHtml(date.slice(5))}</strong><small>${dateRows.length} 项</small></th>` : ""}
          <td class="stock-signal-index"><span class="${tone}">${String(marker.markerIndex).padStart(2, "0")}</span></td>
          <td class="stock-signal-name"><strong>${escapeHtml(name)}</strong></td>
          <td>${escapeHtml(markerSourceName(marker))}</td>
          <td>${escapeHtml(markerScoreText(marker))}</td>
          <td><span class="stock-signal-strength ${tone}">${signalStrengthLabel(marker.direction)}</span></td>
          <td><button type="button" data-signal-query="${escapeHtml(markerCatalogQuery(marker))}" title="查看“${escapeHtml(name)}”的含义和计算方式">释义</button></td>
        </tr>
      `;
    }).join("")).join("");
    const canToggle = groups.length > visibleGroups.length || state.stockSignalsExpanded;
    return `
      <div class="stock-signal-table-wrap">
        <table class="stock-signal-table">
          <thead><tr><th>日期</th><th>#</th><th>信号名称</th><th>信号源</th><th>触发值 / 说明</th><th>强度</th><th>操作</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      ${canToggle ? `<button class="stock-signal-toggle" type="button" data-expand-stock-signals>${state.stockSignalsExpanded ? "收起明细" : `展开更多（共 ${markers.length} 项信号）`} <span aria-hidden="true">${state.stockSignalsExpanded ? "↑" : "↓"}</span></button>` : ""}
    `;
  }

  function chartAverageValue(candles, windowSize) {
    const closes = (candles || []).slice(-windowSize).map((candle) => Number(candle.close)).filter(Number.isFinite);
    if (closes.length < windowSize) return NaN;
    return closes.reduce((sum, value) => sum + value, 0) / closes.length;
  }

  function markerNameSummary(markers, direction, limit = 5) {
    const counts = new Map();
    markers.filter((marker) => marker.direction === direction).forEach((marker) => {
      const name = markerDisplayName(marker);
      const current = counts.get(name) || { marker, count: 0 };
      current.count += 1;
      counts.set(name, current);
    });
    return [...counts.values()].sort((a, b) => b.count - a.count).slice(0, limit);
  }

  function renderSignalSummary(markers, direction) {
    const rows = markerNameSummary(markers, direction);
    if (!rows.length) return `<span class="stock-insight-empty">暂无</span>`;
    return rows.map(({ marker, count }) => `<button type="button" class="${markerTone(direction)}" data-signal-query="${escapeHtml(markerCatalogQuery(marker))}">${escapeHtml(markerDisplayName(marker))}${count > 1 ? ` ×${count}` : ""}</button>`).join("");
  }

  function stockDecisionText(leader, bearishCount) {
    const trend = Number(leader.combined_score) >= 70 ? "趋势偏强" : Number(leader.combined_score) >= 50 ? "趋势中性" : "趋势偏弱";
    const momentum = Number(leader.ret_5d) > 0 ? "短期动量占优" : "短期动量回落";
    const risk = bearishCount ? `近 20 个交易日出现 ${bearishCount} 个风险信号，关注回撤持续性。` : "近期没有显著回撤信号。";
    return `${trend}，${momentum}。${risk}`;
  }

  function openStockPage(code) {
    const normalizedCode = normalizeCode(code);
    if (normalizedCode !== normalizeCode(state.leaderCode)) state.stockSignalsExpanded = false;
    state.leaderCode = normalizedCode;
    state.view = "stock";
    renderStockPage();
    renderViews();
  }

  function closeStockPage() {
    state.view = "dashboard";
    state.section = "leadersSection";
    state.mode = "overview";
    state.activeDashboardNav = "龙头观察";
    renderDashboard();
    renderViews();
  }

  function renderStockPage() {
    const container = $("stockPage");
    if (!container) return;
    const code = normalizeCode(state.leaderCode);
    const leader = (data.leaders || []).find((item) => normalizeCode(item.code) === code);
    if (!leader) {
      container.innerHTML = `<button class="stock-back" type="button" data-stock-back><span aria-hidden="true">←</span> 返回龙头观察</button><div class="empty">没有找到该股票的数据</div>`;
      container.querySelector("[data-stock-back]")?.addEventListener("click", closeStockPage);
      return;
    }
    const chart = (data.stockCharts || {})[code] || { candles: [], markers: [] };
    const candles = chart.candles || [];
    const markers = stockChartMarkers(chart);
    const latest = candles[candles.length - 1];
    const bullishCount = markers.filter((marker) => marker.direction === "bullish").length;
    const bearishCount = markers.filter((marker) => marker.direction === "bearish").length;
    const neutralCount = markers.length - bullishCount - bearishCount;
    const ma5 = chartAverageValue(candles, 5);
    const ma10 = chartAverageValue(candles, 10);
    const ma20 = chartAverageValue(candles, 20);
    const key = aiKey("stock", code);
    container.innerHTML = `
      <header class="stock-page-header" style="${styleVars(leader.board_path)}">
        <div class="stock-page-identity">
          <button class="stock-back" type="button" data-stock-back><span aria-hidden="true">←</span> 龙头观察</button>
          <h2>${escapeHtml(leader.name)} <small>${escapeHtml(code)}</small></h2>
          <p><span class="stock-industry">${escapeHtml(boardLabel(leader.board_path))}</span><span>人气 #${escapeHtml(leader.rank)}</span><span>行情截至 ${escapeHtml(latest?.date || "--")}</span></p>
        </div>
        <div class="stock-header-stat"><span>最新价</span><strong class="${Number(latest?.pct) >= 0 ? "up" : "down"}">${num(latest?.close, 2)}</strong><small>${Number.isFinite(Number(latest?.pct)) ? `${Number(latest.pct) >= 0 ? "+" : ""}${num(latest.pct, 2)}%` : "--"}</small></div>
        <div class="stock-header-stat"><span>5日</span><strong class="${Number(leader.ret_5d) >= 0 ? "up" : "down"}">${pct(leader.ret_5d)}</strong><small>短线动量</small></div>
        <div class="stock-header-stat"><span>20日</span><strong class="${Number(leader.ret_20d) >= 0 ? "up" : "down"}">${pct(leader.ret_20d)}</strong><small>波段动量</small></div>
        <div class="stock-header-stat"><span>量价强度</span><strong>${num(leader.qlib_factor_score, 1)}</strong><small>LumenAlpha</small></div>
        <div class="stock-header-stat"><span>显著信号</span><strong>${markers.length}</strong><small>${bullishCount} 强 · ${bearishCount} 弱${neutralCount ? ` · ${neutralCount} 中性` : ""}</small></div>
        <div class="stock-page-score">
          <button class="stock-page-watch${isWatched(code) ? " active" : ""}" type="button" data-stock-page-watch="${escapeHtml(code)}">${isWatched(code) ? "★ 已关注" : "☆ 加入自选"}</button>
          <span>综合强度</span><strong>${num(leader.combined_score, 1)}</strong>
        </div>
      </header>
      <section class="stock-chart-section">
        <div class="stock-section-head">
          <div class="stock-chart-title"><h3>30日 K 线</h3><p>最近 20 个交易日的显著信号全部标记</p></div>
          <div class="stock-chart-meta">
            <div class="stock-ma-legend"><span class="ma5">MA5 <b>${num(ma5, 2)}</b></span><span class="ma10">MA10 <b>${num(ma10, 2)}</b></span><span class="ma20">MA20 <b>${num(ma20, 2)}</b></span></div>
            <div class="stock-chart-legend"><span class="bullish"><i></i>强势</span><span class="bearish"><i></i>弱势</span><span class="neutral"><i></i>中性</span></div>
          </div>
        </div>
        <div class="stock-chart-scroll">${renderKlineChart(chart, `${leader.name} 30日K线`, 30, { expanded: true, hideChrome: true })}</div>
      </section>
      <div class="stock-research-grid">
        <section class="stock-signal-section">
          <div class="stock-section-head"><div><h3>信号明细</h3><p>按日期分组（最新在上）</p></div><strong class="stock-signal-total">${markers.length} 项</strong></div>
          ${renderStockSignalTable(markers)}
        </section>
        <aside class="stock-insight-rail">
          <section class="stock-insight-block stock-decision">
            <div class="stock-insight-head"><h3>当前判断</h3><span>基于 ${escapeHtml(latest?.date || "--")}</span></div>
            <p>${escapeHtml(stockDecisionText(leader, bearishCount))}</p>
          </section>
          <section class="stock-insight-block">
            <div class="stock-insight-head"><h3>强势信号</h3><strong class="bullish">${bullishCount}</strong></div>
            <div class="stock-insight-signals">${renderSignalSummary(markers, "bullish")}</div>
          </section>
          <section class="stock-insight-block">
            <div class="stock-insight-head"><h3>风险信号</h3><strong class="bearish">${bearishCount}</strong></div>
            <div class="stock-insight-signals">${renderSignalSummary(markers, "bearish")}</div>
          </section>
          <section class="stock-insight-block stock-score-breakdown">
            <div class="stock-insight-head"><h3>评分结构</h3><span>0-100</span></div>
            <div class="score-bars">
              ${scoreLine("综合", leader.combined_score, "#ef4444")}
              ${scoreLine("量价强度", leader.qlib_factor_score, "#2563eb")}
              ${scoreLine("技术形态", leader.lumen_score_norm, "#d97706")}
              ${scoreLine("板块动能", leader.sector_trend_score, "#059669")}
            </div>
          </section>
          <section class="stock-insight-block stock-page-ai">${renderAiResult(key, "AI 分析")}</section>
        </aside>
      </div>
    `;
    container.querySelector("[data-stock-back]")?.addEventListener("click", closeStockPage);
    container.querySelector("[data-stock-page-watch]")?.addEventListener("click", async (event) => {
      await toggleWatch(event.currentTarget.dataset.stockPageWatch);
      renderStockPage();
    });
    container.querySelector("[data-expand-stock-signals]")?.addEventListener("click", () => {
      state.stockSignalsExpanded = !state.stockSignalsExpanded;
      renderStockPage();
    });
    bindSignalStationLinks(container);
    attachAiButton(container, "stock", code, () => stockAiContext(leader, chart), renderStockPage);
    requestAnimationFrame(() => {
      const chartViewport = container.querySelector(".stock-chart-scroll");
      if (chartViewport && chartViewport.scrollWidth > chartViewport.clientWidth) {
        chartViewport.scrollLeft = chartViewport.scrollWidth - chartViewport.clientWidth;
      }
    });
  }

  function renderSectorTrends() {
    const boards = [...(data.boards || [])]
      .filter(isClassifiedBoard)
      .sort((a, b) => Number(b.sector_trend_score || -1) - Number(a.sector_trend_score || -1));
    const visible = state.board === "all" ? boards : boards.filter((board) => board.board_path === state.board);
    const chartBoards = boards.filter((board) => (data.boardCharts || {})[board.board_path]?.candles?.length).length;
    $("coverageBadge").textContent = `K线覆盖 ${chartBoards}/${boards.length}`;
    if (!visible.length) {
      state.selectedBoard = null;
      $("sectorTrends").innerHTML = `<div class="empty">当前筛选下暂无明确分类板块 K 线。</div>`;
      renderBoardDetail();
      return;
    }
    if (!state.selectedBoard || !visible.some((board) => board.board_path === state.selectedBoard)) {
      state.selectedBoard = visible[0]?.board_path || null;
    }
    $("sectorTrends").innerHTML = visible
      .map((board) => {
        const toneStyle = styleVars(board.board_path);
        const chart = (data.boardCharts || {})[board.board_path] || { candles: [] };
        const rows = (chart.candles || []).slice(-state.boardWindow);
        const active = state.selectedBoard === board.board_path ? " active" : "";
        const intervalRet = rows.length >= 2 ? Number(rows[rows.length - 1].close) / Number(rows[0].close) - 1 : NaN;
        return `
          <article class="trend-card${active}" style="${toneStyle}" data-board="${escapeHtml(board.board_path)}">
            <div class="trend-head">
              <div>
                <h3>${escapeHtml(boardLabel(board.board_path))}</h3>
                <p>${escapeHtml(boardSubLabel(board.board_path))}  |  样本 ${board.curve_member_count || 0}/${board.stock_count || 0}</p>
              </div>
              <div class="trend-score">${num(board.sector_trend_score, 0)}</div>
            </div>
            ${renderMiniKline({ candles: rows }, `${boardLabel(board.board_path)} ${state.boardWindow}日K线`)}
            <div class="trend-meta">
              <span class="${Number(intervalRet) >= 0 ? "up" : "down"}">${state.boardWindow}日 ${signedPct(intervalRet)}</span>
              <span>样本 ${board.curve_member_count || 0}/${board.stock_count || 0}</span>
            </div>
          </article>
        `;
      })
      .join("");
    $("sectorTrends").querySelectorAll(".trend-card").forEach((card) => {
      card.addEventListener("click", () => {
        state.selectedBoard = card.dataset.board || state.selectedBoard;
        renderSectorTrends();
      });
    });
    renderBoardDetail();
  }

  function renderBoardDetail() {
    if (!state.selectedBoard && state.board !== "all") {
      $("boardDetail").innerHTML = `<div class="empty">当前筛选下暂无板块详情。</div>`;
      return;
    }
    const fallback = (data.boards || []).find(isClassifiedBoard);
    const board = (data.boards || []).find((item) => item.board_path === state.selectedBoard) || fallback;
    if (!board) {
      $("boardDetail").innerHTML = `<div class="empty">暂无板块数据</div>`;
      return;
    }
    const chart = (data.boardCharts || {})[board.board_path] || { candles: [], markers: [], constituents: [] };
    const constituents = chart.constituents || [];
    const key = aiKey("board", board.board_path);
    $("boardDetail").innerHTML = `
      <div class="board-detail-card" style="${styleVars(board.board_path)}">
        <div class="board-detail-title">
          <div>
            <h3>${escapeHtml(boardLabel(board.board_path))}</h3>
            <p>${escapeHtml(boardSubLabel(board.board_path))}  |  最佳人气 #${escapeHtml(board.best_rank || "--")}</p>
          </div>
          <span class="score-pill">${num(board.sector_trend_score, 0)}</span>
        </div>
        <div class="kline-block">
          <div class="kline-head"><strong>板块${state.boardWindow}日K线</strong><span>近5日显著信号 ${chart.markers ? chart.markers.length : 0}</span></div>
          ${renderKlineChart(chart, `${boardLabel(board.board_path)} 板块${state.boardWindow}日K线`, state.boardWindow)}
        </div>
        ${renderAiResult(key, "板块AI分析")}
      </div>
      <div class="board-detail-card">
        <div class="kline-head"><strong>成分股</strong><span>${constituents.length} 只</span></div>
        <div class="constituent-list">
          ${constituents.map((stock) => `
            <div class="constituent-row">
              <span>#${escapeHtml(stock.rank || "--")}</span>
              <strong>${escapeHtml(stock.name)} <span>${escapeHtml(stock.code)}</span></strong>
              <span>${stock.combined_score == null ? "--" : num(stock.combined_score, 0)}</span>
            </div>
          `).join("")}
        </div>
      </div>
    `;
    attachAiButton($("boardDetail"), "board", board.board_path, () => boardAiContext(board, chart), renderBoardDetail);
  }

  function renderSignalTable() {
    const allRows = filteredSignals();
    const rows = allRows.slice(0, 42);
    const totalRows = allRows.length;
    $("signalResultCount").textContent = `当前 ${rows.length}/${totalRows}`;
    if (!rows.length) {
      $("signalTable").innerHTML = `<div class="empty">当前板块暂无信号</div>`;
      return;
    }
    $("signalTable").innerHTML = rows
      .map((row) => {
        const strength = signalStrength(row);
        const directionClass = strength.key === "strong" ? "bullish" : strength.key === "weak" ? "bearish" : "neutral";
        return `
          <div class="signal-row">
            <span class="source ${sourceClass(row.source_project)}">${escapeHtml(sourceName(row.source_project))}</span>
            <strong>${escapeHtml(row.name)}</strong>
            <span><span class="signal-name-line"><span class="signal-name">${escapeHtml(signalDisplayName(row.signal_name))}</span><button class="signal-help" type="button" data-signal-query="${escapeHtml(signalCatalogQuery(row.signal_name))}" title="查看含义和计算方式" aria-label="查看${escapeHtml(signalDisplayName(row.signal_name))}的含义和计算方式">?</button></span><br><span class="evidence">${escapeHtml(brandText(row.evidence))}</span></span>
            <span class="signal-score">${escapeHtml(signalScoreText(row))}</span>
            <span class="direction ${directionClass}">${escapeHtml(strength.label)}</span>
          </div>
        `;
      })
      .join("");
    bindSignalStationLinks($("signalTable"));
  }

  function renderReview() {
    const review = data.review || {};
    const metrics = [
      ["重分类样本", review.rows_detail || "--"],
      ["科技样本", review.tech_rows || "--"],
      ["入选股票", review.selected_stocks || "--"],
      ["历史覆盖", `${review.history_ok || 0}/${review.history_total || 0}`],
      ["缺失历史", review.history_missing || 0],
      ["统一信号", review.unified_signal_rows || "--"],
      ["曲线板块", `${review.curve_boards || 0}/${review.selected_boards || 0}`],
      ["因子目录", (factorCatalog.stats || {}).total || "--"],
    ];
    $("reviewHealth").textContent = `${review.history_ok || 0}/${review.history_total || 0}`;
    $("reviewMetrics").innerHTML = metrics
      .map(([label, value]) => `<div class="review-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
      .join("");

    const issues = review.known_issues || [];
    const notes = [
      "科技 taxonomy 已能区分 PCB、光模块/CPO、液冷温控、算力服务器等细分方向。",
      "LumenAlpha 与东方财富人气已统一到同一张信号表，并保留来源标记。",
      ...issues,
    ];
    $("reviewFindings").innerHTML = notes.map((note) => `<div class="review-item">${escapeHtml(brandText(note))}</div>`).join("");

    const boards = [...(data.boards || [])]
      .filter(isClassifiedBoard)
      .sort((a, b) => Number(b.sector_trend_score || -1) - Number(a.sector_trend_score || -1))
      .slice(0, 18);
    $("reviewBoards").innerHTML = boards
      .map((board, index) => `
        <div class="review-board" style="${styleVars(board.board_path)}">
          <span class="rank-mini">${index + 1}</span>
          <div>
            <strong>${escapeHtml(boardLabel(board.board_path))}</strong>
            <span>${escapeHtml(boardSubLabel(board.board_path))}  |  样本 ${board.curve_member_count || 0}/${board.stock_count || 0}</span>
          </div>
          <div class="review-board-score">${num(board.sector_trend_score, 0)}</div>
        </div>
      `)
      .join("");
  }

  function renderAuth() {
    const user = state.authUser;
    const label = $("authButtonLabel");
    const button = $("authButton");
    if (!label || !button) return;
    label.textContent = user ? user.username : "登录";
    button.classList.toggle("signed-in", Boolean(user));
    button.classList.toggle("https-required", state.authReady && !state.authAvailable);
    button.setAttribute("aria-haspopup", user ? "menu" : "dialog");
    button.setAttribute("aria-expanded", user && !$("accountMenu").hidden ? "true" : "false");
    button.querySelector(".auth-avatar").textContent = user ? user.username.slice(0, 1).toUpperCase() : "人";
    $("accountUsername").textContent = user?.username || "--";
    if (!user) $("accountMenu").hidden = true;
    $("authSecurityNotice").hidden = !state.authReady || state.authAvailable;
    $("authForm").querySelectorAll("input, button").forEach((control) => {
      control.disabled = !state.authReady || !state.authAvailable || state.authSubmitting;
    });
    $("authSubmit").textContent = state.authSubmitting ? "处理中..." : state.authMode === "register" ? "创建账号" : "登录";
  }

  function setAuthMode(mode) {
    state.authMode = mode === "register" ? "register" : "login";
    $("authTitle").textContent = state.authMode === "register" ? "注册 LumenAlpha" : "登录 LumenAlpha";
    document.querySelectorAll(".auth-tab").forEach((button) => {
      const active = button.dataset.authMode === state.authMode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    const confirmField = $("confirmPasswordField");
    confirmField.hidden = state.authMode !== "register";
    $("authPasswordConfirm").required = state.authMode === "register";
    $("authPassword").autocomplete = state.authMode === "register" ? "new-password" : "current-password";
    $("authError").hidden = true;
    renderAuth();
  }

  function openAuthDialog(mode = "login") {
    setAuthMode(mode);
    $("accountMenu").hidden = true;
    const dialog = $("authDialog");
    if (!dialog.open) dialog.showModal();
    if (state.authAvailable) requestAnimationFrame(() => $("authUsername").focus());
  }

  function refreshAccountViews() {
    renderAuth();
    renderWatchCount();
    if (state.view === "dashboard") {
      renderLeaderLadder();
      renderLeaderDetail();
    }
    if (state.view === "watchlist") renderWatchlist();
  }

  async function syncAccountWatchlist() {
    if (!state.authUser) return;
    const remote = await apiRequest("/api/watchlist");
    const remoteCodes = new Set((remote.codes || []).map(normalizeCode).filter(Boolean));
    const guestCodes = readGuestWatchlist();
    for (const code of guestCodes) {
      if (remoteCodes.has(code)) continue;
      const synced = await apiRequest("/api/watchlist", { method: "POST", body: { code } });
      (synced.codes || []).forEach((item) => remoteCodes.add(normalizeCode(item)));
    }
    clearGuestWatchlist();
    state.watchlist = [...remoteCodes].filter(Boolean);
  }

  async function loadAuthState() {
    try {
      const payload = await apiRequest("/api/auth/me");
      state.authUser = payload.user || null;
      state.authAvailable = payload.authAvailable !== false;
      if (state.authUser) await syncAccountWatchlist();
      else state.watchlist = readGuestWatchlist();
    } catch (_error) {
      state.authUser = null;
      state.authAvailable = false;
      state.watchlist = readGuestWatchlist();
    } finally {
      state.authReady = true;
      refreshAccountViews();
    }
  }

  async function submitAuthForm(event) {
    event.preventDefault();
    if (!state.authAvailable || state.authSubmitting) return;
    const username = $("authUsername").value.trim();
    const password = $("authPassword").value;
    const confirm = $("authPasswordConfirm").value;
    const error = $("authError");
    if (state.authMode === "register" && password !== confirm) {
      error.textContent = "两次输入的密码不一致";
      error.hidden = false;
      return;
    }
    state.authSubmitting = true;
    error.hidden = true;
    $("authForm").setAttribute("aria-busy", "true");
    renderAuth();
    try {
      const payload = await apiRequest(`/api/auth/${state.authMode}`, { method: "POST", body: { username, password } });
      state.authUser = payload.user;
      await syncAccountWatchlist();
      $("authDialog").close();
      $("authForm").reset();
      refreshAccountViews();
    } catch (authError) {
      error.textContent = authError.message;
      error.hidden = false;
    } finally {
      state.authSubmitting = false;
      $("authForm").setAttribute("aria-busy", "false");
      renderAuth();
    }
  }

  async function logoutAccount() {
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
    } catch (_error) {
      // The local account state still needs to be cleared if the session expired.
    }
    state.authUser = null;
    state.watchlist = readGuestWatchlist();
    $("accountMenu").hidden = true;
    refreshAccountViews();
  }

  function bindAuth() {
    $("authButton")?.addEventListener("click", () => {
      if (state.authUser) {
        $("accountMenu").hidden = !$("accountMenu").hidden;
        renderAuth();
      } else {
        openAuthDialog("login");
      }
    });
    $("logoutButton")?.addEventListener("click", logoutAccount);
    $("authClose")?.addEventListener("click", () => $("authDialog").close());
    $("authDialog")?.addEventListener("cancel", () => $("authDialog").close());
    document.querySelectorAll(".auth-tab").forEach((button) => button.addEventListener("click", () => setAuthMode(button.dataset.authMode)));
    $("authForm")?.addEventListener("submit", submitAuthForm);
    $("passwordToggle")?.addEventListener("click", () => {
      const password = $("authPassword");
      const showing = password.type === "text";
      password.type = showing ? "password" : "text";
      $("passwordToggle").textContent = showing ? "显示" : "隐藏";
      $("passwordToggle").setAttribute("aria-label", showing ? "显示密码" : "隐藏密码");
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".auth-control")) {
        $("accountMenu").hidden = true;
        renderAuth();
      }
    });
  }

  function renderWatchCount() {
    const count = state.watchlist.length;
    if ($("watchCount")) $("watchCount").textContent = count;
    if ($("watchlistStatus")) $("watchlistStatus").textContent = `${count} 只`;
  }

  function renderWatchlist() {
    renderWatchCount();
    const hint = $("watchlistHint");
    if (state.authUser) {
      hint.textContent = `已登录为 ${state.authUser.username}，自选会自动跨设备同步`;
    } else {
      hint.innerHTML = `访客数据仅保存在当前浏览器 <button type="button" data-watchlist-login>登录同步</button>`;
      hint.querySelector("[data-watchlist-login]")?.addEventListener("click", () => openAuthDialog("login"));
    }
    const watched = state.watchlist
      .map((code) => (data.leaders || []).find((leader) => normalizeCode(leader.code) === code))
      .filter(Boolean);
    if (!watched.length) {
      $("watchlistContent").innerHTML = `<div class="watchlist-empty"><strong>还没有自选股票</strong><p>在龙头观察或个股拆解中点击星标，就会出现在这里。</p><button type="button" data-go-leaders>去看龙头</button>${state.authUser ? "" : `<button class="secondary" type="button" data-empty-login>登录账号</button>`}</div>`;
      $("watchlistContent").querySelector("[data-go-leaders]")?.addEventListener("click", () => {
        state.view = "dashboard";
        state.section = "leadersSection";
        state.mode = "overview";
        state.activeDashboardNav = "龙头观察";
        renderViews();
      });
      $("watchlistContent").querySelector("[data-empty-login]")?.addEventListener("click", () => openAuthDialog("login"));
      return;
    }
    $("watchlistContent").innerHTML = `<div class="leader-table-head"><span>#</span><span>股票</span><span>板块</span><span>综合</span><span>5日</span><span>趋势</span><span>18日K线</span><span></span></div>${watched.map(leaderCard).join("")}`;
    $("watchlistContent").querySelectorAll(".leader-row").forEach((row) => {
      row.addEventListener("click", (event) => {
        if (event.target.closest(".watch-toggle")) return;
        state.leaderCode = row.dataset.code;
        state.view = "dashboard";
        state.section = "leadersSection";
        state.mode = "overview";
        state.activeDashboardNav = "龙头观察";
        renderDashboard();
        renderViews();
      });
    });
    $("watchlistContent").querySelectorAll(".watch-toggle").forEach((button) => {
      button.addEventListener("click", () => {
        toggleWatch(button.dataset.watch);
        renderWatchlist();
      });
    });
  }

  function renderMerge() {
    const flow = [
      ["LumenAlpha", "统一因子与技术信号", "Alpha158 / Alpha360 / 表达式因子 / 技术形态"],
      ["Taxonomy", "科技板块分层", "一级科技 + 二级主线 + 三级细分板块"],
      ["Signal Table", "统一信号表", "source_project / signal_name / score / evidence"],
      ["Dashboard", "轮动工作台", "龙头显著信号 + 板块K线 + 因子解释"],
    ];
    $("mergeFlow").innerHTML = flow
      .map(([title, subtitle, body], index) => `
        <div class="merge-step">
          <span>${index + 1}</span>
          <strong>${escapeHtml(title)}</strong>
          <em>${escapeHtml(subtitle)}</em>
          <p>${escapeHtml(body)}</p>
        </div>
      `)
      .join("");

    const schema = [
      ["date", "信号日期"],
      ["code / name", "股票代码与名称"],
      ["board_l1/l2/l3", "板块层级"],
      ["source_project", "LumenAlpha / Eastmoney"],
      ["source_module", "来源模块"],
      ["signal_name", "信号名称"],
      ["signal_score", "统一分值"],
      ["evidence", "解释证据"],
    ];
    $("mergeSchema").innerHTML = schema
      .map(([field, meaning]) => `<div class="schema-item"><strong>${escapeHtml(field)}</strong><span>${escapeHtml(meaning)}</span></div>`)
      .join("");
  }

  function tableCells(line) {
    return line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());
  }

  function isTableSeparator(line) {
    return /^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line.trim());
  }

  function renderMarkdownLite(markdown) {
    const lines = brandText(markdown).split(/\r?\n/);
    const html = [];
    let list = [];

    function flushList() {
      if (!list.length) return;
      html.push(`<ul>${list.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
      list = [];
    }

    for (let index = 0; index < lines.length; index += 1) {
      const raw = lines[index];
      const line = raw.trim();
      if (!line) {
        flushList();
        continue;
      }
      if (line.startsWith("|")) {
        flushList();
        const tableLines = [];
        while (index < lines.length && lines[index].trim().startsWith("|")) {
          tableLines.push(lines[index].trim());
          index += 1;
        }
        index -= 1;
        const rows = tableLines.filter((row) => !isTableSeparator(row)).map(tableCells);
        if (rows.length) {
          const [head, ...body] = rows;
          html.push(`
            <div class="report-table-wrap">
              <table class="report-table">
                <thead><tr>${head.map((cell) => `<th>${escapeHtml(cell)}</th>`).join("")}</tr></thead>
                <tbody>${body.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody>
              </table>
            </div>
          `);
        }
        continue;
      }
      if (line.startsWith("# ")) {
        flushList();
        html.push(`<h2>${escapeHtml(line.slice(2))}</h2>`);
        continue;
      }
      if (line.startsWith("## ")) {
        flushList();
        html.push(`<h3>${escapeHtml(line.slice(3))}</h3>`);
        continue;
      }
      if (line.startsWith("- ")) {
        list.push(line.slice(2));
        continue;
      }
      flushList();
      html.push(`<p>${escapeHtml(line)}</p>`);
    }
    flushList();
    return html.join("");
  }

  function renderDailyAnalysis() {
    const status = $("analysisStatus");
    const target = $("dailyAnalysis");
    if (!status || !target) return;
    status.textContent = state.dailyReportStatus;
    if (!state.dailyReportText) {
      target.innerHTML = `<div class="empty">日报还没有生成，运行 daily refresh 后会显示在这里。</div>`;
      return;
    }
    const key = aiKey("daily", "latest");
    const boards = [...(data.boards || [])]
      .filter(isClassifiedBoard)
      .sort((a, b) => Number(b.sector_trend_score || -1) - Number(a.sector_trend_score || -1));
    const leaders = filteredLeaders().slice(0, 5);
    const strong = boards.slice(0, 3);
    const weak = [...boards].sort((a, b) => Number(a.sector_trend_score || 999) - Number(b.sector_trend_score || 999)).slice(0, 3);
    const review = data.review || {};
    target.innerHTML = `
      ${renderAiResult(key, "日报AI分析")}
      <div class="daily-summary-grid">
        <section class="daily-block primary"><span>一句话结论</span><strong>${escapeHtml(strong.length ? `${boardLabel(strong[0].board_path)}领涨，主线集中在${strong.map((board) => boardLabel(board.board_path)).join("、")}` : "当前没有足够数据形成明确主线")}</strong><p>先观察板块强度是否延续，再结合个股量价确认。</p></section>
        <section class="daily-block"><span>机会方向</span>${strong.map((board, index) => `<div class="daily-row"><em>${index + 1}</em><strong>${escapeHtml(boardLabel(board.board_path))}</strong><b>${num(board.sector_trend_score, 0)}</b></div>`).join("")}</section>
        <section class="daily-block risk"><span>降温与风险</span>${weak.map((board) => `<div class="daily-row"><strong>${escapeHtml(boardLabel(board.board_path))}</strong><b>强度 ${num(board.sector_trend_score, 0)}</b></div>`).join("")}</section>
        <section class="daily-block"><span>重点观察</span>${leaders.map((leader) => `<button class="daily-leader" type="button" data-daily-code="${escapeHtml(leader.code)}"><strong>${escapeHtml(leader.name)}</strong><em>${escapeHtml(boardLabel(leader.board_path))}</em><b>${num(leader.combined_score, 1)}</b></button>`).join("")}</section>
      </div>
      <div class="daily-health"><span>历史覆盖 ${escapeHtml(review.history_ok || 0)}/${escapeHtml(review.history_total || 0)}</span><span>统一信号 ${escapeHtml(review.unified_signal_rows || 0)} 条</span><span>缺失 ${escapeHtml(review.history_missing || 0)} 只</span></div>
      <details class="report-details"><summary>查看完整量化数据报告</summary><div class="markdown-report">${renderMarkdownLite(state.dailyReportText)}</div></details>
    `;
    target.querySelectorAll("[data-daily-code]").forEach((button) => {
      button.addEventListener("click", () => {
        state.leaderCode = button.dataset.dailyCode;
        state.view = "dashboard";
        state.section = "leadersSection";
        state.mode = "overview";
        state.activeDashboardNav = "龙头观察";
        renderDashboard();
        renderViews();
      });
    });
    attachAiButton(target, "daily", "latest", dailyAiContext, renderDailyAnalysis);
  }

  function loadDailyAnalysis() {
    if (state.dailyReportLoading || state.dailyReportText || state.dailyReportStatus === "读取失败") return;
    state.dailyReportLoading = true;
    fetch("daily_analysis.md", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.text();
      })
      .then((text) => {
        state.dailyReportText = text;
        const generated = text.match(/Generated:\s*([^\n]+)/);
        state.dailyReportStatus = generated ? generated[1].trim() : "已生成";
        renderDailyAnalysis();
      })
      .catch(() => {
        state.dailyReportStatus = "读取失败";
        renderDailyAnalysis();
      })
      .finally(() => {
        state.dailyReportLoading = false;
      });
  }

  function factorItems() {
    let items = factorCatalog.items || [];
    if (state.factorProject !== "all") {
      items = items.filter((item) => projectLabel(item.project) === state.factorProject);
    }
    if (state.factorFamily !== "all") {
      items = items.filter((item) => factorGroup(item) === state.factorFamily);
    }
    const keyword = state.factorSearch.trim().toLowerCase();
    if (keyword) {
      items = items.filter((item) => {
        const text = [
          item.project,
          item.family,
          item.name,
          item.category,
          item.meaning,
          item.formula,
          item.parameters,
          item.direction,
          item.source_file,
          item.notes,
        ].join(" ").toLowerCase();
        return text.includes(keyword);
      });
      items.sort((a, b) => {
        const aExact = String(a.name || "").toLowerCase() === keyword ? 1 : 0;
        const bExact = String(b.name || "").toLowerCase() === keyword ? 1 : 0;
        return bExact - aExact;
      });
    }
    return items;
  }

  function factorGroup(item) {
    const formula = item.project === "qlib" ? item.formula : "";
    const text = [item.name, item.category, item.meaning, formula, item.family].join(" ").toLowerCase();
    if (/k线|形态|反包|影线|十字星|实体|偏移|支撑|背离|反转/.test(text)) return "K线形态";
    if (/波动|风险|std|振幅|回撤|volatility/.test(text)) return "波动风险";
    if (/趋势|均线|ma|slope|beta|突破|多头|空头/.test(text)) return "趋势";
    if (/动量|momentum|roc|涨跌|收益/.test(text)) return "动量";
    if (/量|volume|资金|成交|换手/.test(text)) return "成交量";
    if (/热度|人气|排名|rank|关注/.test(text)) return "市场热度";
    return "其他";
  }

  function driverState(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return { label: "数据不足", tone: "neutral", note: "当前样本不足，暂不参与判断。" };
    if (n >= 70) return { label: "偏强", tone: "bullish", note: "在当前样本中处于较强区间。" };
    if (n >= 45) return { label: "中性", tone: "neutral", note: "没有形成明显优势或风险。" };
    return { label: "偏弱", tone: "bearish", note: "该维度落后于多数样本，需要谨慎。" };
  }

  function renderFactorMetrics() {
    const stats = factorCatalog.stats || {};
    const leader = (data.leaders || []).find((item) => item.code === state.leaderCode) || filteredLeaders()[0] || (data.leaders || [])[0];
    const chart = leader ? (data.stockCharts || {})[normalizeCode(leader.code)] || { candles: [] } : { candles: [] };
    const drivers = leader ? [
      ["趋势", leader.qlib_ma20_bias_rank, "股价相对20日均线的位置"],
      ["动量", (Number(leader.qlib_mom_5_rank || 0) + Number(leader.qlib_mom_20_rank || 0)) / 2, "近期涨幅在样本中的强弱"],
      ["成交量", leader.qlib_volume_rank, "当前量能相对近20日是否活跃"],
      ["波动风险", leader.qlib_volatility_rank, "波动越可控，分数越高"],
      ["市场热度", leader.popularity_score, "东方财富人气排名转化的热度"],
    ] : [];
    const formulaCount = Number(stats.formulaCount || 0);
    const formulaTotal = Number(stats.total || 0);
    const unimplemented = Number(stats.unimplementedCount || 0);
    $("factorGeneratedAt").textContent = `${factorCatalog.generatedAt || "--"} · 计算说明 ${formulaCount}/${formulaTotal}${unimplemented ? ` · ${unimplemented} 项待实现` : ""}`;
    $("factorTotal").textContent = `当前 ${factorItems().length}/${stats.total || 0}`;
    $("factorInsights").innerHTML = leader ? `
      <div class="factor-stock-summary">
        <div><span>当前解释对象</span><h3>${escapeHtml(leader.name)} <small>${escapeHtml(normalizeCode(leader.code))}</small></h3><p>${escapeHtml(boardLabel(leader.board_path))} · 综合分 ${num(leader.combined_score, 1)}</p></div>
        <div class="factor-stock-kline">${renderMiniKline(chart, `${leader.name} 因子解释K线`)}</div>
      </div>
      <div class="driver-list">${drivers.map(([label, value, meaning]) => {
        const status = driverState(value);
        return `<div class="driver-row"><div><strong>${escapeHtml(label)}</strong><span>${escapeHtml(meaning)}</span></div><div class="driver-bar"><i style="--w:${clamp(value)}%"></i></div><b>${num(value, 0)}</b><em class="${status.tone}">${status.label}</em><p>${escapeHtml(status.note)}</p></div>`;
      }).join("")}</div>
    ` : `<div class="empty">暂无可解释股票</div>`;
  }

  function renderFactorTabs() {
    const projectLabels = [...new Set((factorCatalog.items || []).map((item) => projectLabel(item.project)))];
    const projects = projectLabels.length > 1 ? ["all", ...projectLabels] : projectLabels;
    if (!projects.includes(state.factorProject)) state.factorProject = projects[0] || "all";
    $("factorProjectTabs").innerHTML = projects
      .map((project) => {
        const active = state.factorProject === project ? " active" : "";
        const label = project === "all" ? "全部来源" : project;
        return `<button class="factor-tab${active}" type="button" data-project="${escapeHtml(project)}">${escapeHtml(label)}</button>`;
      })
      .join("");
    $("factorProjectTabs").querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        state.factorProject = button.dataset.project || "all";
        state.factorFamily = "all";
        state.factorLimit = 24;
        renderFactors();
      });
    });

    const familyBase = state.factorProject === "all" ? factorCatalog.items || [] : (factorCatalog.items || []).filter((item) => projectLabel(item.project) === state.factorProject);
    const order = ["趋势", "动量", "成交量", "波动风险", "K线形态", "市场热度", "其他"];
    const available = new Set(familyBase.map(factorGroup));
    const families = ["all", ...order.filter((item) => available.has(item))];
    $("factorFamilyTabs").innerHTML = families
      .map((family) => {
        const active = state.factorFamily === family ? " active" : "";
        const label = family === "all" ? "全部主题" : family;
        return `<button class="factor-tab${active}" type="button" data-family="${escapeHtml(family)}">${escapeHtml(label)}</button>`;
      })
      .join("");
    $("factorFamilyTabs").querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        state.factorFamily = button.dataset.family || "all";
        state.factorLimit = 24;
        renderFactors();
      });
    });
  }

  function renderFactorNotes() {
    $("factorNotes").innerHTML = `<div class="factor-note"><strong>公式标记：</strong>t 为最新交易日，t-1 为前一交易日，Valid 表示数据非空；计算条件来自当前源码，不构成操作建议。</div>`;
  }

  function factorRow(item) {
    const score = item.score === "" || item.score === null || item.score === undefined ? "--" : item.score;
    const params = brandText(item.parameters ? `参数 ${item.parameters}` : "无额外参数");
    const formula = brandText(item.formula || "未提供计算说明").replaceAll(" AND ", "\nAND ").replaceAll("；", "；\n");
    const isUnimplemented = String(item.formula || "").startsWith("当前源码未实现");
    const status = isUnimplemented ? "待实现" : Number(score) > 0 ? "偏多" : Number(score) < 0 ? "偏空" : "解释项";
    const methodNote = item.notes ? `<p class="factor-method-note">${escapeHtml(brandText(item.notes))}</p>` : "";
    return `
      <div class="factor-row">
        <div class="factor-name">
          <strong>${escapeHtml(brandText(item.name))}</strong>
          <span>${escapeHtml(factorGroup(item))} · ${escapeHtml(projectLabel(item.project))}</span>
        </div>
        <div class="factor-meaning"><span>它代表什么</span><p>${escapeHtml(brandText(item.meaning || "暂无通俗解释"))}</p></div>
        <span class="factor-status${isUnimplemented ? " pending" : ""}">${escapeHtml(status)}</span>
        <details class="factor-method${isUnimplemented ? " is-unimplemented" : ""}"><summary>查看计算方法</summary><div><span class="factor-method-label">触发条件</span><code>${escapeHtml(formula)}</code><p>${escapeHtml(params)} · 来源 ${escapeHtml(factorSourceLabel(item))}</p>${methodNote}</div></details>
      </div>
    `;
  }

  function renderFactorCatalog() {
    const items = factorItems();
    $("factorTotal").textContent = `当前 ${items.length}/${(factorCatalog.stats || {}).total || 0}`;
    if (!items.length) {
      $("factorCatalog").innerHTML = `<div class="empty">没有匹配的因子或信号</div>`;
      return;
    }
    const visible = items.slice(0, state.factorLimit);
    $("factorTotal").textContent = `匹配 ${items.length} · 显示 ${visible.length}`;
    $("factorCatalog").innerHTML = `${visible.map(factorRow).join("")}${visible.length < items.length ? `<button id="factorMore" class="load-more" type="button">再显示 ${Math.min(24, items.length - visible.length)} 条</button>` : ""}`;
    $("factorMore")?.addEventListener("click", () => {
      state.factorLimit += 24;
      renderFactorCatalog();
    });
  }

  function renderFactors() {
    renderFactorMetrics();
    renderFactorTabs();
    renderFactorNotes();
    renderFactorCatalog();
  }

  function renderViews() {
    document.body.classList.toggle("stock-view-active", state.view === "stock");
    const stockResearchNav = $("stockResearchNav");
    if (stockResearchNav) stockResearchNav.hidden = !state.leaderCode;
    const pageTitle = $("pageTitle");
    if (pageTitle) pageTitle.textContent = state.view === "stock" ? "个股研究" : "股票板块轮动";
    document.querySelectorAll(".view").forEach((view) => {
      view.classList.toggle("active", view.id === `${state.view}View`);
    });
    const dashboard = $("dashboardView");
    if (dashboard) dashboard.dataset.section = state.section || "overviewSection";
    document.querySelectorAll(".nav-item, .mobile-nav-item, .mobile-menu-item").forEach((item) => {
      const view = item.dataset.view || "dashboard";
      const section = item.dataset.section || "";
      const active = state.view === "dashboard"
        ? view === "dashboard" && section === state.section
        : view === state.view && !section;
      item.classList.toggle("active", active);
    });
    syncModeButtons();
    if (state.view === "dashboard" && state.section) {
      requestAnimationFrame(() => {
        const target = $(state.section);
        if (target) target.scrollIntoView({ behavior: "auto", block: "start" });
      });
    } else {
      requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "instant" }));
    }
  }

  function bindNav() {
    document.querySelectorAll(".nav-item, .mobile-nav-item, .mobile-menu-item").forEach((button) => {
      if (!button.dataset.view) return;
      button.addEventListener("click", () => {
        state.view = button.dataset.view || "dashboard";
        if (state.view === "dashboard") {
          state.section = button.dataset.section || "overviewSection";
          state.activeDashboardNav = button.textContent.trim();
          state.mode = sectionModes[state.section] || "overview";
        }
        if ($("mobileMoreMenu")) $("mobileMoreMenu").hidden = true;
        renderViews();
        renderCurrentViewData();
      });
    });
  }

  function bindModes() {
    document.querySelectorAll(".mode").forEach((button) => {
      button.addEventListener("click", () => {
        state.mode = button.dataset.mode || "overview";
        const target = modeSections[state.mode] || modeSections.overview;
        state.view = "dashboard";
        state.section = target.section;
        state.activeDashboardNav = target.nav;
        renderViews();
      });
    });
  }

  function bindFactorSearch() {
    const input = $("factorSearch");
    if (!input) return;
    input.addEventListener("input", () => {
      state.factorSearch = input.value || "";
      state.factorLimit = 24;
      renderFactorMetrics();
      renderFactorCatalog();
    });
  }

  function bindSignalSearch() {
    const input = $("signalSearch");
    if (!input) return;
    input.addEventListener("input", () => {
      state.signalSearch = input.value || "";
      renderSignalTable();
    });
  }

  function bindBoardWindows() {
    const controls = $("boardWindowControls");
    if (!controls) return;
    controls.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        state.boardWindow = Number(button.dataset.window || 10);
        controls.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
        renderSectorTrends();
      });
    });
  }

  function bindGlobalSearch() {
    const input = $("globalSearch");
    const results = $("globalSearchResults");
    if (!input || !results) return;
    input.addEventListener("input", () => {
      const keyword = input.value.trim().toLowerCase();
      state.globalSearch = keyword;
      if (!keyword) {
        results.hidden = true;
        results.innerHTML = "";
        return;
      }
      const matches = (data.leaders || []).filter((leader) => [leader.name, leader.code, leader.board_path].join(" ").toLowerCase().includes(keyword)).slice(0, 8);
      results.hidden = false;
      results.innerHTML = matches.length ? matches.map((leader) => `<button type="button" data-search-code="${escapeHtml(leader.code)}"><span><strong>${escapeHtml(leader.name)}</strong><small>${escapeHtml(normalizeCode(leader.code))} · ${escapeHtml(boardLabel(leader.board_path))}</small></span><b>${num(leader.combined_score, 1)}</b></button>`).join("") : `<div class="search-empty">没有找到匹配股票</div>`;
      results.querySelectorAll("[data-search-code]").forEach((button) => {
        button.addEventListener("click", () => {
          state.leaderCode = button.dataset.searchCode;
          state.view = "dashboard";
          state.section = "leadersSection";
          state.mode = "overview";
          state.activeDashboardNav = "龙头观察";
          input.value = "";
          results.hidden = true;
          renderDashboard();
          renderViews();
        });
      });
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".global-search-wrap")) results.hidden = true;
    });
  }

  function bindShellControls() {
    $("sidebarToggle")?.addEventListener("click", () => {
      document.body.classList.toggle("sidebar-collapsed");
    });
    $("mobileMore")?.addEventListener("click", () => {
      const menu = $("mobileMoreMenu");
      menu.hidden = !menu.hidden;
    });
  }

  function render() {
    renderDashboard();
    renderViews();
    renderCurrentViewData();
  }

  function renderDashboard() {
    renderGeneratedAt();
    renderMarketBrief();
    renderMetrics();
    renderBoardChips();
    renderLeaderLadder();
    renderLeaderDetail();
    renderSectorTrends();
    renderSignalTable();
    renderWatchCount();
  }

  function renderCurrentViewData() {
    if (state.view === "analysis") {
      renderDailyAnalysis();
      loadDailyAnalysis();
    } else if (state.view === "factor") {
      renderFactors();
    } else if (state.view === "review") {
      renderReview();
    } else if (state.view === "watchlist") {
      renderWatchlist();
    } else if (state.view === "stock") {
      renderStockPage();
    }
  }

  bindNav();
  bindModes();
  bindFactorSearch();
  bindSignalSearch();
  bindBoardWindows();
  bindGlobalSearch();
  bindShellControls();
  bindAuth();
  renderAuth();
  render();
  loadAuthState();
})();
