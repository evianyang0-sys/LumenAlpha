(function () {
  const data = window.SECTOR_DASHBOARD_DATA || {};
  const factorCatalog = window.FACTOR_CATALOG || { items: [], stats: {}, notes: [] };
  const state = {
    board: "all",
    leaderCode: null,
    mode: "day",
    view: "dashboard",
    section: "leadersSection",
    activeDashboardNav: "龙头天梯",
    signalSearch: "",
    boardWindow: 10,
    selectedBoard: null,
    factorProject: "all",
    factorFamily: "all",
    factorSearch: "",
    dailyReportText: "",
    dailyReportStatus: "读取中",
    dailyReportLoading: false,
    aiAnalyses: {},
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
    return source || "--";
  }

  function projectLabel(project) {
    if (project === "qlib") return "qlib";
    if (project === "LumenAlpha") return "LumenAlpha";
    return project || "--";
  }

  function aiKey(type, id) {
    return `${type}:${id || "latest"}`;
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
    return `<ul>${rows.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
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
    return `
      <div class="ai-card">
        <div class="ai-card-head">
          <div>
            <strong>${escapeHtml(title)}</strong>
            <span>${item.cached ? "缓存结果" : "实时结果"}  |  ${escapeHtml(item.model || "DeepSeek")}</span>
          </div>
          <button class="ai-button subtle" type="button" data-ai-key="${escapeHtml(key)}" data-refresh="1">刷新</button>
        </div>
        <p class="ai-summary">${escapeHtml(analysis.summary || "--")}</p>
        <div class="ai-grid">
          <div><span>看多依据</span>${aiList(analysis.bullish_points)}</div>
          <div><span>风险点</span>${aiList(analysis.risk_points)}</div>
          <div><span>信号分歧</span>${aiList(analysis.signal_conflicts)}</div>
          <div><span>观察计划</span>${aiList(analysis.next_day_plan)}</div>
        </div>
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
      .sort((a, b) => Number(b.sector_trend_score || -1) - Number(a.sector_trend_score || -1))
      .slice(0, 12)
      .map(compactBoard);
    const leaders = [...(data.leaders || [])]
      .sort((a, b) => Number(b.combined_score || -1) - Number(a.combined_score || -1))
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
    return state.board === "all" ? leaders : leaders.filter((item) => item.board_path === state.board);
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
    $("generatedAt").textContent = `${data.generatedAt || "--"}  |  历史覆盖 ${review.history_ok || 0}/${review.history_total || 0}`;
  }

  function renderMetrics() {
    const review = data.review || {};
    const sourceCount = (data.signals || []).reduce((acc, row) => {
      acc[row.source_project] = (acc[row.source_project] || 0) + 1;
      return acc;
    }, {});
    const topBoard = [...(data.boards || [])]
      .filter((board) => Number.isFinite(Number(board.sector_trend_score)))
      .sort((a, b) => Number(b.sector_trend_score) - Number(a.sector_trend_score))[0];
    const items = [
      ["科技样本", review.tech_rows || "--"],
      ["入选股票", review.selected_stocks || "--"],
      ["统一信号", review.unified_signal_rows || "--"],
      ["曲线板块", `${review.curve_boards || 0}/${review.selected_boards || 0}`],
      ["qlib 信号", sourceCount.qlib || 0],
      ["最强板块", boardLabel(topBoard && topBoard.board_path)],
    ];
    $("metrics").innerHTML = items
      .map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
      .join("");
  }

  function renderBoardChips() {
    const boards = [...(data.boards || [])].sort((a, b) => {
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
        const leaders = filteredLeaders();
        state.leaderCode = leaders[0] && leaders[0].code;
        render();
      });
    });
  }

  function signalBadges(text) {
    const parts = String(text || "")
      .split("|")
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, 4);
    if (!parts.length) return `<span class="signal-badge">暂无显著信号</span>`;
    return parts.map((part) => `<span class="signal-badge">${escapeHtml(part)}</span>`).join("");
  }

  function leaderCard(leader) {
    const active = state.leaderCode === leader.code ? " active" : "";
    const board = boardLabel(leader.board_path);
    return `
      <button class="leader-card${active}" type="button" data-code="${escapeHtml(leader.code)}" style="${styleVars(leader.board_path)}">
        <div class="leader-top"><span>#${escapeHtml(leader.rank)}</span><span>${num(leader.combined_score, 1)}</span></div>
        <h3>${escapeHtml(leader.name)}</h3>
        <div class="board-tag">${escapeHtml(board)}</div>
        <div class="leader-scores">
          <span>Q ${num(leader.qlib_factor_score, 0)}</span>
          <span>L ${num(leader.lumen_score_norm, 0)}</span>
          <span>板 ${num(leader.sector_trend_score, 0)}</span>
        </div>
      </button>
    `;
  }

  function renderLeaderLadder() {
    const leaders = filteredLeaders();
    const title = state.board === "all" ? "显著信号优先" : `${boardLabel(state.board)}  |  ${leaders.length} 只`;
    $("leaderSubhead").textContent = title;
    if (!leaders.length) {
      $("leaderLadder").innerHTML = `<div class="empty">当前板块暂无龙头样本</div>`;
      return;
    }
    if (!state.leaderCode || !leaders.some((leader) => leader.code === state.leaderCode)) {
      state.leaderCode = leaders[0].code;
    }
    const tiers = [
      { label: "强信号", min: 80, rows: leaders.filter((item) => Number(item.combined_score) >= 80).slice(0, 14) },
      { label: "共振", min: 70, rows: leaders.filter((item) => Number(item.combined_score) < 80 && Number(item.combined_score) >= 70).slice(0, 16) },
      { label: "观察", min: 0, rows: leaders.filter((item) => Number(item.combined_score) < 70).slice(0, 18) },
    ].filter((tier) => tier.rows.length);
    $("leaderLadder").innerHTML = tiers
      .map((tier, index) => `
        <div class="ladder-row">
          <div class="level-mark"><span class="level-num">${tiers.length - index}</span><span class="level-label">${escapeHtml(tier.label)}</span></div>
          <div class="cards-row">${tier.rows.map(leaderCard).join("")}</div>
        </div>
      `)
      .join("");
    $("leaderLadder").querySelectorAll(".leader-card").forEach((card) => {
      card.addEventListener("click", () => {
        state.leaderCode = card.dataset.code;
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
        <h3>${escapeHtml(leader.name)}</h3>
        <p>${escapeHtml(leader.code)}  |  人气 #${escapeHtml(leader.rank)}  |  ${escapeHtml(leader.board_path)}</p>
      </div>
      <div class="score-bars">
        ${scoreLine("综合", leader.combined_score, "#ef4444")}
        ${scoreLine("qlib", leader.qlib_factor_score, "#2f7df6")}
        ${scoreLine("LumenAlpha", leader.lumen_score_norm, "#d97706")}
        ${scoreLine("板块", leader.sector_trend_score, "#059669")}
      </div>
      <div class="signal-stack">${signalBadges(leader.top_signals)}</div>
      <div class="detail-kv">
        <div class="kv"><span>5日涨幅</span><strong>${pct(leader.ret_5d)}</strong></div>
        <div class="kv"><span>20日涨幅</span><strong>${pct(leader.ret_20d)}</strong></div>
        <div class="kv"><span>板块5日</span><strong>${pct(leader.sector_ret_5d)}</strong></div>
        <div class="kv"><span>板块20日</span><strong>${pct(leader.sector_ret_20d)}</strong></div>
      </div>
      <div class="kline-block">
        <div class="kline-head"><strong>30日K线</strong><span>近5日显著信号 ${chart.markers ? chart.markers.length : 0}</span></div>
        ${renderKlineChart(chart, `${leader.name} 30日K线`)}
      </div>
      ${renderAiResult(key, "个股AI分析")}
    `;
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

  function renderKlineChart(chart, title = "30日K线") {
    const candles = (chart && chart.candles) || [];
    const markers = (chart && chart.markers) || [];
    if (!candles.length) {
      return `<div class="empty">暂无 K 线数据</div>`;
    }
    const width = 360;
    const height = 210;
    const pad = { left: 24, right: 12, top: 22, bottom: 24 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
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
    const yOf = (value) => pad.top + (max - Number(value)) / span * plotH;
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
    const visibleMarkers = markers
      .filter((m) => dateToIndex.has(m.date))
      .slice(-10);
    const markerSvg = visibleMarkers.map((m, markerIndex) => {
      const index = dateToIndex.get(m.date);
      const candle = candles[index];
      const x = xOf(index);
      const y = yOf(m.y || candle.close);
      const label = String(m.label || "").slice(0, 10);
      const labelW = Math.max(34, Math.min(76, label.length * 8 + 10));
      const labelX = Math.max(4, Math.min(width - labelW - 4, x - labelW / 2));
      const labelY = Math.max(3, y - 18 - (markerIndex % 3) * 12);
      const tone = markerTone(m.direction);
      return `
        <g class="kline-marker ${tone}">
          <line x1="${x.toFixed(1)}" y1="${(labelY + 14).toFixed(1)}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${markerFill(m.direction)}" stroke-dasharray="2 2" opacity="0.65"></line>
          <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.6"></circle>
          <rect x="${labelX.toFixed(1)}" y="${labelY.toFixed(1)}" width="${labelW.toFixed(1)}" height="16"></rect>
          <text x="${(labelX + 5).toFixed(1)}" y="${(labelY + 11).toFixed(1)}">${escapeHtml(label)}</text>
        </g>
      `;
    }).join("");
    const start = candles[0]?.date?.slice(5) || "";
    const end = candles[candles.length - 1]?.date?.slice(5) || "";
    return `
      <svg class="kline-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}">
        <line class="kline-axis" x1="${pad.left}" y1="${pad.top + plotH}" x2="${width - pad.right}" y2="${pad.top + plotH}"></line>
        <line class="kline-axis" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top + plotH}"></line>
        <text x="${pad.left}" y="14" font-size="10" fill="#64748b">${escapeHtml(title)}</text>
        <text x="${pad.left}" y="${height - 6}" font-size="9" fill="#94a3b8">${escapeHtml(start)}</text>
        <text x="${width - pad.right - 28}" y="${height - 6}" font-size="9" fill="#94a3b8">${escapeHtml(end)}</text>
        ${candleSvg}
        ${markerSvg}
      </svg>
    `;
  }

  function sparkline(rows, path) {
    if (!rows || rows.length < 2) {
      return `<svg class="sparkline" viewBox="0 0 220 66" role="img" aria-label="暂无曲线"><line class="axis" x1="0" y1="54" x2="220" y2="54"></line></svg>`;
    }
    const values = rows.map((row) => Number(row.sector_index)).filter(Number.isFinite);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(max - min, 1);
    const points = rows.map((row, index) => {
      const x = (index / Math.max(rows.length - 1, 1)) * 220;
      const y = 56 - ((Number(row.sector_index) - min) / span) * 48;
      return [x, y];
    });
    const line = points.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    const area = `${line} L220,62 L0,62 Z`;
    return `
      <svg class="sparkline" viewBox="0 0 220 66" role="img" aria-label="${escapeHtml(boardLabel(path))}趋势">
        <line class="axis" x1="0" y1="56" x2="220" y2="56"></line>
        <path class="area" d="${area}"></path>
        <path class="line" d="${line}"></path>
      </svg>
    `;
  }

  function renderSectorTrends() {
    const curveMap = curvesByBoard();
    const boards = [...(data.boards || [])].sort((a, b) => Number(b.sector_trend_score || -1) - Number(a.sector_trend_score || -1));
    const visible = state.board === "all" ? boards : boards.filter((board) => board.board_path === state.board);
    if (!state.selectedBoard || !boards.some((board) => board.board_path === state.selectedBoard)) {
      state.selectedBoard = visible[0]?.board_path || boards[0]?.board_path || null;
    }
    const curveBoards = boards.filter((board) => curveMap.has(board.board_path)).length;
    $("coverageBadge").textContent = `曲线覆盖 ${curveBoards}/${boards.length}`;
    $("sectorTrends").innerHTML = visible
      .map((board) => {
        const toneStyle = styleVars(board.board_path);
        const rows = (curveMap.get(board.board_path) || []).slice(-state.boardWindow);
        const active = state.selectedBoard === board.board_path ? " active" : "";
        const intervalRet = rows.length >= 2 ? Number(rows[rows.length - 1].sector_index) / Number(rows[0].sector_index) - 1 : NaN;
        return `
          <article class="trend-card${active}" style="${toneStyle}" data-board="${escapeHtml(board.board_path)}">
            <div class="trend-head">
              <div>
                <h3>${escapeHtml(boardLabel(board.board_path))}</h3>
                <p>${escapeHtml(boardSubLabel(board.board_path))}  |  样本 ${board.curve_member_count || 0}/${board.stock_count || 0}</p>
              </div>
              <div class="trend-score">${num(board.sector_trend_score, 0)}</div>
            </div>
            ${sparkline(rows, board.board_path)}
            <div class="trend-meta">
              <span>${state.boardWindow}日 ${pct(intervalRet)}</span>
              <span>5日 ${pct(board.sector_ret_5d)}</span>
              <span>20日 ${pct(board.sector_ret_20d)}</span>
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
    const board = (data.boards || []).find((item) => item.board_path === state.selectedBoard) || (data.boards || [])[0];
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
          <div class="kline-head"><strong>板块30日K线</strong><span>近5日显著信号 ${chart.markers ? chart.markers.length : 0}</span></div>
          ${renderKlineChart(chart, `${boardLabel(board.board_path)} 板块30日K线`)}
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
    const rows = filteredSignals().slice(0, 42);
    const totalRows = filteredSignals().length;
    $("signalResultCount").textContent = `当前 ${rows.length}/${totalRows}`;
    if (!rows.length) {
      $("signalTable").innerHTML = `<div class="empty">当前板块暂无信号</div>`;
      return;
    }
    $("signalTable").innerHTML = rows
      .map((row) => `
        <div class="signal-row">
          <span class="source ${sourceClass(row.source_project)}">${escapeHtml(sourceName(row.source_project))}</span>
          <strong>${escapeHtml(row.name)}</strong>
          <span><span class="signal-name">${escapeHtml(row.signal_name)}</span><br><span class="evidence">${escapeHtml(row.evidence)}</span></span>
          <span class="signal-score">${num(row.signal_score, 1)}</span>
          <span class="direction ${escapeHtml(row.direction || "neutral")}">${escapeHtml(row.direction || "neutral")}</span>
        </div>
      `)
      .join("");
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
      "qlib、LumenAlpha、东方财富人气已统一到同一张信号表，并保留来源标记。",
      ...issues,
    ];
    $("reviewFindings").innerHTML = notes.map((note) => `<div class="review-item">${escapeHtml(note)}</div>`).join("");

    const boards = [...(data.boards || [])]
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

  function renderMerge() {
    const flow = [
      ["qlib", "标准因子与模型框架", "Alpha158 / Alpha360 / 表达式因子 / 后续回测"],
      ["LumenAlpha", "解释性技术信号", "基础指标 / 普通信号 / 组合信号 / 高级形态"],
      ["Taxonomy", "科技板块分层", "一级科技 + 二级主线 + 三级细分板块"],
      ["Signal Table", "统一信号表", "source_project / signal_name / score / evidence"],
      ["Dashboard", "轮动工作台", "龙头显著信号 + 板块时间曲线 + 因子图谱"],
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
      ["source_project", "qlib / LumenAlpha / Eastmoney"],
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
    const lines = String(markdown || "").split(/\r?\n/);
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
    target.innerHTML = `
      ${renderAiResult(key, "日报AI分析")}
      ${renderMarkdownLite(state.dailyReportText)}
    `;
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
      items = items.filter((item) => item.project === state.factorProject);
    }
    if (state.factorFamily !== "all") {
      items = items.filter((item) => item.family === state.factorFamily);
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
    }
    return items;
  }

  function renderFactorMetrics() {
    const stats = factorCatalog.stats || {};
    const byProject = stats.byProject || {};
    const byFamily = stats.byFamily || {};
    const items = [
      ["总条目", stats.total || (factorCatalog.items || []).length],
      ["qlib", byProject.qlib || 0],
      ["LumenAlpha", byProject.LumenAlpha || 0],
      ["Alpha158", byFamily.Alpha158 || 0],
      ["Alpha360", byFamily.Alpha360 || 0],
    ];
    $("factorGeneratedAt").textContent = `${factorCatalog.generatedAt || "--"}  |  标准因子与信号目录`;
    $("factorTotal").textContent = `当前 ${factorItems().length}/${stats.total || 0}`;
    $("factorMetrics").innerHTML = items
      .map(([label, value]) => `<div class="factor-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
      .join("");
  }

  function renderFactorTabs() {
    const projects = ["all", ...new Set((factorCatalog.items || []).map((item) => item.project))];
    $("factorProjectTabs").innerHTML = projects
      .map((project) => {
        const active = state.factorProject === project ? " active" : "";
        const label = project === "all" ? "全部项目" : projectLabel(project);
        return `<button class="factor-tab${active}" type="button" data-project="${escapeHtml(project)}">${escapeHtml(label)}</button>`;
      })
      .join("");
    $("factorProjectTabs").querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        state.factorProject = button.dataset.project || "all";
        state.factorFamily = "all";
        renderFactors();
      });
    });

    const familyBase = state.factorProject === "all"
      ? factorCatalog.items || []
      : (factorCatalog.items || []).filter((item) => item.project === state.factorProject);
    const families = ["all", ...new Set(familyBase.map((item) => item.family))];
    $("factorFamilyTabs").innerHTML = families
      .map((family) => {
        const active = state.factorFamily === family ? " active" : "";
        const label = family === "all" ? "全部特征族" : family;
        return `<button class="factor-tab${active}" type="button" data-family="${escapeHtml(family)}">${escapeHtml(label)}</button>`;
      })
      .join("");
    $("factorFamilyTabs").querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        state.factorFamily = button.dataset.family || "all";
        renderFactors();
      });
    });
  }

  function renderFactorNotes() {
    $("factorNotes").innerHTML = (factorCatalog.notes || [])
      .map((note) => `<div class="factor-note">${escapeHtml(note)}</div>`)
      .join("");
  }

  function factorRow(item) {
    const score = item.score === "" || item.score === null || item.score === undefined ? "--" : item.score;
    const params = item.parameters ? `参数 ${item.parameters}` : "";
    const notes = item.notes ? `<br>${escapeHtml(item.notes)}` : "";
    return `
      <div class="factor-row">
        <span class="source ${sourceClass(item.project)}">${escapeHtml(projectLabel(item.project))}</span>
        <div class="factor-name">
          <strong>${escapeHtml(item.name)}</strong>
          <span>${escapeHtml(item.family)}</span>
        </div>
        <div class="factor-category">${escapeHtml(item.category || "--")}<br>${escapeHtml(params)}</div>
        <div class="factor-meaning">${escapeHtml(item.meaning || "--")}${notes}</div>
        <div class="factor-formula"><code>${escapeHtml(item.formula || item.source_file || "--")}</code></div>
        <div class="factor-score">${escapeHtml(score)}</div>
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
    $("factorCatalog").innerHTML = `
      <div class="factor-table-head">
        <span>项目</span><span>名称</span><span>类别</span><span>含义</span><span>公式/来源</span><span>分值</span>
      </div>
      ${items.map(factorRow).join("")}
    `;
  }

  function renderFactors() {
    renderFactorMetrics();
    renderFactorTabs();
    renderFactorNotes();
    renderFactorCatalog();
  }

  function renderViews() {
    document.querySelectorAll(".view").forEach((view) => {
      view.classList.toggle("active", view.id === `${state.view}View`);
    });
    document.querySelectorAll(".nav-item").forEach((item) => {
      const view = item.dataset.view || "dashboard";
      if (state.view !== "dashboard") {
        item.classList.toggle("active", view === state.view);
      } else {
        item.classList.toggle("active", view === "dashboard" && item.textContent.includes(state.activeDashboardNav));
      }
    });
    if (state.view === "dashboard" && state.section) {
      requestAnimationFrame(() => {
        const target = $(state.section);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } else {
      requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "smooth" }));
    }
  }

  function bindNav() {
    document.querySelectorAll(".nav-item").forEach((button) => {
      button.addEventListener("click", () => {
        state.view = button.dataset.view || "dashboard";
        if (state.view === "dashboard") {
          state.section = button.dataset.section || "leadersSection";
          state.activeDashboardNav = button.querySelector("span:last-child")?.textContent || "龙头天梯";
        }
        renderViews();
      });
    });
  }

  function bindModes() {
    document.querySelectorAll(".mode").forEach((button) => {
      button.addEventListener("click", () => {
        state.mode = button.dataset.mode || "day";
        document.querySelectorAll(".mode").forEach((item) => item.classList.toggle("active", item === button));
      });
    });
  }

  function bindFactorSearch() {
    const input = $("factorSearch");
    if (!input) return;
    input.addEventListener("input", () => {
      state.factorSearch = input.value || "";
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

  function render() {
    renderGeneratedAt();
    renderMetrics();
    renderBoardChips();
    renderLeaderLadder();
    renderLeaderDetail();
    renderSectorTrends();
    renderSignalTable();
    renderFactors();
    renderReview();
    renderMerge();
    renderDailyAnalysis();
    renderViews();
    loadDailyAnalysis();
  }

  bindNav();
  bindModes();
  bindFactorSearch();
  bindSignalSearch();
  bindBoardWindows();
  render();
})();
