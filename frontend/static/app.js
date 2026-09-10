const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const state = {
  dashboard: null,
  games: [],
  jobs: [],
  queue: null,
  openingStats: [],
  profiles: [],
  activeProfile: null,
  openingSortBy: "most_played",
  activeView: "home",
  search: "",
  sortBy: "recent",
  timeFilter: "all",
  filtersOpen: false,
  statsTime: "Overall",
  theme: document.documentElement.dataset.theme || "light",
  selectedGameId: null,
  selectedGame: null,
  selectedPly: null,
  selectedPositions: [],
  startingFen: null,
  boardOrientations: {
    gameExplorer: "white",
    analysisBoard: "white",
    openingExplorer: "white",
  },
  analysisBoard: null,
  openingExplorer: null,
  pollTimer: null,
  pendingDeleteGameId: null,
};

const els = {
  status: document.querySelector("#status"),
  pageTitle: document.querySelector("#pageTitle"),
  refreshButton: document.querySelector("#refreshButton"),
  themeToggleButton: document.querySelector("#themeToggleButton"),
  profileSelect: document.querySelector("#profileSelect"),
  createProfileButton: document.querySelector("#createProfileButton"),
  profileModal: document.querySelector("#profileModal"),
  newProfileName: document.querySelector("#newProfileName"),
  cancelProfileButton: document.querySelector("#cancelProfileButton"),
  saveProfileButton: document.querySelector("#saveProfileButton"),
  activeImportProfile: document.querySelector("#activeImportProfile"),
  navButtons: document.querySelectorAll(".bottom-nav-button"),
  views: {
    home: document.querySelector("#homeView"),
    openings: document.querySelector("#openingsView"),
    openingExplorer: document.querySelector("#openingExplorerView"),
    games: document.querySelector("#gamesView"),
    insights: document.querySelector("#insightsView"),
    more: document.querySelector("#moreView"),
    analysis: document.querySelector("#analysisView"),
    detail: document.querySelector("#detailView"),
  },
  metricsGrid: document.querySelector("#metricsGrid"),
  statsTimeControl: document.querySelector("#statsTimeControl"),
  timeStatsGrid: document.querySelector("#timeStatsGrid"),
  insightList: document.querySelector("#insightList"),
  trendChart: document.querySelector("#trendChart"),
  ratingChart: document.querySelector("#ratingChart"),
  phaseList: document.querySelector("#phaseList"),
  mistakeList: document.querySelector("#mistakeList"),
  openingList: document.querySelector("#openingList"),
  openingEdgeList: document.querySelector("#openingEdgeList"),
  openingSortSelect: document.querySelector("#openingSortSelect"),
  openingStatsList: document.querySelector("#openingStatsList"),
  openingExplorerMount: document.querySelector("#openingExplorerMount"),
  openingExplorerName: document.querySelector("#openingExplorerName"),
  openingExplorerPly: document.querySelector("#openingExplorerPly"),
  startOpeningExplorerButton: document.querySelector("#startOpeningExplorerButton"),
  importButton: document.querySelector("#importButton"),
  fileInput: document.querySelector("#fileInput"),
  pgnInput: document.querySelector("#pgnInput"),
  chesscomUsername: document.querySelector("#chesscomUsername"),
  syncLimit: document.querySelector("#syncLimit"),
  syncForce: document.querySelector("#syncForce"),
  syncButton: document.querySelector("#syncButton"),
  syncHistory: document.querySelector("#syncHistory"),
  gameList: document.querySelector("#gameList"),
  gameCountLabel: document.querySelector("#gameCountLabel"),
  gameFilterPanel: document.querySelector("#gameFilterPanel"),
  filterToggleButton: document.querySelector("#filterToggleButton"),
  searchInput: document.querySelector("#searchInput"),
  timeFilterSelect: document.querySelector("#timeFilterSelect"),
  sortSelect: document.querySelector("#sortSelect"),
  analyzeAllButton: document.querySelector("#analyzeAllButton"),
  newAnalysisButton: document.querySelector("#newAnalysisButton"),
  moreAnalysisButton: document.querySelector("#moreAnalysisButton"),
  depthInput: document.querySelector("#depthInput"),
  queueSummary: document.querySelector("#queueSummary"),
  jobList: document.querySelector("#jobList"),
  backToGames: document.querySelector("#backToGames"),
  backFromAnalysis: document.querySelector("#backFromAnalysis"),
  backFromOpening: document.querySelector("#backFromOpening"),
  gameDetail: document.querySelector("#gameDetail"),
  analysisBoardMount: document.querySelector("#analysisBoardMount"),
  confirmModal: document.querySelector("#confirmModal"),
  confirmBody: document.querySelector("#confirmBody"),
  cancelDeleteButton: document.querySelector("#cancelDeleteButton"),
  confirmDeleteButton: document.querySelector("#confirmDeleteButton"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function showStatus(message, timeout = 5000) {
  els.status.textContent = message;
  els.status.hidden = false;
  if (timeout) {
    setTimeout(() => {
      els.status.hidden = true;
    }, timeout);
  }
}

function setView(view) {
  state.activeView = view;
  document.body.classList.toggle("workspace-active", isWorkspaceView(view));
  Object.entries(els.views).forEach(([key, node]) => {
    node.classList.toggle("active", key === view);
  });
  const primaryView = primaryViewFor(view);
  els.navButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.view === primaryView);
  });
  if (els.pageTitle) els.pageTitle.textContent = pageTitleFor(view);
}

function isWorkspaceView(view) {
  return view === "analysis" || view === "openingExplorer";
}

function primaryViewFor(view) {
  if (view === "detail" || view === "analysis") return "games";
  if (view === "openingExplorer") return "openings";
  return view;
}

function pageTitleFor(view) {
  return {
    home: "Home",
    openings: "Openings",
    openingExplorer: "Opening Explorer",
    games: "Games",
    insights: "Insights",
    more: "More",
    detail: "Game",
    analysis: "Analysis",
  }[view] || "Home";
}

async function loadAll() {
  await loadProfiles();
  const profileQuery = profileParam();
  const [dashboard, games, queueStatus, syncs, openingStats] = await Promise.all([
    api(`/api/dashboard${profileQuery}`),
    api(`/api/games${profileQuery}`),
    api(`/api/analysis/jobs${profileQuery}`),
    api(`/api/chesscom/syncs${profileQuery}`),
    api(`/api/openings?sort_by=${encodeURIComponent(state.openingSortBy)}${profileAmpParam()}`),
  ]);
  state.dashboard = dashboard;
  state.games = games;
  state.queue = queueStatus;
  state.jobs = queueStatus.jobs || [];
  state.syncs = syncs || [];
  state.openingStats = openingStats || [];
  renderDashboard();
  renderProfiles();
  renderGames();
  renderOpeningStats();
  renderJobs();
  renderSyncHistory();
  updatePolling();
}

async function loadProfiles() {
  const [profiles, active] = await Promise.all([
    api("/api/profiles"),
    api("/api/profiles/active"),
  ]);
  state.profiles = profiles || [];
  const storedId = localStorage.getItem("activeProfileId");
  const storedProfile = state.profiles.find((profile) => String(profile.id) === storedId);
  state.activeProfile = storedProfile || active;
  if (storedProfile && String(active.id) !== String(storedProfile.id)) {
    await api("/api/profiles/active", {
      method: "PUT",
      body: JSON.stringify({ profile_id: Number(storedProfile.id) }),
    });
  }
  localStorage.setItem("activeProfileId", String(state.activeProfile.id));
}

function renderProfiles() {
  els.profileSelect.innerHTML = state.profiles.map((profile) => `
    <option value="${profile.id}" ${String(profile.id) === String(state.activeProfile?.id) ? "selected" : ""}>
      ${escapeHtml(profile.name)}
    </option>
  `).join("");
  els.activeImportProfile.textContent = `Profile: ${state.activeProfile?.name || "-"}`;
  els.chesscomUsername.value = state.activeProfile?.chesscom_username || "";
  els.syncLimit.value = state.activeProfile?.chesscom_sync_days || 7;
}

function profileParam() {
  return state.activeProfile ? `?profile_id=${encodeURIComponent(state.activeProfile.id)}` : "";
}

function profileAmpParam() {
  return state.activeProfile ? `&profile_id=${encodeURIComponent(state.activeProfile.id)}` : "";
}

function renderOpeningStats() {
  const rows = state.openingStats || [];
  if (!rows.length) {
    els.openingStatsList.innerHTML = `<section class="panel">No openings yet.</section>`;
    return;
  }
  els.openingStatsList.innerHTML = rows.map((row) => `
    <article class="opening-stat-card">
      <div>
        <div class="stat-title">${escapeHtml(row.opening)}</div>
        <div class="stat-subtitle">${row.games} games · ${formatNumber(row.average_game_length)} avg moves</div>
      </div>
      <div class="opening-stat-grid">
        <div><span>W</span><strong>${row.win_pct}%</strong></div>
        <div><span>D</span><strong>${row.draw_pct}%</strong></div>
        <div><span>L</span><strong>${row.loss_pct}%</strong></div>
        <div><span>Acc</span><strong>${row.average_accuracy == null ? "-" : `${row.average_accuracy}%`}</strong></div>
      </div>
    </article>
  `).join("");
}

function renderDashboard() {
  const totals = state.dashboard?.totals || {};
  const metrics = [
    ["Games", totals.games ?? 0],
    ["Analyzed", totals.analyzed_games ?? 0],
    ["ACPL", formatNumber(totals.acpl)],
    ["Accuracy", totals.accuracy == null ? "-" : `${totals.accuracy}%`],
    ["Wins", totals.wins ?? 0],
    ["Draws", totals.draws ?? 0],
    ["Losses", totals.losses ?? 0],
    ["Blunders", totals.blunders ?? 0],
  ];
  els.metricsGrid.innerHTML = metrics.map(([label, value]) => `
    <article class="metric">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${escapeHtml(String(value))}</div>
    </article>
  `).join("");

  renderTimeStats(state.dashboard?.time_control_stats || []);
  renderInsights(state.dashboard?.insights || []);
  renderTrend(state.dashboard?.trend || []);
  renderRatingTrend(state.dashboard?.rating_trend || []);
  renderPhases(state.dashboard?.phases || []);
  renderMistakes(state.dashboard?.mistake_breakdown || {});
  renderOpenings(state.dashboard?.openings || []);
  renderOpeningEdges(state.dashboard?.opening_summary || {});
}

function renderTimeStats(rows) {
  const selected = rows.find((row) => row.time_class === state.statsTime) || rows[0];
  if (!selected) {
    els.timeStatsGrid.innerHTML = "";
    return;
  }
  const metrics = [
    ["Games", selected.games ?? 0],
    ["W-L-D", `${selected.wins ?? 0}-${selected.losses ?? 0}-${selected.draws ?? 0}`],
    ["Accuracy", selected.accuracy == null ? "-" : `${selected.accuracy}%`],
    ["Avg Length", selected.average_game_length == null ? "-" : `${selected.average_game_length} moves`],
  ];
  els.timeStatsGrid.innerHTML = metrics.map(([label, value]) => `
    <article class="metric compact-metric">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${escapeHtml(String(value))}</div>
    </article>
  `).join("");
  els.statsTimeControl.querySelectorAll(".segment").forEach((button) => {
    button.classList.toggle("active", button.dataset.statsTime === state.statsTime);
  });
}


function renderInsights(insights) {
  if (!insights.length) {
    els.insightList.innerHTML = `<div class="stat-subtitle">Analyze more games to generate coaching notes.</div>`;
    return;
  }
  els.insightList.innerHTML = insights.map((insight) => `
    <article class="insight-card">
      <div class="stat-title">${escapeHtml(insight.title)}</div>
      <div class="stat-subtitle">${escapeHtml(insight.body)}</div>
    </article>
  `).join("");
}

function renderTrend(rows) {
  if (!rows.length) {
    els.trendChart.innerHTML = `<div class="stat-subtitle">Analyze games to see your accuracy trend.</div>`;
    return;
  }
  const max = Math.max(...rows.map((row) => row.acpl || 0), 1);
  els.trendChart.innerHTML = rows.map((row) => {
    const height = Math.max(8, Math.round((row.acpl / max) * 100));
    return `<div class="bar" title="Game ${row.game_id}: ${row.acpl} ACPL" style="height:${height}%"></div>`;
  }).join("");
}

function renderRatingTrend(rows) {
  if (!rows.length) {
    els.ratingChart.innerHTML = `<div class="stat-subtitle">Rating appears when PGNs include ratings.</div>`;
    return;
  }
  const ratings = rows.map((row) => row.rating || 0);
  const min = Math.min(...ratings);
  const max = Math.max(...ratings);
  const span = Math.max(1, max - min);
  els.ratingChart.innerHTML = rows.map((row) => {
    const height = Math.max(8, Math.round(((row.rating - min) / span) * 90) + 10);
    return `<div class="bar rating-bar" title="Game ${row.game_id}: ${row.rating}" style="height:${height}%"></div>`;
  }).join("");
}

function renderPhases(phases) {
  if (!phases.length) {
    els.phaseList.innerHTML = `<div class="stat-subtitle">No phase analysis yet.</div>`;
    return;
  }
  els.phaseList.innerHTML = phases.map((phase) => `
    <div class="stat-row">
      <div>
        <div class="stat-title">${capitalize(phase.phase)}</div>
        <div class="stat-subtitle">${phase.moves} moves analyzed · ${escapeHtml(phase.label || "steady")}</div>
      </div>
      <span class="pill">${formatNumber(phase.acpl)} ACPL</span>
    </div>
  `).join("");
}

function renderMistakes(breakdown) {
  const rows = [
    ["Inaccuracies", breakdown.inaccuracies || 0],
    ["Mistakes", breakdown.mistakes || 0],
    ["Blunders", breakdown.blunders || 0],
    ["Large Swings", breakdown.large_eval_swings || 0],
    ["Conversion Misses", breakdown.conversion_failures || 0],
    ["Defensive Saves", breakdown.defensive_saves || 0],
  ];
  els.mistakeList.innerHTML = rows.map(([label, value]) => `
    <div class="stat-row">
      <div>
        <div class="stat-title">${escapeHtml(label)}</div>
        <div class="stat-subtitle">${mistakeDescription(label)}</div>
      </div>
      <span class="pill">${value}</span>
    </div>
  `).join("");
}

function renderOpenings(openings) {
  if (!openings.length) {
    els.openingList.innerHTML = `<div class="stat-subtitle">Imported games will appear here.</div>`;
    return;
  }
  els.openingList.innerHTML = openings.map((opening) => `
    <div class="stat-row">
      <div>
        <div class="stat-title">${escapeHtml(opening.opening)}</div>
        <div class="stat-subtitle">${opening.games} games · ${Math.round((opening.score_rate || 0) * 100)}% score</div>
      </div>
      <span class="pill">${formatNumber(opening.acpl)} ACPL</span>
    </div>
  `).join("");
}

function renderOpeningEdges(summary) {
  const best = summary.best || [];
  const weakest = summary.weakest || [];
  if (!best.length && !weakest.length) {
    els.openingEdgeList.innerHTML = `<div class="stat-subtitle">Opening strengths appear after analyzed games.</div>`;
    return;
  }
  els.openingEdgeList.innerHTML = `
    <div class="edge-grid">
      <div>
        <div class="mini-heading">Best</div>
        ${best.map(renderOpeningEdge).join("") || `<div class="stat-subtitle">No analyzed openings.</div>`}
      </div>
      <div>
        <div class="mini-heading">Weakest</div>
        ${weakest.map(renderOpeningEdge).join("") || `<div class="stat-subtitle">No analyzed openings.</div>`}
      </div>
    </div>
  `;
}

function renderOpeningEdge(opening) {
  return `
    <div class="edge-row">
      <div class="stat-title">${escapeHtml(opening.opening)}</div>
      <div class="stat-subtitle">${opening.games} games · ${formatNumber(opening.acpl)} ACPL · ${opening.score_rate == null ? "-" : Math.round(opening.score_rate * 100)}% score</div>
    </div>
  `;
}

function mistakeDescription(label) {
  const descriptions = {
    "Inaccuracies": "75+ CPL moves",
    "Mistakes": "150+ CPL moves",
    "Blunders": "300+ CPL moves",
    "Large Swings": "major evaluation drops",
    "Conversion Misses": "errors from good positions",
    "Defensive Saves": "steady moves while worse",
  };
  return descriptions[label] || "";
}

function renderGames() {
  const query = state.search.trim().toLowerCase();
  const games = sortGames(state.games.filter((game) => {
    const haystack = `${game.white || ""} ${game.black || ""} ${game.opening || ""} ${game.eco || ""} ${game.time_class || ""}`.toLowerCase();
    const matchesQuery = haystack.includes(query);
    const matchesTime = state.timeFilter === "all" || game.time_class === state.timeFilter;
    return matchesQuery && matchesTime;
  }));
  if (els.gameFilterPanel) els.gameFilterPanel.hidden = !state.filtersOpen;
  if (els.filterToggleButton) els.filterToggleButton.textContent = state.filtersOpen ? "Hide Filters" : "Filter";
  if (els.gameCountLabel) {
    const label = games.length === 1 ? "1 game" : `${games.length} games`;
    els.gameCountLabel.textContent = label;
  }
  if (!games.length) {
    els.gameList.innerHTML = `<section class="panel">No games match.</section>`;
    return;
  }
  els.gameList.innerHTML = games.map((game) => `
    <article class="game-row clickable-card" data-game-id="${game.id}" role="button" tabindex="0">
      <span class="result-mark ${gameResultClass(game)}" aria-label="${escapeHtml(gameResultWord(game))}">${escapeHtml(gameResultMark(game))}</span>
      <div class="game-row-main">
        <div class="game-row-title">
          <span>${escapeHtml(opponentName(game))}</span>
          <span class="game-row-elo">${escapeHtml(opponentElo(game))}</span>
        </div>
        <div class="game-row-meta">${escapeHtml(game.opening || game.eco || "Unknown opening")} · ${escapeHtml(shortDate(game.played_at))}</div>
      </div>
      <span class="time-icon" title="${escapeHtml(game.time_class || "Unknown")}">${timeControlIcon(game.time_class)}</span>
      <span class="game-row-result">${escapeHtml(displayResult(game.result))}</span>
    </article>
  `).join("");
}

function sortGames(games) {
  const sorted = [...games];
  const acpl = (game) => game.acpl == null ? Number.POSITIVE_INFINITY : Number(game.acpl);
  const plies = (game) => Number(game.ply_count || 0);
  const date = (game) => String(game.played_at || "");
  if (state.sortBy === "accuracy_desc") {
    sorted.sort((a, b) => acpl(a) - acpl(b));
  } else if (state.sortBy === "accuracy_asc") {
    sorted.sort((a, b) => acpl(b) - acpl(a));
  } else if (state.sortBy === "longest") {
    sorted.sort((a, b) => plies(b) - plies(a));
  } else if (state.sortBy === "shortest") {
    sorted.sort((a, b) => plies(a) - plies(b));
  } else if (state.sortBy === "time_class") {
    sorted.sort((a, b) => timeRank(a.time_class) - timeRank(b.time_class) || date(b).localeCompare(date(a)));
  } else {
    sorted.sort((a, b) => date(b).localeCompare(date(a)) || Number(b.id) - Number(a.id));
  }
  return sorted;
}

function gameResultMark(game) {
  const result = gameResultWord(game);
  if (result === "win") return "✓";
  if (result === "loss") return "×";
  if (result === "draw") return "–";
  return "";
}

function gameResultClass(game) {
  return gameResultWord(game);
}

function gameResultWord(game) {
  const result = String(game.result || "");
  if (result === "1/2-1/2") return "draw";
  const userColor = userColorForGame(game);
  if (result === "1-0") return userColor === "white" ? "win" : "loss";
  if (result === "0-1") return userColor === "black" ? "win" : "loss";
  return "unknown";
}

function opponentName(game) {
  const userColor = userColorForGame(game);
  return userColor === "white" ? (game.black || "Black") : (game.white || "White");
}

function opponentElo(game) {
  const userColor = userColorForGame(game);
  const elo = userColor === "white" ? game.black_elo : game.white_elo;
  return elo == null ? "Unrated" : String(elo);
}

function displayResult(result) {
  if (result === "1/2-1/2") return "½-½";
  return result || "*";
}

function shortDate(value) {
  if (!value) return "Unknown date";
  const text = String(value);
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return text;
  return `${match[2]}/${match[3]}/${match[1].slice(2)}`;
}

function timeControlIcon(timeClass) {
  const label = String(timeClass || "Unknown");
  const icons = {
    Bullet: "•",
    Blitz: "⚡",
    Rapid: "◷",
    Classical: "◴",
    "Daily / Correspondence": "✉",
  };
  return icons[label] || "○";
}

function filteredGameIds() {
  const query = state.search.trim().toLowerCase();
  return state.games
    .filter((game) => {
      const haystack = `${game.white || ""} ${game.black || ""} ${game.opening || ""} ${game.eco || ""} ${game.time_class || ""}`.toLowerCase();
      return haystack.includes(query) && (state.timeFilter === "all" || game.time_class === state.timeFilter);
    })
    .map((game) => game.id);
}

function renderJobs() {
  const queued = state.queue?.queued || 0;
  const running = state.jobs.filter((job) => job.status === "running").length;
  const queuedJobs = state.jobs.filter((job) => job.status === "queued").length;
  els.queueSummary.textContent = running || queuedJobs || queued ? `${running} running · ${queuedJobs || queued} queued` : "Idle";

  const activeJobs = state.jobs
    .filter((job) => ["queued", "running", "failed"].includes(job.status))
    .slice(0, 6);

  if (!activeJobs.length) {
    els.jobList.innerHTML = `<div class="stat-subtitle">No active analysis jobs.</div>`;
    return;
  }

  els.jobList.innerHTML = activeJobs.map((job) => {
    const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
    return `
      <div class="stat-row">
        <div>
          <div class="stat-title">${escapeHtml(job.white || "White")} vs ${escapeHtml(job.black || "Black")}</div>
          <div class="stat-subtitle">Depth ${job.depth} · ${escapeHtml(job.status)} · ${job.analyzed_plies}/${job.total_plies} plies</div>
          <div class="progress-track"><div class="progress-fill" style="width:${progress}%"></div></div>
          ${job.error ? `<div class="stat-subtitle">${escapeHtml(job.error)}</div>` : ""}
        </div>
        <span class="pill ${job.status === "failed" ? "bad" : "warn"}">${progress}%</span>
      </div>
    `;
  }).join("");
}

async function renderGameDetail(gameId) {
  state.selectedGameId = gameId;
  const detail = await api(`/api/games/${gameId}${profileParam()}`);
  const game = detail.game;
  const moves = detail.moves || [];
  state.selectedGame = game;
  state.selectedPositions = moves;
  state.startingFen = detail.starting_fen || moves[0]?.fen_before || null;
  state.selectedPly = defaultSelectedPly(moves);
  els.gameDetail.innerHTML = `
    <section class="panel detail-header">
      <h2>${escapeHtml(game.white || "White")} vs ${escapeHtml(game.black || "Black")}</h2>
      <div class="stat-subtitle">${escapeHtml(game.played_at || "Unknown date")} · ${escapeHtml(game.result || "*")}</div>
      <div class="stat-subtitle">${escapeHtml(game.opening || game.eco || "Unknown opening")}</div>
      <div class="detail-actions">
        <button class="secondary-button" id="analysisGameButton">Analysis Board</button>
        <button class="primary" id="analyzeGameButton">Analyze Game</button>
        <button class="danger-button" id="deleteGameButton">Delete Game</button>
      </div>
    </section>
    ${renderBoardExplorer(moves, state.startingFen)}
    <section class="panel analysis-panel">
      <div class="panel-heading">
        <h2>Evaluation</h2>
        <span class="pill">${detail.depth == null ? "Pending" : `Depth ${detail.depth}`}</span>
      </div>
      ${renderEvaluationGraph(detail.evaluation_history || [], detail.evaluation_summary || {}, game)}
    </section>
    <section class="panel analysis-panel">
      <div class="panel-heading">
        <h2>Move Quality</h2>
      </div>
      ${renderQualityCounts(detail.quality_counts || {}, game)}
    </section>
    <div class="move-table-heading">
      <span>${escapeHtml(game.white || "White")}</span>
      <span>${escapeHtml(game.black || "Black")}</span>
    </div>
    <section class="move-list">
      ${renderMovePairs(moves)}
    </section>
  `;
  document.querySelector("#analyzeGameButton").addEventListener("click", async () => {
    showStatus("Analysis queued. You can keep browsing while it runs.", 0);
    try {
      await api(`/api/analysis/games/${gameId}?depth=${selectedDepth()}${profileAmpParam()}`, { method: "POST" });
      await loadAll();
      showStatus("Analysis queued.");
    } catch (error) {
      showStatus(error.message, 8000);
    }
  });
  document.querySelector("#analysisGameButton").addEventListener("click", async () => {
    await openGameAnalysisBoard(gameId);
  });
  document.querySelector("#deleteGameButton").addEventListener("click", async () => {
    await deleteGame(gameId);
  });
  bindAnalysisDetailInteractions();
  updateSelectedPly();
  setView("detail");
}

function renderMovePairs(moves) {
  const pairs = [];
  for (let index = 0; index < moves.length; index += 2) {
    pairs.push([moves[index], moves[index + 1]]);
  }
  return pairs.map(([whiteMove, blackMove]) => `
    <article class="move-pair-row">
      ${renderMoveCell(whiteMove, "white")}
      ${renderMoveCell(blackMove, "black")}
    </article>
  `).join("");
}

function renderMoveCell(move, color) {
  if (!move) {
    return `<div class="move-cell ${color} empty"></div>`;
  }
  const classification = move.classification || "pending";
  const loss = move.centipawn_loss == null ? "-" : move.centipawn_loss;
  return `
    <div class="move-cell ${color}" data-move-ply="${move.ply}">
      <div>
        <div class="move-san">${move.move_number}. ${escapeHtml(move.san)}</div>
        <div class="move-meta">Best ${escapeHtml(move.best_uci || "-")} · Eval ${formatEval(move.eval_after_cp, move.mate_after)}</div>
        ${move.clock_seconds == null ? "" : `<div class="move-meta">Clock ${formatClock(move.clock_seconds)}</div>`}
      </div>
      <span class="pill ${classificationClass(classification)}">${escapeHtml(classification)} ${loss}</span>
    </div>
  `;
}

function renderEvaluationGraph(history, summary, game = {}) {
  const userColor = userColorForGame(game);
  const points = history
    .filter((point) => point.eval_cp != null)
    .map((point) => ({ ...point, perspective_cp: perspectiveCp(point.eval_cp, userColor) }));
  if (!points.length) {
    return `<div class="stat-subtitle">Analyze this game to draw the evaluation graph.</div>`;
  }

  const width = 320;
  const height = 160;
  const pad = 18;
  const maxAbs = Math.max(200, Math.min(1000, ...points.map((point) => Math.abs(Number(point.perspective_cp)))));
  const xFor = (index) => points.length === 1
    ? width / 2
    : pad + (index * (width - pad * 2)) / (points.length - 1);
  const yFor = (cp) => {
    const clamped = Math.max(-maxAbs, Math.min(maxAbs, Number(cp)));
    return pad + ((maxAbs - clamped) * (height - pad * 2)) / (maxAbs * 2);
  };
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(index).toFixed(1)} ${yFor(point.perspective_cp).toFixed(1)}`).join(" ");
  const equalityY = yFor(0).toFixed(1);
  const areaPath = `${path} L ${xFor(points.length - 1).toFixed(1)} ${equalityY} L ${xFor(0).toFixed(1)} ${equalityY} Z`;
  const last = points[points.length - 1];
  const swings = summary.largest_swings || [];
  const peakUser = Math.max(...points.map((point) => Number(point.perspective_cp)));
  const peakOpponent = Math.min(...points.map((point) => Number(point.perspective_cp)));

  return `
    <div class="eval-graph-wrap">
      <svg class="eval-graph" viewBox="0 0 ${width} ${height}" role="img" aria-label="Engine evaluation graph">
        <rect class="eval-band-user" x="${pad}" y="${pad}" width="${width - pad * 2}" height="${equalityY - pad}"></rect>
        <rect class="eval-band-opponent" x="${pad}" y="${equalityY}" width="${width - pad * 2}" height="${height - pad - equalityY}"></rect>
        <path class="eval-area" d="${areaPath}"></path>
        <line class="eval-grid-line" x1="${pad}" y1="${equalityY}" x2="${width - pad}" y2="${equalityY}"></line>
        <path class="eval-line" d="${path}"></path>
        ${points.map((point, index) => `
          <circle
            class="eval-hit-target"
            data-eval-ply="${point.ply}"
            cx="${xFor(index).toFixed(1)}"
            cy="${yFor(point.perspective_cp).toFixed(1)}"
            r="7"
          >
            <title>${moveLabel(point)} · ${playerAdvantageLabel(point.eval_cp, point.mate, game)}</title>
          </circle>
        `).join("")}
      </svg>
      <div class="eval-legend">
        <span>You +</span>
        <strong>${playerAdvantageLabel(last.eval_cp, last.mate, game)}</strong>
        <span>Opponent +</span>
      </div>
      <div class="eval-summary-grid">
        <div><span>Peak You</span><strong>${perspectiveAdvantageLabel(peakUser)}</strong></div>
        <div><span>Peak Opponent</span><strong>${perspectiveAdvantageLabel(peakOpponent)}</strong></div>
        <div><span>Final</span><strong>${playerAdvantageLabel(last.eval_cp, last.mate, game)}</strong></div>
      </div>
      <div class="eval-selected" id="evalSelected"></div>
      ${swings.length ? `
        <div class="swing-list">
          <div class="mini-heading">Largest Swings</div>
          ${swings.map((swing) => `
            <button class="swing-button" data-select-ply="${swing.ply}">
              <span>${escapeHtml(moveLabel(swing))}</span>
              <strong>${formatSignedCp(swing.delta_cp)}</strong>
            </button>
          `).join("")}
        </div>
      ` : ""}
    </div>
  `;
}

function renderBoardExplorer(moves, startingFen) {
  return renderBoardComponent({
    id: "gameExplorer",
    mode: "game",
    title: "Explorer",
    startingFen,
    positions: moves,
    selectedPly: state.selectedPly,
    orientation: state.boardOrientations.gameExplorer,
    emptyText: "Select a move to inspect the position.",
    includeTimeline: true,
  });
}

function bindAnalysisDetailInteractions() {
  document.querySelectorAll("[data-eval-ply], [data-select-ply], [data-move-ply], [data-explorer-ply]").forEach((node) => {
    node.addEventListener("click", () => {
      const ply = Number(node.dataset.evalPly || node.dataset.selectPly || node.dataset.movePly || node.dataset.explorerPly);
      if (!Number.isNaN(ply)) {
        state.selectedPly = ply;
        updateSelectedPly();
      }
    });
  });
  document.querySelectorAll('[data-board-id="gameExplorer"][data-board-nav]').forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedPly = nextExplorerPly(button.dataset.boardNav);
      updateSelectedPly();
    });
  });
}

function updateSelectedPly() {
  const selected = state.selectedPositions.find((position) => Number(position.ply) === Number(state.selectedPly));
  document.querySelectorAll("[data-eval-ply], [data-move-ply], [data-select-ply], [data-explorer-ply]").forEach((node) => {
    const ply = Number(node.dataset.evalPly || node.dataset.movePly || node.dataset.selectPly || node.dataset.explorerPly);
    node.classList.toggle("selected", ply === Number(state.selectedPly));
  });
  updateExplorerBoard(selected);
  const panel = document.querySelector("#evalSelected");
  if (!panel) return;
  if (!selected) {
    panel.innerHTML = `
      <div>
        <div class="stat-title">Starting position</div>
        <div class="stat-subtitle">No move selected yet.</div>
      </div>
      <span class="pill">Start</span>
      <strong>-</strong>
    `;
    return;
  }
  panel.innerHTML = `
    <div>
      <div class="stat-title">${escapeHtml(moveLabel(selected))}</div>
      <div class="stat-subtitle">Best ${escapeHtml(selected.best_uci || "-")} · CPL ${selected.centipawn_loss == null ? "-" : selected.centipawn_loss}</div>
    </div>
    <span class="pill ${classificationClass(selected.classification)}">${escapeHtml(selected.classification || "unknown")}</span>
    <strong>${playerAdvantageLabel(selected.eval_after_cp ?? selected.eval_after_display_cp, selected.mate_after, state.selectedGame || {})}</strong>
  `;
}

function updateExplorerBoard(selected) {
  const fen = selected?.fen || selected?.fen_after || state.startingFen || state.selectedPositions[0]?.fen_before;
  updateBoardComponent({
    id: "gameExplorer",
    fen,
    selected,
    positions: state.selectedPositions,
    selectedPly: state.selectedPly,
    orientation: state.boardOrientations.gameExplorer,
  });

  const indicator = document.querySelector('[data-board-indicator="gameExplorer"]');
  if (indicator) {
    indicator.textContent = selected ? moveLabel(selected) : "Start";
  }

  const current = document.querySelector('[data-board-current="gameExplorer"]');
  if (!current) return;
  if (!selected) {
    current.innerHTML = `
      <div class="stat-title">Starting position</div>
      <div class="stat-subtitle">Use the arrows or tap a move below.</div>
    `;
    return;
  }
  current.innerHTML = `
    <div class="stat-title">${escapeHtml(moveLabel(selected))}</div>
    <div class="stat-subtitle">
      ${escapeHtml(capitalize(selected.color || selected.side || "Side"))} played ${escapeHtml(selected.san || selected.uci || "")}
      · Eval ${formatEval(selected.eval_after_cp, selected.mate_after)}
      ${selected.clock_seconds == null ? "" : `· Clock ${formatClock(selected.clock_seconds)}`}
    </div>
  `;
}

function renderBoardComponent(config) {
  const orientation = config.orientation || "white";
  const positions = config.positions || [];
  const timelineAttribute = config.timelineAttribute || "data-explorer-ply";
  return `
    <section class="panel board-panel" data-board-component="${escapeHtml(config.id)}" data-board-mode="${escapeHtml(config.mode || "game")}">
      <div class="panel-heading">
        <h2>${escapeHtml(config.title || "Board")}</h2>
        <span class="pill" data-board-indicator="${escapeHtml(config.id)}">${config.startingFen ? "Ready" : "No board"}</span>
      </div>
      <div class="board-layout">
        <div class="chessboard-wrap" data-board-orientation="${escapeHtml(orientation)}">
          <div class="board-rank-labels" data-board-ranks="${escapeHtml(config.id)}" aria-hidden="true">
            ${renderRankLabels(orientation)}
          </div>
          <div class="chessboard" id="chessboard-${escapeHtml(config.id)}" data-board-surface="${escapeHtml(config.id)}" aria-label="Chess board"></div>
          <div class="board-file-labels" data-board-files="${escapeHtml(config.id)}" aria-hidden="true">
            ${renderFileLabels(orientation)}
          </div>
        </div>
        <div class="explorer-side">
          <div class="explorer-current" data-board-current="${escapeHtml(config.id)}">${escapeHtml(config.emptyText || "Select a move.")}</div>
          <div class="explorer-controls" aria-label="Board navigation">
            <button class="nav-button" data-board-id="${escapeHtml(config.id)}" data-board-nav="start" title="Jump to beginning" aria-label="Jump to beginning">|&lt;</button>
            <button class="nav-button" data-board-id="${escapeHtml(config.id)}" data-board-nav="prev" title="Previous move" aria-label="Previous move">&lt;</button>
            <button class="nav-button" data-board-id="${escapeHtml(config.id)}" data-board-nav="next" title="Next move" aria-label="Next move">&gt;</button>
            <button class="nav-button" data-board-id="${escapeHtml(config.id)}" data-board-nav="end" title="Jump to end" aria-label="Jump to end">&gt;|</button>
          </div>
          ${config.includeBoardActions ? `
            <div class="board-extra-controls">
              <button class="secondary-button" data-board-id="${escapeHtml(config.id)}" data-board-action="reset">Reset</button>
              <button class="secondary-button" data-board-id="${escapeHtml(config.id)}" data-board-action="flip">Flip</button>
            </div>
          ` : ""}
          ${config.statusHtml || ""}
          ${config.includeTimeline ? `
            <div class="move-strip" aria-label="Move timeline">
              <button class="move-chip start" ${timelineAttribute}="0">Start</button>
              ${positions.map((move) => `
                <button class="move-chip ${escapeHtml(move.side || move.color || "")}" ${timelineAttribute}="${move.ply}">
                  <span>${escapeHtml(moveLabel(move))}</span>
                </button>
              `).join("")}
            </div>
          ` : ""}
        </div>
      </div>
    </section>
  `;
}

function updateBoardComponent(config) {
  const board = document.querySelector(`[data-board-surface="${config.id}"]`);
  if (!board) return;
  const orientation = config.orientation || "white";
  board.innerHTML = renderBoardSquares(config.fen, orientation, Boolean(config.allowInteraction));

  const ranks = document.querySelector(`[data-board-ranks="${config.id}"]`);
  if (ranks) ranks.innerHTML = renderRankLabels(orientation);
  const files = document.querySelector(`[data-board-files="${config.id}"]`);
  if (files) files.innerHTML = renderFileLabels(orientation);

  const maxPly = Math.max(0, ...(config.positions || []).map((move) => Number(move.ply) || 0));
  const currentPly = Number(config.selectedPly) || 0;
  document.querySelectorAll(`[data-board-id="${config.id}"][data-board-nav]`).forEach((button) => {
    const nav = button.dataset.boardNav;
    const atStart = currentPly <= 0;
    const atEnd = currentPly >= maxPly;
    button.disabled = (nav === "start" || nav === "prev") ? atStart : atEnd;
  });
  if (config.selectedSquare) {
    const selected = board.querySelector(`[data-board-square="${config.selectedSquare}"]`);
    selected?.classList.add("selected");
  }
  (config.legalMoves || []).forEach((move) => {
    if (move.from !== config.selectedSquare) return;
    const target = board.querySelector(`[data-board-square="${move.to}"]`);
    target?.classList.add("legal-target");
    if (pieceAt(config.fen, move.to)) {
      target?.classList.add("legal-capture");
    }
  });
}

function nextExplorerPly(action) {
  const maxPly = Math.max(0, ...state.selectedPositions.map((move) => Number(move.ply) || 0));
  const current = Number(state.selectedPly) || 0;
  if (action === "start") return 0;
  if (action === "end") return maxPly;
  if (action === "prev") return Math.max(0, current - 1);
  if (action === "next") return Math.min(maxPly, current + 1);
  return current;
}

function renderBoardSquares(fen, orientation = "white", interactive = false) {
  if (!fen) {
    return `<div class="board-empty">No FEN available</div>`;
  }
  const boardPart = String(fen).split(" ")[0];
  const rows = boardPart.split("/");
  if (rows.length !== 8) {
    return `<div class="board-empty">Invalid board position</div>`;
  }
  const parsedRows = rows.map((row) => {
    const squares = [];
    for (const token of row) {
      const empty = Number(token);
      if (Number.isInteger(empty) && empty > 0) {
        for (let count = 0; count < empty; count += 1) {
          squares.push("");
        }
      } else {
        squares.push(token);
      }
    }
    return squares.slice(0, 8);
  });
  const files = ["a", "b", "c", "d", "e", "f", "g", "h"];
  const squareRows = parsedRows.map((row, rankIndex) => {
    const rank = 8 - rankIndex;
    return row.map((piece, fileIndex) => ({
      piece,
      square: `${files[fileIndex]}${rank}`,
      fileIndex,
      rank,
    }));
  });
  const orientedRows = orientation === "black"
    ? squareRows.slice().reverse().map((row) => row.slice().reverse())
    : squareRows;
  return orientedRows.map((row) => {
    return row.map((item) => {
      const isLight = (item.fileIndex + item.rank) % 2 === 0;
      return `
        <div
          class="board-square ${isLight ? "light" : "dark"} ${interactive ? "interactive" : ""}"
          data-board-square="${escapeHtml(item.square)}"
          ${interactive ? `role="button" aria-label="${escapeHtml(item.square)}"` : ""}
        >
          ${item.piece ? renderPieceSvg(item.piece) : ""}
        </div>
      `;
    }).join("");
  }).join("");
}

function renderRankLabels(orientation = "white") {
  const ranks = orientation === "black" ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1];
  return ranks.map((rank) => `<span>${rank}</span>`).join("");
}

function renderFileLabels(orientation = "white") {
  const files = orientation === "black" ? ["h", "g", "f", "e", "d", "c", "b", "a"] : ["a", "b", "c", "d", "e", "f", "g", "h"];
  return files.map((file) => `<span>${file}</span>`).join("");
}

function renderPieceSvg(piece) {
  const white = piece === piece.toUpperCase();
  const type = piece.toLowerCase();
  const title = `${white ? "White" : "Black"} ${pieceName(type)}`;
  const src = `/static/pieces/cburnett/${white ? "w" : "b"}${type}.svg`;
  return `
    <img class="piece piece-svg ${white ? "white-piece" : "black-piece"}" src="${src}" alt="${title}" draggable="false" />
  `;
}

function pieceName(type) {
  return {
    k: "king",
    q: "queen",
    r: "rook",
    b: "bishop",
    n: "knight",
    p: "pawn",
  }[type] || "piece";
}

async function openBlankAnalysisBoard() {
  const workspace = await api("/api/board/position", {
    method: "POST",
    body: JSON.stringify({ moves: [], starting_fen: STARTING_FEN, selected_ply: 0 }),
  });
  applyAnalysisWorkspace(workspace, null);
  renderAnalysisBoard();
  els.backFromAnalysis.hidden = true;
  setView("analysis");
}

async function openGameAnalysisBoard(gameId) {
  const workspace = await api(`/api/board/games/${gameId}${profileParam()}`);
  applyAnalysisWorkspace(workspace, workspace.game || null);
  renderAnalysisBoard();
  els.backFromAnalysis.hidden = false;
  setView("analysis");
}

function applyAnalysisWorkspace(workspace, sourceGame = undefined) {
  state.analysisBoard = {
    ...workspace,
    sourceGame: sourceGame === undefined ? state.analysisBoard?.sourceGame || null : sourceGame,
    selectedSquare: null,
  };
}

function renderAnalysisBoard() {
  const boardState = state.analysisBoard || {
    starting_fen: STARTING_FEN,
    fen: STARTING_FEN,
    selected_ply: 0,
    moves: [],
    move_history: [],
    positions: [],
    legal_moves: [],
    turn: "white",
  };
  const source = boardState.sourceGame;
  els.analysisBoardMount.innerHTML = renderBoardComponent({
    id: "analysisBoard",
    mode: "analysis",
    title: source ? `${source.white || "White"} vs ${source.black || "Black"}` : "Analysis Board",
    startingFen: boardState.starting_fen || STARTING_FEN,
    positions: boardState.move_history || [],
    selectedPly: boardState.selected_ply || 0,
    orientation: state.boardOrientations.analysisBoard,
    emptyText: "Tap a piece to make a legal move.",
    includeTimeline: true,
    includeBoardActions: true,
    allowInteraction: true,
    timelineAttribute: "data-analysis-ply",
    statusHtml: renderAnalysisStatus(boardState),
  });
  updateAnalysisBoard();
  bindAnalysisBoardInteractions();
}

function renderAnalysisStatus(boardState) {
  const engine = boardState.engine;
  const engineText = !engine
    ? "Engine off"
    : engine.status === "ok"
      ? `${formatEval(engine.score_cp, engine.mate)} · Best ${engine.best_move || "-"}`
      : "Engine unavailable";
  return `
    <div class="analysis-status-grid">
      <div>
        <span class="metric-label">Turn</span>
        <strong>${escapeHtml(capitalize(boardState.turn || "white"))}</strong>
      </div>
      <div>
        <span class="metric-label">Engine</span>
        <strong>${escapeHtml(engineText)}</strong>
      </div>
    </div>
  `;
}

function updateAnalysisBoard() {
  const boardState = state.analysisBoard;
  if (!boardState) return;
  const selected = (boardState.positions || []).find((position) => Number(position.ply) === Number(boardState.selected_ply));
  updateBoardComponent({
    id: "analysisBoard",
    fen: boardState.fen,
    selected,
    positions: boardState.move_history || [],
    selectedPly: boardState.selected_ply || 0,
    orientation: state.boardOrientations.analysisBoard,
    allowInteraction: true,
    selectedSquare: boardState.selectedSquare,
    legalMoves: boardState.legal_moves || [],
  });
  document.querySelectorAll("[data-analysis-ply]").forEach((node) => {
    node.classList.toggle("selected", Number(node.dataset.analysisPly) === Number(boardState.selected_ply));
  });

  const indicator = document.querySelector('[data-board-indicator="analysisBoard"]');
  if (indicator) indicator.textContent = selected?.ply ? moveLabel(selected) : "Start";

  const current = document.querySelector('[data-board-current="analysisBoard"]');
  if (!current) return;
  current.innerHTML = `
    <div class="stat-title">${selected?.ply ? escapeHtml(moveLabel(selected)) : "Starting position"}</div>
    <div class="stat-subtitle">
      ${escapeHtml(positionStatusText(boardState))}
    </div>
  `;
}

function bindAnalysisBoardInteractions() {
  document.querySelectorAll('[data-board-id="analysisBoard"][data-board-nav]').forEach((button) => {
    button.addEventListener("click", async () => {
      await navigateAnalysisBoard(button.dataset.boardNav);
    });
  });
  document.querySelectorAll('[data-board-id="analysisBoard"][data-board-action]').forEach((button) => {
    button.addEventListener("click", async () => {
      if (button.dataset.boardAction === "reset") {
        await resetAnalysisBoard();
      } else if (button.dataset.boardAction === "flip") {
        state.boardOrientations.analysisBoard = state.boardOrientations.analysisBoard === "white" ? "black" : "white";
        updateAnalysisBoard();
      }
    });
  });
  document.querySelectorAll("[data-analysis-ply]").forEach((node) => {
    node.addEventListener("click", async () => {
      await selectAnalysisPly(Number(node.dataset.analysisPly));
    });
  });
  document.querySelector('[data-board-surface="analysisBoard"]')?.addEventListener("click", async (event) => {
    const square = event.target.closest("[data-board-square]")?.dataset.boardSquare;
    if (square) {
      await handleAnalysisSquare(square);
    }
  });
}

async function navigateAnalysisBoard(action) {
  const boardState = state.analysisBoard;
  if (!boardState) return;
  const maxPly = Math.max(0, ...(boardState.move_history || []).map((move) => Number(move.ply) || 0));
  const current = Number(boardState.selected_ply) || 0;
  const next = action === "start"
    ? 0
    : action === "end"
      ? maxPly
      : action === "prev"
        ? Math.max(0, current - 1)
        : action === "next"
          ? Math.min(maxPly, current + 1)
          : current;
  await selectAnalysisPly(next);
}

async function selectAnalysisPly(ply) {
  const boardState = state.analysisBoard;
  if (!boardState) return;
  const workspace = await api("/api/board/position", {
    method: "POST",
    body: JSON.stringify({
      moves: boardState.moves || [],
      starting_fen: boardState.starting_fen || STARTING_FEN,
      selected_ply: Math.max(0, Number(ply) || 0),
    }),
  });
  applyAnalysisWorkspace(workspace);
  renderAnalysisBoard();
}

async function resetAnalysisBoard() {
  const workspace = await api("/api/board/position", {
    method: "POST",
    body: JSON.stringify({ moves: [], starting_fen: STARTING_FEN, selected_ply: 0 }),
  });
  applyAnalysisWorkspace(workspace, null);
  renderAnalysisBoard();
}

async function handleAnalysisSquare(square) {
  const boardState = state.analysisBoard;
  if (!boardState) return;
  const selected = boardState.selectedSquare;
  const clickedPiece = pieceAt(boardState.fen, square);
  const turnColor = boardState.turn || "white";
  if (!selected) {
    if (pieceBelongsToTurn(clickedPiece, turnColor)) {
      boardState.selectedSquare = square;
      updateAnalysisBoard();
    }
    return;
  }

  const legal = legalMoveForSquares(selected, square, boardState.legal_moves || []);
  if (legal) {
    const workspace = await api("/api/board/move", {
      method: "POST",
      body: JSON.stringify({
        move: legal.uci,
        moves: boardState.moves || [],
        starting_fen: boardState.starting_fen || STARTING_FEN,
        selected_ply: boardState.selected_ply || 0,
      }),
    });
    applyAnalysisWorkspace(workspace);
    renderAnalysisBoard();
    return;
  }

  if (pieceBelongsToTurn(clickedPiece, turnColor)) {
    boardState.selectedSquare = square;
  } else {
    boardState.selectedSquare = null;
  }
  updateAnalysisBoard();
}

function legalMoveForSquares(from, to, legalMoves) {
  const matches = legalMoves.filter((move) => move.from === from && move.to === to);
  if (!matches.length) return null;
  return matches.find((move) => move.promotion === "q") || matches[0];
}

function pieceBelongsToTurn(piece, turn) {
  if (!piece) return false;
  const isWhite = piece === piece.toUpperCase();
  return (turn === "white" && isWhite) || (turn === "black" && !isWhite);
}

function pieceAt(fen, square) {
  if (!fen || !square) return "";
  const file = square.charCodeAt(0) - 97;
  const rank = Number(square.slice(1));
  if (file < 0 || file > 7 || rank < 1 || rank > 8) return "";
  const rows = String(fen).split(" ")[0].split("/");
  const row = rows[8 - rank];
  if (!row) return "";
  let currentFile = 0;
  for (const token of row) {
    const empty = Number(token);
    if (Number.isInteger(empty) && empty > 0) {
      currentFile += empty;
    } else {
      if (currentFile === file) return token;
      currentFile += 1;
    }
  }
  return "";
}

function positionStatusText(boardState) {
  if (boardState.is_checkmate) return "Checkmate";
  if (boardState.is_stalemate) return "Stalemate";
  if (boardState.result) return `Game over ${boardState.result}`;
  if (boardState.is_check) return `${capitalize(boardState.turn)} to move, in check`;
  return `${capitalize(boardState.turn || "white")} to move`;
}

async function ensureOpeningExplorer() {
  if (state.openingExplorer) {
    renderOpeningExplorer();
    return;
  }
  const workspace = await api("/api/board/position", {
    method: "POST",
    body: JSON.stringify({ moves: [], starting_fen: STARTING_FEN, selected_ply: 0 }),
  });
  applyOpeningExplorerWorkspace(workspace, "Opening not identified");
  renderOpeningExplorer();
}

function applyOpeningExplorerWorkspace(workspace, openingName = undefined) {
  state.openingExplorer = {
    ...workspace,
    openingName: openingName === undefined ? state.openingExplorer?.openingName || "Opening not identified" : openingName,
    selectedSquare: null,
  };
}

async function refreshOpeningName() {
  const explorer = state.openingExplorer;
  if (!explorer) return;
  const sans = (explorer.move_history || []).map((move) => move.san).filter(Boolean);
  if (!sans.length) {
    explorer.openingName = "Opening not identified";
    return;
  }
  const result = await api("/api/openings/detect", {
    method: "POST",
    body: JSON.stringify({ sans }),
  });
  explorer.openingName = result.opening || "Opening not identified";
}

function renderOpeningExplorer() {
  const explorer = state.openingExplorer;
  if (!explorer || !els.openingExplorerMount) return;
  els.openingExplorerName.textContent = explorer.openingName || "Opening not identified";
  els.openingExplorerPly.textContent = explorer.selected_ply ? `${explorer.selected_ply} ply` : "Start";
  els.openingExplorerMount.innerHTML = renderBoardComponent({
    id: "openingExplorer",
    mode: "opening_explorer",
    title: "Board",
    startingFen: explorer.starting_fen || STARTING_FEN,
    positions: explorer.move_history || [],
    selectedPly: explorer.selected_ply || 0,
    orientation: state.boardOrientations.openingExplorer,
    emptyText: "Tap moves to identify the opening.",
    includeTimeline: true,
    includeBoardActions: true,
    allowInteraction: true,
    timelineAttribute: "data-opening-ply",
    statusHtml: `
      <div class="analysis-status-grid">
        <div>
          <span class="metric-label">Turn</span>
          <strong>${escapeHtml(capitalize(explorer.turn || "white"))}</strong>
        </div>
        <div>
          <span class="metric-label">Position</span>
          <strong>${escapeHtml(positionStatusText(explorer))}</strong>
        </div>
      </div>
    `,
  });
  updateOpeningExplorer();
  bindOpeningExplorerInteractions();
}

function updateOpeningExplorer() {
  const explorer = state.openingExplorer;
  if (!explorer) return;
  const selected = (explorer.positions || []).find((position) => Number(position.ply) === Number(explorer.selected_ply));
  updateBoardComponent({
    id: "openingExplorer",
    fen: explorer.fen,
    selected,
    positions: explorer.move_history || [],
    selectedPly: explorer.selected_ply || 0,
    orientation: state.boardOrientations.openingExplorer,
    allowInteraction: true,
    selectedSquare: explorer.selectedSquare,
    legalMoves: explorer.legal_moves || [],
  });
  document.querySelectorAll("[data-opening-ply]").forEach((node) => {
    node.classList.toggle("selected", Number(node.dataset.openingPly) === Number(explorer.selected_ply));
  });
  const indicator = document.querySelector('[data-board-indicator="openingExplorer"]');
  if (indicator) indicator.textContent = selected?.ply ? moveLabel(selected) : "Start";
  const current = document.querySelector('[data-board-current="openingExplorer"]');
  if (current) {
    current.innerHTML = `
      <div class="stat-title">${selected?.ply ? escapeHtml(moveLabel(selected)) : "Starting position"}</div>
      <div class="stat-subtitle">${escapeHtml(positionStatusText(explorer))}</div>
    `;
  }
}

function bindOpeningExplorerInteractions() {
  document.querySelectorAll('[data-board-id="openingExplorer"][data-board-nav]').forEach((button) => {
    button.addEventListener("click", async () => {
      await navigateOpeningExplorer(button.dataset.boardNav);
    });
  });
  document.querySelectorAll('[data-board-id="openingExplorer"][data-board-action]').forEach((button) => {
    button.addEventListener("click", async () => {
      if (button.dataset.boardAction === "reset") {
        await resetOpeningExplorer();
      } else if (button.dataset.boardAction === "flip") {
        state.boardOrientations.openingExplorer = state.boardOrientations.openingExplorer === "white" ? "black" : "white";
        updateOpeningExplorer();
      }
    });
  });
  document.querySelectorAll("[data-opening-ply]").forEach((node) => {
    node.addEventListener("click", async () => {
      await selectOpeningPly(Number(node.dataset.openingPly));
    });
  });
  document.querySelector('[data-board-surface="openingExplorer"]')?.addEventListener("click", async (event) => {
    const square = event.target.closest("[data-board-square]")?.dataset.boardSquare;
    if (square) {
      await handleOpeningSquare(square);
    }
  });
}

async function navigateOpeningExplorer(action) {
  const explorer = state.openingExplorer;
  if (!explorer) return;
  const maxPly = Math.max(0, ...(explorer.move_history || []).map((move) => Number(move.ply) || 0));
  const current = Number(explorer.selected_ply) || 0;
  const next = action === "start"
    ? 0
    : action === "end"
      ? maxPly
      : action === "prev"
        ? Math.max(0, current - 1)
        : action === "next"
          ? Math.min(maxPly, current + 1)
          : current;
  await selectOpeningPly(next);
}

async function selectOpeningPly(ply) {
  const explorer = state.openingExplorer;
  if (!explorer) return;
  const workspace = await api("/api/board/position", {
    method: "POST",
    body: JSON.stringify({
      moves: explorer.moves || [],
      starting_fen: explorer.starting_fen || STARTING_FEN,
      selected_ply: Math.max(0, Number(ply) || 0),
    }),
  });
  applyOpeningExplorerWorkspace(workspace);
  await refreshOpeningName();
  renderOpeningExplorer();
}

async function resetOpeningExplorer() {
  const workspace = await api("/api/board/position", {
    method: "POST",
    body: JSON.stringify({ moves: [], starting_fen: STARTING_FEN, selected_ply: 0 }),
  });
  applyOpeningExplorerWorkspace(workspace, "Opening not identified");
  renderOpeningExplorer();
}

async function handleOpeningSquare(square) {
  const explorer = state.openingExplorer;
  if (!explorer) return;
  const selected = explorer.selectedSquare;
  const clickedPiece = pieceAt(explorer.fen, square);
  const turnColor = explorer.turn || "white";
  if (!selected) {
    if (pieceBelongsToTurn(clickedPiece, turnColor)) {
      explorer.selectedSquare = square;
      updateOpeningExplorer();
    }
    return;
  }

  const legal = legalMoveForSquares(selected, square, explorer.legal_moves || []);
  if (legal) {
    const workspace = await api("/api/board/move", {
      method: "POST",
      body: JSON.stringify({
        move: legal.uci,
        moves: explorer.moves || [],
        starting_fen: explorer.starting_fen || STARTING_FEN,
        selected_ply: explorer.selected_ply || 0,
      }),
    });
    applyOpeningExplorerWorkspace(workspace);
    await refreshOpeningName();
    renderOpeningExplorer();
    return;
  }

  if (pieceBelongsToTurn(clickedPiece, turnColor)) {
    explorer.selectedSquare = square;
  } else {
    explorer.selectedSquare = null;
  }
  updateOpeningExplorer();
}

function defaultSelectedPly(moves) {
  const analyzed = [...moves].reverse().find((move) => move.eval_after_display_cp != null);
  return analyzed ? Number(analyzed.ply) : Number(moves[0]?.ply || 0);
}

function renderQualityCounts(counts, game) {
  const buckets = ["good", "imprecision", "inaccuracy", "mistake", "blunder", "unknown"];
  const whiteCounts = counts.white || {};
  const blackCounts = counts.black || {};
  return `
    <div class="quality-grid">
      <div class="quality-player">${escapeHtml(game.white || "White")}</div>
      <div class="quality-player">${escapeHtml(game.black || "Black")}</div>
      ${buckets.map((bucket) => `
        <div class="quality-row">
          <span>${escapeHtml(capitalize(bucket))}</span>
          <strong>${whiteCounts[bucket] || 0}</strong>
        </div>
        <div class="quality-row">
          <span>${escapeHtml(capitalize(bucket))}</span>
          <strong>${blackCounts[bucket] || 0}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

async function deleteGame(gameId) {
  const confirmed = await confirmDelete(gameId);
  if (!confirmed) return;
  try {
    await api(`/api/games/${gameId}${profileParam()}`, { method: "DELETE" });
    showStatus("Game deleted.");
    state.selectedGameId = null;
    await loadAll();
    setView("games");
  } catch (error) {
    showStatus(error.message, 8000);
  }
}

function confirmDelete(gameId) {
  const game = state.games.find((item) => String(item.id) === String(gameId));
  els.confirmBody.textContent = game
    ? `Delete ${game.white || "White"} vs ${game.black || "Black"} and its analysis?`
    : "Delete this game and its analysis?";
  state.pendingDeleteGameId = gameId;
  els.confirmModal.hidden = false;
  return new Promise((resolve) => {
    const cleanup = (value) => {
      els.confirmModal.hidden = true;
      state.pendingDeleteGameId = null;
      els.cancelDeleteButton.removeEventListener("click", onCancel);
      els.confirmDeleteButton.removeEventListener("click", onConfirm);
      resolve(value);
    };
    const onCancel = () => cleanup(false);
    const onConfirm = () => cleanup(true);
    els.cancelDeleteButton.addEventListener("click", onCancel);
    els.confirmDeleteButton.addEventListener("click", onConfirm);
  });
}

async function importGames() {
  const files = Array.from(els.fileInput.files || []);
  let imported = 0;
  let duplicates = 0;
  let errors = [];

  if (files.length) {
    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      const result = await api(`/api/imports/pgn-file${profileParam()}`, { method: "POST", body: form });
      imported += result.imported || 0;
      duplicates += result.duplicates || 0;
      errors = errors.concat(result.errors || []);
    }
  }

  if (els.pgnInput.value.trim()) {
    const result = await api("/api/imports/pgn", {
      method: "POST",
      body: JSON.stringify({ pgn: els.pgnInput.value, profile_id: Number(state.activeProfile.id) }),
    });
    imported += result.imported || 0;
    duplicates += result.duplicates || 0;
    errors = errors.concat(result.errors || []);
  }

  if (!files.length && !els.pgnInput.value.trim()) {
    showStatus("Choose a PGN file or paste PGN text.");
    return;
  }

  els.pgnInput.value = "";
  els.fileInput.value = "";
  showStatus(`Imported ${imported} games. Skipped ${duplicates} duplicates. ${errors.length} warnings.`);
  await loadAll();
  setView("games");
}

async function syncChessCom(options = {}) {
  const username = String(options.username || els.chesscomUsername.value || "").trim();
  if (!username) {
    showStatus("Enter a Chess.com username.");
    return;
  }
  const days = Math.max(1, Math.min(365, Number(els.syncLimit.value) || state.activeProfile?.chesscom_sync_days || 7));
  showStatus(options.auto ? `Refreshing and syncing ${username}.` : `Syncing the last ${days} days from Chess.com.`, 0);
  const result = await api("/api/chesscom/sync", {
    method: "POST",
    body: JSON.stringify({
      username,
      days,
      force: els.syncForce.checked,
      profile_id: Number(state.activeProfile.id),
    }),
  });
  await rememberSyncPreferences(username, days);
  showStatus(`Synced ${result.archives} archives: ${result.imported} new, ${result.duplicates} duplicates.`);
  await loadAll();
  if (!options.auto) setView("games");
}

async function rememberSyncPreferences(username, days) {
  if (!state.activeProfile?.id) return;
  const profile = await api(`/api/profiles/${state.activeProfile.id}/sync-preferences`, {
    method: "PUT",
    body: JSON.stringify({
      chesscom_username: username,
      chesscom_sync_days: days,
    }),
  });
  state.activeProfile = profile;
  localStorage.setItem("activeProfileId", String(profile.id));
}

function renderSyncHistory() {
  if (!els.syncHistory) return;
  const syncs = state.syncs || [];
  if (!syncs.length) {
    els.syncHistory.innerHTML = `<div class="stat-subtitle">No Chess.com syncs yet.</div>`;
    return;
  }
  els.syncHistory.innerHTML = syncs.slice(0, 5).map((sync) => `
    <div class="stat-row">
      <div>
        <div class="stat-title">${escapeHtml(sync.username)}</div>
        <div class="stat-subtitle">${archiveLabel(sync.archive_url)} · ${escapeHtml(sync.status)} · ${sync.synced_at}</div>
      </div>
      <span class="pill">${sync.imported}+${sync.duplicates}</span>
    </div>
  `).join("");
}

function statusPill(game) {
  const status = game.analysis_status || "not_analyzed";
  const cls = status === "complete" ? "good" : status === "failed" ? "bad" : "warn";
  return `<span class="pill ${cls}">${escapeHtml(status.replace("_", " "))}</span>`;
}

function classificationClass(classification) {
  if (classification === "blunder") return "bad";
  if (classification === "mistake" || classification === "inaccuracy" || classification === "imprecision") return "warn";
  if (classification === "good") return "good";
  return "";
}

function moveLabel(point) {
  const suffix = point.side === "black" || point.color === "black" ? "..." : ".";
  return `${point.move_number}${suffix} ${point.san || ""}`.trim();
}

function advantageLabel(cp, mate) {
  if (mate != null) {
    if (mate === 0) return "Mate";
    return mate > 0 ? `White M${mate}` : `Black M${Math.abs(mate)}`;
  }
  if (cp == null) return "-";
  const value = Number(cp);
  if (Math.abs(value) >= 9500) return value > 0 ? "White mate" : "Black mate";
  if (Math.abs(value) < 25) return "Equal";
  return value > 0 ? `White +${(value / 100).toFixed(2)}` : `Black +${Math.abs(value / 100).toFixed(2)}`;
}

function playerAdvantageLabel(cp, mate, gameOrMove = {}) {
  const userColor = userColorForGame(gameOrMove);
  const perspective = perspectiveCp(cp, userColor);
  if (mate != null) {
    const userMate = userColor === "black" ? -Number(mate) : Number(mate);
    if (userMate === 0) return "Mate";
    return userMate > 0 ? `You M${userMate}` : `Opponent M${Math.abs(userMate)}`;
  }
  if (perspective == null) return "-";
  const value = Number(perspective);
  if (Math.abs(value) >= 9500) return value > 0 ? "You mate" : "Opponent mate";
  if (Math.abs(value) < 25) return "Equal";
  return value > 0 ? `You +${(value / 100).toFixed(2)}` : `Opponent +${Math.abs(value / 100).toFixed(2)}`;
}

function perspectiveAdvantageLabel(cp) {
  if (cp == null) return "-";
  const value = Number(cp);
  if (Math.abs(value) >= 9500) return value > 0 ? "You mate" : "Opponent mate";
  if (Math.abs(value) < 25) return "Equal";
  return value > 0 ? `You +${(value / 100).toFixed(2)}` : `Opponent +${Math.abs(value / 100).toFixed(2)}`;
}

function perspectiveCp(cp, userColor) {
  if (cp == null) return null;
  const value = Number(cp);
  if (!Number.isFinite(value)) return null;
  return userColor === "black" ? -value : value;
}

function userColorForGame(game = {}) {
  if (game.player_color) return game.player_color;
  const candidates = [
    state.activeProfile?.chesscom_username,
    state.dashboard?.player,
    state.activeProfile?.name,
    inferredPrimaryPlayer(),
  ].map((value) => String(value || "").trim().toLowerCase()).filter(Boolean);
  if (!candidates.length) return "white";
  if (candidates.includes(String(game.white || "").trim().toLowerCase())) return "white";
  if (candidates.includes(String(game.black || "").trim().toLowerCase())) return "black";
  return "white";
}

function inferredPrimaryPlayer() {
  const counts = new Map();
  (state.games || []).forEach((game) => {
    [game.white, game.black].forEach((name) => {
      const key = String(name || "").trim();
      if (!key) return;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
  });
  let bestName = "";
  let bestCount = 0;
  counts.forEach((count, name) => {
    if (count > bestCount) {
      bestName = name;
      bestCount = count;
    }
  });
  return bestCount > 1 ? bestName : "";
}

function formatSignedCp(cp) {
  if (cp == null) return "-";
  const value = Number(cp);
  if (Math.abs(value) >= 9500) return "Mate swing";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value / 100).toFixed(2)}`;
}

function formatEval(cp, mate) {
  if (mate != null) return `M${mate}`;
  if (cp == null) return "-";
  return (cp / 100).toFixed(2);
}

function formatClock(seconds) {
  const total = Math.max(0, Number(seconds || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = Math.floor(total % 60).toString().padStart(2, "0");
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs}`;
  }
  return `${minutes}:${secs}`;
}

function formatNumber(value) {
  return value == null ? "-" : value;
}

function capitalize(value) {
  return String(value || "").slice(0, 1).toUpperCase() + String(value || "").slice(1);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function archiveLabel(url) {
  const match = String(url || "").match(/games\/(\d{4})\/(\d{2})/);
  if (!match) return "Archive";
  return `${match[1]}-${match[2]}`;
}

function accuracyLabel(game) {
  if (game.acpl == null) return "Accuracy -";
  return `Accuracy ${Math.max(0, Math.min(100, 100 - Number(game.acpl) / 3)).toFixed(1)}%`;
}

function trashIcon() {
  return `
    <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18">
      <path d="M9 3h6l1 2h4v2H4V5h4l1-2Zm-2 6h10l-1 12H8L7 9Zm3 2v8h2v-8h-2Zm4 0v8h2v-8h-2Z" fill="currentColor"></path>
    </svg>
  `;
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
}

els.navButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    setView(button.dataset.view);
  });
});

els.startOpeningExplorerButton.addEventListener("click", async () => {
  await ensureOpeningExplorer();
  setView("openingExplorer");
});

els.refreshButton.addEventListener("click", async () => {
  const username = (els.chesscomUsername.value || state.activeProfile?.chesscom_username || "").trim();
  if (username) {
    await syncChessCom({ username, auto: true });
    return;
  }
  await loadAll();
  showStatus("Refreshed.");
});

els.themeToggleButton.addEventListener("click", () => {
  state.theme = state.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = state.theme;
  localStorage.setItem("theme", state.theme);
  updateThemeButton();
});

function updateThemeButton() {
  els.themeToggleButton.textContent = state.theme === "dark" ? "Light Mode" : "Dark Mode";
  els.themeToggleButton.setAttribute("aria-label", state.theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
}

els.importButton.addEventListener("click", async () => {
  try {
    await importGames();
  } catch (error) {
    showStatus(error.message, 8000);
  }
});

els.syncButton.addEventListener("click", async () => {
  try {
    await syncChessCom();
  } catch (error) {
    showStatus(error.message, 10000);
  }
});

els.syncLimit.addEventListener("change", async () => {
  try {
    await rememberSyncPreferences(els.chesscomUsername.value.trim(), Number(els.syncLimit.value) || 7);
    showStatus("Sync window saved.");
  } catch (error) {
    showStatus(error.message, 8000);
  }
});

els.chesscomUsername.addEventListener("change", async () => {
  const username = els.chesscomUsername.value.trim();
  if (!username) return;
  try {
    await rememberSyncPreferences(username, Number(els.syncLimit.value) || 7);
    showStatus("Chess.com username saved.");
  } catch (error) {
    showStatus(error.message, 8000);
  }
});

els.searchInput.addEventListener("input", (event) => {
  state.search = event.target.value;
  renderGames();
});

els.filterToggleButton.addEventListener("click", () => {
  state.filtersOpen = !state.filtersOpen;
  renderGames();
});

els.timeFilterSelect.addEventListener("change", (event) => {
  state.timeFilter = event.target.value;
  renderGames();
});

els.sortSelect.addEventListener("change", (event) => {
  state.sortBy = event.target.value;
  renderGames();
});

els.openingSortSelect.addEventListener("change", async (event) => {
  state.openingSortBy = event.target.value;
  state.openingStats = await api(`/api/openings?sort_by=${encodeURIComponent(state.openingSortBy)}${profileAmpParam()}`);
  renderOpeningStats();
});

els.profileSelect.addEventListener("change", async (event) => {
  const profileId = Number(event.target.value);
  const profile = await api("/api/profiles/active", {
    method: "PUT",
    body: JSON.stringify({ profile_id: profileId }),
  });
  state.activeProfile = profile;
  localStorage.setItem("activeProfileId", String(profile.id));
  state.selectedGameId = null;
  state.selectedGame = null;
  setView("home");
  await loadAll();
});

els.createProfileButton.addEventListener("click", () => {
  els.newProfileName.value = "";
  els.profileModal.hidden = false;
  els.newProfileName.focus();
});

els.cancelProfileButton.addEventListener("click", () => {
  els.profileModal.hidden = true;
});

els.saveProfileButton.addEventListener("click", async () => {
  const name = els.newProfileName.value.trim();
  if (!name) {
    showStatus("Profile name is required.");
    return;
  }
  try {
    const profile = await api("/api/profiles", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    state.activeProfile = profile;
    localStorage.setItem("activeProfileId", String(profile.id));
    els.profileModal.hidden = true;
    setView("home");
    await loadAll();
    showStatus(`Switched to ${profile.name}.`);
  } catch (error) {
    showStatus(error.message, 8000);
  }
});

els.statsTimeControl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-stats-time]");
  if (!button) return;
  state.statsTime = button.dataset.statsTime;
  renderTimeStats(state.dashboard?.time_control_stats || []);
});

els.gameList.addEventListener("click", async (event) => {
  const deleteButton = event.target.closest("[data-delete-game-id]");
  if (deleteButton) {
    event.stopPropagation();
    await deleteGame(deleteButton.dataset.deleteGameId);
    return;
  }
  const card = event.target.closest("[data-game-id]");
  if (!card) return;
  await renderGameDetail(card.dataset.gameId);
});

els.gameList.addEventListener("keydown", async (event) => {
  if (!["Enter", " "].includes(event.key)) return;
  const card = event.target.closest("[data-game-id]");
  if (!card) return;
  event.preventDefault();
  await renderGameDetail(card.dataset.gameId);
});

els.backToGames.addEventListener("click", () => setView("games"));

els.backFromOpening.addEventListener("click", () => setView("openings"));

els.backFromAnalysis.addEventListener("click", () => {
  if (state.selectedGameId) {
    setView("detail");
  } else {
    setView("games");
  }
});

els.newAnalysisButton.addEventListener("click", async () => {
  await openBlankAnalysisBoard();
});

els.moreAnalysisButton.addEventListener("click", async () => {
  await openBlankAnalysisBoard();
});

els.analyzeAllButton.addEventListener("click", async () => {
  const ids = filteredGameIds();
  showStatus(`Analysis queued for ${ids.length} filtered games.`, 0);
  try {
    for (const id of ids) {
      await api(`/api/analysis/games/${id}?depth=${selectedDepth()}${profileAmpParam()}`, { method: "POST" });
    }
    await loadAll();
    showStatus("Analysis queue started.");
  } catch (error) {
    showStatus(error.message, 8000);
  }
});

function selectedDepth() {
  const depth = Number(els.depthInput.value);
  if (!Number.isFinite(depth)) return 10;
  return Math.max(1, Math.min(30, Math.round(depth)));
}

function updatePolling() {
  const hasActiveJobs = state.jobs.some((job) => ["queued", "running"].includes(job.status));
  if (hasActiveJobs && !state.pollTimer) {
    state.pollTimer = setInterval(async () => {
      try {
        await loadAll();
        if (state.activeView === "detail" && state.selectedGameId) {
          await renderGameDetail(state.selectedGameId);
        }
      } catch (error) {
        showStatus(error.message, 8000);
      }
    }, 2500);
  }

  if (!hasActiveJobs && state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

function timeRank(timeClass) {
  const ranks = {
    Bullet: 1,
    Blitz: 2,
    Rapid: 3,
    Classical: 4,
    "Daily / Correspondence": 5,
  };
  return ranks[timeClass] || 99;
}

updateThemeButton();
loadAll().catch((error) => showStatus(error.message, 8000));
