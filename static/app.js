import { Chess } from "./vendor/chess.js/chess.js";
import {
  isMuted,
  playMoveSound,
  playOutcomeSound,
  playSound,
  toggleMuted,
} from "./sound.js";

const PIECE_THEME =
  "/static/vendor/chesspieces/wikipedia/{piece}.png";
const CLIENT_TIMEOUT_MS = 12_000;
const ANALYSIS_TIMEOUT_MS = 28_000;
const EVALUATION_TIMEOUT_MS = 4_000;
const EVALUATION_RANGE_CP = 500;
const IDLE_COMMENTARY_INTERVAL_MS = 2_800;
const MIN_THINKING_TIME_MS = 1_500;
const THINKING_COMMENTARY_DELAY_MS = 650;
const THINKING_COMMENTARY_INTERVAL_MS = 3_200;
const PROMOTION_TEST_FEN = "8/P6k/8/8/8/8/7p/7K w - - 0 1";
const PROMOTION_CAPTURE_TEST_FEN = "1r6/P6k/8/8/8/8/7p/7K w - - 0 1";
const ANALYSIS_TEST_FEN = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1";
const CHECK_SOUND_TEST_FEN = "7k/8/8/8/8/8/8/R6K w - - 0 1";
const CASTLE_SOUND_TEST_FEN = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1";
const LOSS_SOUND_TEST_FEN = "8/8/8/8/8/5kq1/8/R6K w - - 0 1";
const DRAW_SOUND_TEST_FEN = "7k/P7/8/8/8/8/8/7K w - - 0 1";
const PROMOTION_PIECES = new Set(["q", "r", "b", "n"]);
const BOARD_FILES = "abcdefgh";
const THEME_STORAGE_KEY = "chess-theme";
const OPPONENT_STORAGE_KEY = "chess-opponent";
const THEMES = {
  dark: {
    "--page": "#16181a",
    "--page-soft": "#1c1f21",
    "--panel": "rgba(30, 33, 36, 0.92)",
    "--panel-solid": "#1e2123",
    "--panel-raised": "#26292c",
    "--line": "rgba(255, 255, 255, 0.08)",
    "--text": "#f0f1ef",
    "--muted": "#a1a59e",
    "--accent": "#7fa650",
    "--accent-strong": "#96c363",
    "--danger": "#f08073",
    "--light-square": "#ebecd0",
    "--dark-square": "#779556",
    "--shadow": "0 12px 32px rgba(0, 0, 0, 0.22)",
    "--page-glow": "rgba(127, 166, 80, 0.08)",
    "--accent-glow": "rgba(127, 166, 80, 0.05)",
    "--control-tint": "rgba(255, 255, 255, 0.035)",
    "--color-scheme": "dark",
  },
  light: {
    "--page": "#f5f0eb",
    "--page-soft": "#e8e0d8",
    "--panel": "rgba(255, 252, 245, 0.94)",
    "--panel-solid": "#fffaf2",
    "--panel-raised": "#e8e0d8",
    "--line": "rgba(60, 50, 40, 0.15)",
    "--text": "#2c241c",
    "--muted": "#6b5f54",
    "--accent": "#39662f",
    "--accent-strong": "#3a6a30",
    "--danger": "#b53629",
    "--light-square": "#f0d9b5",
    "--dark-square": "#b58863",
    "--shadow": "0 12px 32px rgba(55, 42, 28, 0.15)",
    "--page-glow": "rgba(181, 136, 99, 0.18)",
    "--accent-glow": "rgba(74, 124, 63, 0.1)",
    "--control-tint": "rgba(44, 36, 28, 0.035)",
    "--color-scheme": "light",
  },
  sepia: {
    "--page": "#211b14",
    "--page-soft": "#2b231a",
    "--panel": "rgba(55, 43, 31, 0.94)",
    "--panel-solid": "#372b1f",
    "--panel-raised": "#493827",
    "--line": "rgba(246, 225, 190, 0.14)",
    "--text": "#f4e8d2",
    "--muted": "#c1aa88",
    "--accent": "#e0b45d",
    "--accent-strong": "#c99535",
    "--danger": "#ef8d72",
    "--light-square": "#ead8b5",
    "--dark-square": "#9b7045",
    "--shadow": "0 12px 32px rgba(9, 6, 3, 0.4)",
    "--page-glow": "rgba(178, 128, 73, 0.17)",
    "--accent-glow": "rgba(224, 180, 93, 0.08)",
    "--control-tint": "rgba(255, 239, 213, 0.04)",
    "--color-scheme": "dark",
  },
  ocean: {
    "--page": "#07151c",
    "--page-soft": "#0c202a",
    "--panel": "rgba(15, 43, 55, 0.94)",
    "--panel-solid": "#0f2b37",
    "--panel-raised": "#173c49",
    "--line": "rgba(207, 238, 244, 0.13)",
    "--text": "#effbfc",
    "--muted": "#91b7bf",
    "--accent": "#5ee4d4",
    "--accent-strong": "#31cbbb",
    "--danger": "#ff8b82",
    "--light-square": "#d7eef0",
    "--dark-square": "#4d8996",
    "--shadow": "0 12px 32px rgba(0, 7, 12, 0.42)",
    "--page-glow": "rgba(41, 134, 153, 0.2)",
    "--accent-glow": "rgba(94, 228, 212, 0.09)",
    "--control-tint": "rgba(224, 251, 255, 0.04)",
    "--color-scheme": "dark",
  },
  forest: {
    "--page": "#10170d",
    "--page-soft": "#182114",
    "--panel": "rgba(31, 47, 25, 0.94)",
    "--panel-solid": "#1f2f19",
    "--panel-raised": "#2b3e23",
    "--line": "rgba(229, 239, 213, 0.13)",
    "--text": "#f3f7eb",
    "--muted": "#a8b99a",
    "--accent": "#f0c96a",
    "--accent-strong": "#dbaf43",
    "--danger": "#f28d75",
    "--light-square": "#e1e8c8",
    "--dark-square": "#52704a",
    "--shadow": "0 12px 32px rgba(3, 8, 2, 0.38)",
    "--page-glow": "rgba(85, 124, 69, 0.2)",
    "--accent-glow": "rgba(240, 201, 106, 0.08)",
    "--control-tint": "rgba(245, 255, 235, 0.04)",
    "--color-scheme": "dark",
  },
};
const PIECE_NAMES = {
  p: "pawn",
  n: "knight",
  b: "bishop",
  r: "rook",
  q: "queen",
  k: "king",
};
const CAPTURED_PIECE_SYMBOLS = {
  p: "♙",
  n: "♘",
  b: "♗",
  r: "♖",
  q: "♕",
};

class MovePredictor {
  constructor(boardState) {
    this.baseFen = MovePredictor.fenFrom(boardState);
    this.legalMoveCache = new Map();
  }

  static fenFrom(boardState) {
    return typeof boardState === "string" ? boardState : boardState.fen();
  }

  getLegalMovesFromSquare(square, boardState = this.baseFen) {
    const fen = MovePredictor.fenFrom(boardState);
    const cacheKey = `${fen}|${square}`;
    if (!this.legalMoveCache.has(cacheKey)) {
      const position = new Chess(fen);
      this.legalMoveCache.set(cacheKey, position.moves({ square, verbose: true }));
    }
    return this.legalMoveCache.get(cacheKey).map((move) => ({ ...move }));
  }

  getMovePath(startSquare, endSquare) {
    const startFile = BOARD_FILES.indexOf(startSquare[0]);
    const startRank = Number(startSquare[1]);
    const endFile = BOARD_FILES.indexOf(endSquare[0]);
    const endRank = Number(endSquare[1]);
    const fileDistance = endFile - startFile;
    const rankDistance = endRank - startRank;
    const isStraight = fileDistance === 0 || rankDistance === 0;
    const isDiagonal = Math.abs(fileDistance) === Math.abs(rankDistance);
    if (!isStraight && !isDiagonal) {
      return [];
    }

    const fileStep = Math.sign(fileDistance);
    const rankStep = Math.sign(rankDistance);
    const path = [];
    let file = startFile + fileStep;
    let rank = startRank + rankStep;
    while (file !== endFile || rank !== endRank) {
      path.push(`${BOARD_FILES[file]}${rank}`);
      file += fileStep;
      rank += rankStep;
    }
    return path;
  }

  predictBoardStateAfterMove(move, boardState = this.baseFen) {
    const prediction = new Chess(MovePredictor.fenFrom(boardState));
    const completedMove = prediction.move(move);
    if (!completedMove) {
      throw new Error("The planned move is not legal in this position.");
    }
    return { board: prediction, move: completedMove };
  }
}
const localTestName = ["127.0.0.1", "localhost"].includes(window.location.hostname)
  ? new URLSearchParams(window.location.search).get("test")
  : null;
const promotionTestFen = {
  promotion: PROMOTION_TEST_FEN,
  "promotion-capture": PROMOTION_CAPTURE_TEST_FEN,
  draw: DRAW_SOUND_TEST_FEN,
}[localTestName] || null;
const analysisTestFen = localTestName === "analysis" ? ANALYSIS_TEST_FEN : null;
const soundTestFen = {
  check: CHECK_SOUND_TEST_FEN,
  castle: CASTLE_SOUND_TEST_FEN,
  loss: LOSS_SOUND_TEST_FEN,
}[localTestName] || null;
const initialTestFen = promotionTestFen || analysisTestFen || soundTestFen;

const elements = {
  analysisBadge: document.querySelector("#analysisBadge"),
  analysisBestLine: document.querySelector("#analysisBestLine"),
  analysisBestMove: document.querySelector("#analysisBestMove"),
  analysisEngineName: document.querySelector("#analysisEngineName"),
  analysisError: document.querySelector("#analysisError"),
  analysisEvaluationDetail: document.querySelector("#analysisEvaluationDetail"),
  analysisGraph: document.querySelector("#analysisGraph"),
  analysisLossDetail: document.querySelector("#analysisLossDetail"),
  analysisMaterialDetail: document.querySelector("#analysisMaterialDetail"),
  analysisMoveExplanation: document.querySelector("#analysisMoveExplanation"),
  analysisMoveList: document.querySelector("#analysisMoveList"),
  analysisMoveTitle: document.querySelector("#analysisMoveTitle"),
  analysisPanel: document.querySelector("#analysisPanel"),
  analysisPositionCount: document.querySelector("#analysisPositionCount"),
  analysisResult: document.querySelector("#analysisResult"),
  board: document.querySelector("#myBoard"),
  boardOverlay: document.querySelector("#boardOverlay"),
  botCommentary: document.querySelector("#botCommentary"),
  botButtons: document.querySelectorAll("[data-bot]"),
  botSelectorHeading: document.querySelector("#botSelectorHeading"),
  botSelectionStatus: document.querySelector("#botSelectionStatus"),
  clearPlanButton: document.querySelector("#clearPlanButton"),
  closeAnalysisButton: document.querySelector("#closeAnalysisButton"),
  copyPlanButton: document.querySelector("#copyPlanButton"),
  cancelPromotionButton: document.querySelector("#cancelPromotionButton"),
  dependencyAlert: document.querySelector("#dependencyAlert"),
  depthBadge: document.querySelector("#depthBadge"),
  depthBadgeValue: document.querySelector("#depthBadgeValue"),
  errorBox: document.querySelector("#errorBox"),
  evaluationValue: document.querySelector("#evaluationValue"),
  evalBar: document.querySelector("#evalBar"),
  evalBarScore: document.querySelector("#evalBarScore"),
  evalBlackFill: document.querySelector("#evalBlackFill"),
  evalWhiteFill: document.querySelector("#evalWhiteFill"),
  lockedPill: document.querySelector("#lockedPill"),
  capturedPieces: document.querySelector("#capturedPieces"),
  moveCount: document.querySelector("#moveCount"),
  moveHistory: document.querySelector("#moveHistory"),
  newGameButton: document.querySelector("#newGameButton"),
  nextAnalysisButton: document.querySelector("#nextAnalysisButton"),
  nodesValue: document.querySelector("#nodesValue"),
  opponentName: document.querySelector("#opponentName"),
  opponentAvatar: document.querySelector("#opponentAvatar"),
  opponentDialog: document.querySelector("#opponentDialog"),
  opponentDialogDescription: document.querySelector("#opponentDialogDescription"),
  opponentDialogHeading: document.querySelector("#opponentDialogHeading"),
  opponentSelectionError: document.querySelector("#opponentSelectionError"),
  opponentTier: document.querySelector("#opponentTier"),
  promotionDialog: document.querySelector("#promotionDialog"),
  promotionOptions: document.querySelectorAll("[data-promotion]"),
  planMovesButton: document.querySelector("#planMovesButton"),
  planningArrows: document.querySelector("#planningArrows"),
  planningCard: document.querySelector("#planningCard"),
  planningMoveCount: document.querySelector("#planningMoveCount"),
  planningSequence: document.querySelector("#planningSequence"),
  previousAnalysisButton: document.querySelector("#previousAnalysisButton"),
  retryButton: document.querySelector("#retryButton"),
  reviewGameButton: document.querySelector("#reviewGameButton"),
  reviewFromSelectionButton: document.querySelector("#reviewFromSelectionButton"),
  searchNotice: document.querySelector("#searchNotice"),
  statusDescription: document.querySelector("#statusDescription"),
  statusHeading: document.querySelector("#statusHeading"),
  thinkingPill: document.querySelector("#thinkingPill"),
  undoPlanButton: document.querySelector("#undoPlanButton"),
  whiteAccuracy: document.querySelector("#whiteAccuracy"),
  whiteCounts: document.querySelector("#whiteCounts"),
  blackAccuracy: document.querySelector("#blackAccuracy"),
  blackCounts: document.querySelector("#blackCounts"),
  selectedEvaluation: document.querySelector("#selectedEvaluation"),
  soundIcon: document.querySelector("#soundIcon"),
  soundLabel: document.querySelector("#soundLabel"),
  soundToggle: document.querySelector("#soundToggle"),
  themeSelect: document.querySelector("#themeSelect"),
  themeStatus: document.querySelector("#themeStatus"),
};

let game = createInitialGame();
let gameStartFen = game.fen();
let board;
let isThinking = false;
let lastError = "";
let lastEngineStats = null;
let activeRequestId = 0;
let pendingController = null;
let evaluationController = null;
let evaluationRequestId = 0;
let analysisController = null;
let pendingPromotion = null;
let selectedSquare = null;
let selectedMoves = [];
let focusedSquare = promotionTestFen
  ? "a7"
  : analysisTestFen
  ? "f7"
  : localTestName === "check"
  ? "a1"
  : localTestName === "castle"
  ? "e1"
  : localTestName === "loss"
  ? "a1"
  : "e2";
let lastMove = null;
let interactionMessage = "";
let engineMoveAnnouncement = "";
let dragInProgress = false;
let selectedBot = {
  id: "professor",
  label: "The Professor",
  tier: "expert",
  depth: 4,
  avatar: "professor.png",
  idleLines: [],
};
let opponentSelected = false;
let gameActive = false;
let isStartingGame = false;
let botRequestInFlight = false;
let currentCommentary = "";
let idleCommentaryTimer = null;
let thinkingCommentaryDelayTimer = null;
const planningState = {
  isPlanning: false,
  selectedSquare: null,
  highlightedSquares: new Set(),
  arrows: [],
  moveSequence: [],
  hypotheticalBoard: null,
  baseFen: null,
  predictor: null,
};
const analysisState = {
  isLoading: false,
  isOpen: false,
  data: null,
  selectedPly: 0,
  reviewBoard: null,
  error: "",
};

function initialize() {
  initializeTheme();

  if (typeof window.jQuery !== "function" || typeof window.Chessboard !== "function") {
    showDependencyError();
    return;
  }

  board = window.Chessboard("myBoard", {
    draggable: true,
    position: game.fen(),
    orientation: "white",
    pieceTheme: PIECE_THEME,
    onDragStart,
    onDrop,
    onSnapEnd: syncBoard,
  });

  elements.board.setAttribute("role", "grid");
  elements.board.setAttribute("aria-rowcount", "8");
  elements.board.setAttribute("aria-colcount", "8");
  elements.board.addEventListener("click", handleBoardClick);
  elements.board.addEventListener("keydown", handleBoardKeydown);
  elements.board.addEventListener("focusin", handleBoardFocus);
  elements.botButtons.forEach((button) => {
    button.addEventListener("click", selectBot);
  });
  elements.newGameButton.addEventListener("click", handleNewGame);
  elements.soundToggle.addEventListener("click", handleSoundToggle);
  elements.themeSelect.addEventListener("change", (event) => applyTheme(event.target.value));
  elements.reviewGameButton.addEventListener("click", requestGameAnalysis);
  elements.closeAnalysisButton.addEventListener("click", closeGameAnalysis);
  elements.previousAnalysisButton.addEventListener("click", () => {
    selectAnalysisPly(analysisState.selectedPly - 1);
  });
  elements.nextAnalysisButton.addEventListener("click", () => {
    selectAnalysisPly(analysisState.selectedPly + 1);
  });
  elements.analysisMoveList.addEventListener("click", handleAnalysisSelection);
  elements.analysisGraph.addEventListener("click", handleAnalysisSelection);
  elements.analysisGraph.addEventListener("keydown", handleAnalysisGraphKeydown);
  elements.planMovesButton.addEventListener("click", togglePlanningMode);
  elements.undoPlanButton.addEventListener("click", undoPlannedMove);
  elements.clearPlanButton.addEventListener("click", clearPlanningSequence);
  elements.copyPlanButton.addEventListener("click", copyPlanningSequence);
  elements.retryButton.addEventListener("click", requestEngineMove);
  elements.cancelPromotionButton.addEventListener("click", cancelPromotion);
  elements.promotionDialog.addEventListener("cancel", cancelPromotion);
  elements.promotionDialog.addEventListener("keydown", handlePromotionShortcut);
  elements.promotionOptions.forEach((button) => {
    button.addEventListener("click", choosePromotion);
  });
  elements.opponentDialog.addEventListener("cancel", (event) => event.preventDefault());
  elements.reviewFromSelectionButton.addEventListener("click", () => {
    elements.opponentDialog.close();
    requestGameAnalysis();
  });
  window.addEventListener("resize", debounce(() => {
    board.resize();
    scheduleBoardAccessibilityRender();
    renderPlanningArrows();
  }, 100));

  window.chessAppReady = true;
  elements.dependencyAlert.hidden = true;
  elements.dependencyAlert.classList.remove("is-error");
  renderSoundToggle();
  render();
  loadOpponentSelection();
  requestLiveEvaluation();
}

function initializeTheme() {
  let savedTheme = "dark";
  try {
    savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY) || savedTheme;
  } catch (error) {
    // Storage can be unavailable in private or restricted browsing contexts.
  }
  applyTheme(THEMES[savedTheme] ? savedTheme : "dark", false);
}

function applyTheme(themeName, persist = true) {
  const theme = THEMES[themeName];
  if (!theme) return;

  Object.entries(theme).forEach(([property, value]) => {
    document.documentElement.style.setProperty(property, value);
  });
  document.documentElement.dataset.theme = themeName;
  elements.themeSelect.value = themeName;
  elements.themeStatus.textContent = `${elements.themeSelect.selectedOptions[0].text} theme applied.`;

  const themeColor = document.querySelector('meta[name="theme-color"]');
  themeColor?.setAttribute("content", theme["--page"]);

  if (persist) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, themeName);
    } catch (error) {
      // The visual theme still works when preference storage is unavailable.
    }
  }
}

function handleNewGame() {
  playSound("game_start");
  startNewGame();
}

function handleSoundToggle() {
  renderSoundToggle(toggleMuted());
}

function renderSoundToggle(muted = isMuted()) {
  const label = muted ? "Turn sound on" : "Mute sound";
  elements.soundToggle.setAttribute("aria-pressed", String(muted));
  elements.soundToggle.title = label;
  elements.soundIcon.textContent = muted ? "🔇" : "🔊";
  elements.soundLabel.textContent = label;
}

async function selectBot(event) {
  if (opponentSelected) {
    return;
  }

  const button = event.currentTarget;
  const botId = button.dataset.bot;
  botRequestInFlight = true;
  renderBotSelector();
  elements.opponentSelectionError.hidden = true;
  elements.botSelectionStatus.textContent = `Selecting ${button.querySelector("strong").textContent}…`;

  try {
    const response = await fetch("/select_bot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_id: botId }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "The opponent could not be changed.");
    }
    opponentSelected = true;
    try {
      window.localStorage.setItem(OPPONENT_STORAGE_KEY, botId);
    } catch (error) {
      // The server session still preserves the choice when storage is unavailable.
    }
    resetLocalGameState();
    renderSelectedBot(data);
    render();
    elements.opponentDialog.close();
  } catch (error) {
    const message = error.message || "The opponent could not be changed. Please try again.";
    elements.botSelectionStatus.textContent = message;
    elements.opponentSelectionError.textContent = message;
    elements.opponentSelectionError.hidden = false;
  } finally {
    botRequestInFlight = false;
    render();
  }
}

function renderSelectedBot(data) {
  const depth = Number(data.depth);
  selectedBot = {
    id: data.selected,
    label: data.label,
    tier: data.tier || (depth <= 1 ? "novice" : "expert"),
    depth,
    avatar: data.avatar || `${data.selected}.png`,
    idleLines: Array.isArray(data.idle_lines)
      ? data.idle_lines.filter((line) => typeof line === "string" && line.trim())
      : [],
  };
  elements.botButtons.forEach((button) => {
    const isActive = button.dataset.bot === selectedBot.id;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  elements.botSelectionStatus.textContent =
    `${selectedBot.label} is locked for this game at depth ${depth}.`;
  elements.botSelectorHeading.textContent = selectedBot.label;
  elements.lockedPill.hidden = false;
  elements.depthBadgeValue.textContent = String(depth);
  elements.depthBadge.setAttribute(
    "aria-label",
    `${selectedBot.label} engine search depth ${depth}`,
  );
  elements.opponentName.textContent = selectedBot.label;
  elements.opponentTier.textContent = `${selectedBot.tier} · Plays Black`;
  elements.opponentAvatar.src = `/static/avatars/${encodeURIComponent(selectedBot.avatar)}`;
  elements.opponentAvatar.alt = `${selectedBot.label} avatar`;
  elements.opponentAvatar.hidden = false;
  updateCommentary(data.commentary);
}

function renderBotSelector() {
  elements.botButtons.forEach((button) => {
    button.disabled = opponentSelected || isStartingGame || botRequestInFlight;
  });
}

function renderBotLockMessage() {
  if (opponentSelected) {
    elements.botSelectionStatus.textContent =
      `${selectedBot.label} is locked for this game at depth ${selectedBot.depth}.`;
  }
}

function updateCommentary(line) {
  if (typeof line !== "string" || !line.trim()) {
    return;
  }
  currentCommentary = line.trim();
  elements.botCommentary.textContent = currentCommentary;
  elements.botCommentary.hidden = false;
}

function clearCommentary() {
  currentCommentary = "";
  elements.botCommentary.textContent = "";
  elements.botCommentary.hidden = true;
}

function showNextIdleCommentary() {
  const alternatives = selectedBot.idleLines.filter((line) => line !== currentCommentary);
  const pool = alternatives.length > 0 ? alternatives : selectedBot.idleLines;
  if (pool.length > 0) {
    updateCommentary(pool[Math.floor(Math.random() * pool.length)]);
  }
}

function startIdleCommentary() {
  stopIdleCommentary();
  showNextIdleCommentary();
  if (selectedBot.idleLines.length > 1) {
    idleCommentaryTimer = window.setInterval(
      showNextIdleCommentary,
      IDLE_COMMENTARY_INTERVAL_MS,
    );
  }
}

function stopIdleCommentary() {
  if (idleCommentaryTimer !== null) {
    window.clearInterval(idleCommentaryTimer);
    idleCommentaryTimer = null;
  }
}

function startThinkingCommentary() {
  stopThinkingCommentary();
  thinkingCommentaryDelayTimer = window.setTimeout(() => {
    thinkingCommentaryDelayTimer = null;
    if (!isThinking) return;
    showNextIdleCommentary();
    if (selectedBot.idleLines.length > 1) {
      idleCommentaryTimer = window.setInterval(
        showNextIdleCommentary,
        THINKING_COMMENTARY_INTERVAL_MS,
      );
    }
  }, THINKING_COMMENTARY_DELAY_MS);
}

function stopThinkingCommentary() {
  if (thinkingCommentaryDelayTimer !== null) {
    window.clearTimeout(thinkingCommentaryDelayTimer);
    thinkingCommentaryDelayTimer = null;
  }
  stopIdleCommentary();
}

function restoreCommentary(line) {
  if (line) {
    updateCommentary(line);
  } else {
    clearCommentary();
  }
}

function onDragStart(source, piece) {
  const activeGame = getActiveGame();
  if (
    analysisState.isOpen ||
    analysisState.isLoading ||
    isStartingGame ||
    botRequestInFlight ||
    isThinking ||
    pendingPromotion ||
    !opponentSelected ||
    activeGame.isGameOver() ||
    (!planningState.isPlanning && activeGame.turn() !== "w") ||
    !piece.toLowerCase().startsWith(activeGame.turn())
  ) {
    return false;
  }

  dragInProgress = true;
  selectPiece(source);
  return true;
}

function onDrop(source, target) {
  window.setTimeout(() => {
    dragInProgress = false;
  }, 0);

  if (source === target) {
    interactionMessage = "";
    render();
    return "snapback";
  }

  if (isPromotionAttempt(source, target)) {
    if (!isLegalPromotionTarget(source, target)) {
      playSound("illegal");
      interactionMessage = `${target} is not a legal destination for that pawn.`;
      render();
      return "snapback";
    }

    openPromotionChooser(source, target);
    return "snapback";
  }

  if (playActiveMove({ from: source, to: target })) {
    return undefined;
  }

  playSound("illegal");
  interactionMessage = `${target} is not a legal destination for the selected piece.`;
  render();
  return "snapback";
}

function playPlayerMove(moveOptions) {
  let move;
  try {
    move = game.move(moveOptions);
  } catch {
    return false;
  }

  if (!move) {
    return false;
  }

  lastMove = { from: move.from, to: move.to };
  focusedSquare = move.to;
  clearSelection(false);
  lastError = "";
  engineMoveAnnouncement = "";
  gameActive = !game.isGameOver();
  playMoveFeedback(move);
  renderBotSelector();
  renderBotLockMessage();
  syncBoard();
  render();
  requestLiveEvaluation();

  if (!game.isGameOver() && game.turn() === "b") {
    requestEngineMove();
  } else if (game.isGameOver()) {
    releaseCompletedGame();
  }

  return true;
}

function playActiveMove(moveOptions) {
  if (!opponentSelected) {
    return false;
  }
  return planningState.isPlanning
    ? playPlannedMove(moveOptions)
    : playPlayerMove(moveOptions);
}

function playMoveFeedback(move, metadata = {}) {
  if (metadata.game_over || game.isGameOver()) {
    playOutcomeSound(metadata.outcome || currentOutcome());
    return;
  }

  const moveFlags = typeof move.flags === "string" ? move.flags : "";
  playMoveSound({
    is_check: metadata.is_check ?? game.isCheck(),
    is_capture: metadata.is_capture ?? Boolean(move.captured),
    is_castle: metadata.is_castle ?? /[kq]/.test(moveFlags),
    is_promotion: metadata.is_promotion ?? Boolean(move.promotion),
  });
}

function currentOutcome() {
  if (!game.isGameOver() || game.isDraw()) {
    return { winner: null };
  }
  return { winner: game.turn() === "w" ? "black" : "white" };
}

function playPlannedMove(moveOptions) {
  const beforeFen = planningState.hypotheticalBoard.fen();
  let prediction;
  try {
    prediction = planningState.predictor.predictBoardStateAfterMove(
      moveOptions,
      planningState.hypotheticalBoard,
    );
  } catch {
    return false;
  }

  planningState.hypotheticalBoard = prediction.board;
  planningState.moveSequence.push({
    ...prediction.move,
    beforeFen,
    afterFen: prediction.board.fen(),
  });
  planningState.arrows.push({
    from: prediction.move.from,
    to: prediction.move.to,
    color: "yellow",
  });
  focusedSquare = prediction.move.to;
  clearSelection(false);
  interactionMessage = "";
  syncBoard();
  render();
  return true;
}

function isPromotionAttempt(source, target) {
  const piece = getActiveGame().get(source);
  const promotionRank = piece?.color === "w" ? "8" : "1";
  return piece?.type === "p" && target.endsWith(promotionRank);
}

function isLegalPromotionTarget(source, target) {
  return getActiveGame().moves({ verbose: true }).some(
    (move) => move.from === source && move.to === target && PROMOTION_PIECES.has(move.promotion),
  );
}

function openPromotionChooser(source, target) {
  pendingPromotion = { from: source, to: target };
  interactionMessage = "";
  elements.promotionDialog.showModal();
  render();
}

function choosePromotion(event) {
  const promotion = event.currentTarget.dataset.promotion;
  if (!pendingPromotion || !PROMOTION_PIECES.has(promotion)) {
    return;
  }

  const moveOptions = { ...pendingPromotion, promotion };
  pendingPromotion = null;
  elements.promotionDialog.close();

  if (!playActiveMove(moveOptions)) {
    playSound("illegal");
    lastError = "That promotion is no longer legal. Please try the move again.";
    syncBoard();
    render();
  }
}

function cancelPromotion(event) {
  event?.preventDefault();
  pendingPromotion = null;
  if (elements.promotionDialog.open) {
    elements.promotionDialog.close();
  }
  syncBoard();
  render();
}

function handlePromotionShortcut(event) {
  if (!pendingPromotion || event.altKey || event.ctrlKey || event.metaKey) {
    return;
  }

  const promotion = event.key.toLowerCase();
  if (!PROMOTION_PIECES.has(promotion)) {
    return;
  }

  event.preventDefault();
  elements.promotionDialog
    .querySelector(`[data-promotion="${promotion}"]`)
    ?.click();
}

function handleBoardClick(event) {
  if (dragInProgress) {
    return;
  }

  const square = squareNameFromElement(event.target.closest(".square-55d63"));
  if (square) {
    activateSquare(square);
  }
}

function handleBoardFocus(event) {
  const square = squareNameFromElement(event.target.closest(".square-55d63"));
  if (square) {
    focusedSquare = square;
    scheduleBoardAccessibilityRender();
  }
}

function handleBoardKeydown(event) {
  const square = squareNameFromElement(event.target.closest(".square-55d63"));
  if (!square) {
    return;
  }

  const direction = {
    ArrowUp: [0, 1],
    ArrowDown: [0, -1],
    ArrowLeft: [-1, 0],
    ArrowRight: [1, 0],
  }[event.key];

  if (direction) {
    event.preventDefault();
    focusBoardSquare(offsetSquare(square, ...direction));
    return;
  }

  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    activateSquare(square);
    return;
  }

  if (event.key === "Escape" && getSelectedSquare()) {
    event.preventDefault();
    clearSelection();
  }
}

function activateSquare(square) {
  const activeGame = getActiveGame();
  const activeSelectedSquare = getSelectedSquare();
  const activeSelectedMoves = getSelectedMoves();
  if (
    analysisState.isOpen ||
    analysisState.isLoading ||
    isStartingGame ||
    botRequestInFlight ||
    isThinking ||
    pendingPromotion ||
    activeGame.isGameOver() ||
    (!planningState.isPlanning && activeGame.turn() !== "w")
  ) {
    return;
  }

  const piece = activeGame.get(square);
  if (!activeSelectedSquare) {
    selectPiece(square);
    return;
  }

  if (square === activeSelectedSquare) {
    clearSelection();
    return;
  }

  const matchingMoves = activeSelectedMoves.filter((move) => move.to === square);
  if (matchingMoves.length > 0) {
    if (matchingMoves.some((move) => PROMOTION_PIECES.has(move.promotion))) {
      openPromotionChooser(activeSelectedSquare, square);
      return;
    }

    playActiveMove({ from: activeSelectedSquare, to: square });
    return;
  }

  if (piece?.color === activeGame.turn()) {
    selectPiece(square);
    return;
  }

  interactionMessage = `${square} is not a legal destination for the selected piece.`;
  playSound("illegal");
  render();
}

function selectPiece(square) {
  const activeGame = getActiveGame();
  const piece = activeGame.get(square);
  if (
    !piece ||
    piece.color !== activeGame.turn() ||
    isStartingGame ||
    botRequestInFlight ||
    isThinking ||
    pendingPromotion ||
    activeGame.isGameOver() ||
    (!planningState.isPlanning && activeGame.turn() !== "w")
  ) {
    const sideToMove = activeGame.turn() === "w" ? "White" : "Black";
    interactionMessage = piece
      ? `Select one of ${sideToMove}'s pieces.`
      : `${square} is empty. Select one of ${sideToMove}'s pieces first.`;
    render();
    return false;
  }

  const legalMoves = planningState.isPlanning
    ? planningState.predictor.getLegalMovesFromSquare(square, activeGame)
    : activeGame.moves({ square, verbose: true });
  if (planningState.isPlanning) {
    planningState.selectedSquare = square;
    planningState.highlightedSquares = new Set(legalMoves.map((move) => move.to));
  } else {
    selectedSquare = square;
  }
  selectedMoves = legalMoves;
  focusedSquare = square;
  interactionMessage = "";
  render();
  return true;
}

function clearSelection(shouldRender = true) {
  if (planningState.isPlanning) {
    planningState.selectedSquare = null;
    planningState.highlightedSquares.clear();
  } else {
    selectedSquare = null;
  }
  selectedMoves = [];
  interactionMessage = "";
  if (shouldRender) {
    render();
  }
}

function getActiveGame() {
  if (analysisState.isOpen) {
    return analysisState.reviewBoard;
  }
  return planningState.isPlanning ? planningState.hypotheticalBoard : game;
}

function getSelectedSquare() {
  if (analysisState.isOpen) {
    return null;
  }
  return planningState.isPlanning ? planningState.selectedSquare : selectedSquare;
}

function getSelectedMoves() {
  return analysisState.isOpen ? [] : selectedMoves;
}

function offsetSquare(square, fileDelta, rankDelta) {
  const fileIndex = Math.min(
    BOARD_FILES.length - 1,
    Math.max(0, BOARD_FILES.indexOf(square[0]) + fileDelta),
  );
  const rank = Math.min(8, Math.max(1, Number(square[1]) + rankDelta));
  return `${BOARD_FILES[fileIndex]}${rank}`;
}

function focusBoardSquare(square) {
  focusedSquare = square;
  renderBoardAccessibility();
  elements.board.querySelector(`.square-${square}`)?.focus();
}

function squareNameFromElement(element) {
  if (!element) {
    return null;
  }

  const squareClass = [...element.classList].find((className) =>
    /^square-[a-h][1-8]$/.test(className),
  );
  return squareClass?.slice("square-".length) || null;
}

function scheduleBoardAccessibilityRender() {
  renderBoardAccessibility();
  renderPlanningArrows();
  window.requestAnimationFrame(() => {
    renderBoardAccessibility();
    renderPlanningArrows();
  });
}

function renderBoardAccessibility() {
  const activeGame = getActiveGame();
  const activeSelectedSquare = getSelectedSquare();
  const activeSelectedMoves = getSelectedMoves();
  const displayedLastMove = getDisplayedLastMove();
  const squares = elements.board.querySelectorAll(".square-55d63");
  squares.forEach((element) => {
    const square = squareNameFromElement(element);
    if (!square) {
      return;
    }

    const matchingMoves = activeSelectedMoves.filter((move) => move.to === square);
    const isCapture = matchingMoves.some((move) => Boolean(move.captured));

    element.classList.toggle(
      "is-selected",
      !planningState.isPlanning && square === activeSelectedSquare,
    );
    element.classList.toggle(
      "is-planning-selected",
      planningState.isPlanning && square === activeSelectedSquare,
    );
    element.classList.toggle(
      "is-legal-move",
      matchingMoves.length > 0 && !isCapture,
    );
    element.classList.toggle(
      "is-legal-capture",
      matchingMoves.length > 0 && isCapture,
    );
    element.classList.toggle(
      "is-last-move",
      square === displayedLastMove?.from || square === displayedLastMove?.to,
    );

    element.setAttribute("role", "gridcell");
    element.setAttribute("aria-rowindex", String(9 - Number(square[1])));
    element.setAttribute("aria-colindex", String(BOARD_FILES.indexOf(square[0]) + 1));
    element.setAttribute("aria-selected", String(square === activeSelectedSquare));
    element.setAttribute(
      "aria-disabled",
      String(
        isThinking ||
        analysisState.isOpen ||
        analysisState.isLoading ||
        activeGame.isGameOver() ||
        (!planningState.isPlanning && activeGame.turn() !== "w"),
      ),
    );
    element.setAttribute("aria-label", describeSquare(square, matchingMoves));
    element.tabIndex = square === focusedSquare ? 0 : -1;
  });
}

function renderPlanningArrows() {
  elements.board.classList.toggle("is-planning", planningState.isPlanning);
  if (!planningState.isPlanning) {
    elements.planningArrows.setAttribute("hidden", "");
    elements.planningArrows.replaceChildren();
    return;
  }

  elements.board.append(elements.planningArrows);
  elements.planningArrows.removeAttribute("hidden");
  elements.planningArrows.setAttribute("viewBox", "0 0 100 100");

  const namespace = "http://www.w3.org/2000/svg";
  const definitions = document.createElementNS(namespace, "defs");
  const marker = document.createElementNS(namespace, "marker");
  marker.setAttribute("id", "planningArrowHead");
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "8");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "5");
  marker.setAttribute("markerHeight", "5");
  marker.setAttribute("orient", "auto-start-reverse");
  const arrowHead = document.createElementNS(namespace, "path");
  arrowHead.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  arrowHead.setAttribute("fill", "#ffd84d");
  marker.append(arrowHead);
  definitions.append(marker);

  const arrows = [
    ...planningState.arrows.map((arrow) => ({ ...arrow, kind: "committed" })),
    ...getSelectedMoves().map((move) => ({
      from: move.from,
      to: move.to,
      color: "yellow",
      kind: "candidate",
    })),
  ];

  const nodes = [definitions];
  arrows.forEach((arrow) => {
    const geometry = arrowGeometry(arrow.from, arrow.to);
    const line = document.createElementNS(namespace, "line");
    line.setAttribute("x1", geometry.x1);
    line.setAttribute("y1", geometry.y1);
    line.setAttribute("x2", geometry.x2);
    line.setAttribute("y2", geometry.y2);
    line.setAttribute("marker-end", "url(#planningArrowHead)");
    line.setAttribute("class", `planning-arrow is-${arrow.kind}`);
    nodes.push(line);
  });
  elements.planningArrows.replaceChildren(...nodes);
}

function arrowGeometry(from, to) {
  const point = (square) => ({
    x: (BOARD_FILES.indexOf(square[0]) + 0.5) * 12.5,
    y: (8 - Number(square[1]) + 0.5) * 12.5,
  });
  const start = point(from);
  const end = point(to);
  const deltaX = end.x - start.x;
  const deltaY = end.y - start.y;
  const distance = Math.hypot(deltaX, deltaY) || 1;
  const endPadding = 3.4;
  return {
    x1: start.x,
    y1: start.y,
    x2: end.x - (deltaX / distance) * endPadding,
    y2: end.y - (deltaY / distance) * endPadding,
  };
}

function describeSquare(square, matchingMoves) {
  const piece = getActiveGame().get(square);
  const activeSelectedSquare = getSelectedSquare();
  const displayedLastMove = getDisplayedLastMove();
  const descriptions = [
    square,
    piece ? `${piece.color === "w" ? "White" : "Black"} ${PIECE_NAMES[piece.type]}` : "empty",
  ];

  if (square === activeSelectedSquare) {
    descriptions.push("selected");
  }
  if (matchingMoves.length > 0) {
    descriptions.push(
      matchingMoves.some((move) => Boolean(move.captured))
        ? "legal capture destination"
        : "legal move destination",
    );
  }
  if (square === displayedLastMove?.from) {
    descriptions.push("last move started here");
  }
  if (square === displayedLastMove?.to) {
    descriptions.push("last move ended here");
  }

  return descriptions.join(", ");
}

function getDisplayedLastMove() {
  if (analysisState.isOpen && analysisState.selectedPly > 0) {
    return analysisState.data.moves[analysisState.selectedPly - 1];
  }
  return lastMove;
}

function syncBoard(useAnimation = true) {
  board.position(getActiveGame().fen(), useAnimation);
  scheduleBoardAccessibilityRender();
}

async function requestEngineMove() {
  if (
    analysisState.isOpen ||
    analysisState.isLoading ||
    planningState.isPlanning ||
    isThinking ||
    game.isGameOver() ||
    game.turn() !== "b"
  ) {
    return;
  }

  const commentaryBeforeThinking = currentCommentary;
  const requestId = ++activeRequestId;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), CLIENT_TIMEOUT_MS);

  pendingController = controller;
  isThinking = true;
  lastError = "";
  startThinkingCommentary();
  render();

  try {
    const fetchPromise = fetch("/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fen: game.fen() }),
      signal: controller.signal,
    });
    const delayPromise = new Promise((resolve) => {
      window.setTimeout(resolve, MIN_THINKING_TIME_MS);
    });

    const [response] = await Promise.all([fetchPromise, delayPromise]);

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "The engine request failed.");
    }

    if (requestId !== activeRequestId) {
      return;
    }

    stopThinkingCommentary();
    if (typeof data.commentary === "string" && data.commentary.trim()) {
      updateCommentary(data.commentary);
    } else {
      restoreCommentary(commentaryBeforeThinking);
    }

    if (!data.engine_move) {
      gameActive = false;
      if (data.game_over) {
        playOutcomeSound(data.outcome || currentOutcome());
        releaseCompletedGame();
      }
      renderBotLockMessage();
      render();
      return;
    }

    const engineMove = parseUciMove(data.engine_move);
    let completedEngineMove;
    try {
      completedEngineMove = game.move(engineMove);
    } catch {
      throw new Error("The engine returned a move the browser could not play.");
    }

    lastMove = {
      from: completedEngineMove.from,
      to: completedEngineMove.to,
    };
    engineMoveAnnouncement = `Engine played ${completedEngineMove.san}.`;
    gameActive = !game.isGameOver();
    playMoveFeedback(completedEngineMove, data);
    renderBotLockMessage();
    syncBoard();
    lastEngineStats = {
      score: Number(data.score),
      nodes: Number(data.nodes),
      depth: Number(data.depth),
      timedOut: Boolean(data.timed_out),
    };
    requestLiveEvaluation();
    if (game.isGameOver()) {
      releaseCompletedGame();
    }
  } catch (error) {
    if (requestId !== activeRequestId) {
      return;
    }

    lastError =
      error.name === "AbortError"
        ? "The engine request timed out. You can retry from this position."
        : error.message || "The engine could not calculate a move.";
    restoreCommentary(commentaryBeforeThinking);
  } finally {
    window.clearTimeout(timer);
    stopThinkingCommentary();
    if (requestId === activeRequestId) {
      isThinking = false;
      pendingController = null;
      render();
    }
  }
}

function parseUciMove(uci) {
  if (typeof uci !== "string" || !/^[a-h][1-8][a-h][1-8][qrbn]?$/.test(uci)) {
    throw new Error("The engine returned an invalid move.");
  }

  return {
    from: uci.slice(0, 2),
    to: uci.slice(2, 4),
    promotion: uci.length === 5 ? uci[4] : undefined,
  };
}

function togglePlanningMode() {
  if (planningState.isPlanning) {
    exitPlanningMode();
    return;
  }

  if (
    analysisState.isOpen ||
    analysisState.isLoading ||
    isThinking ||
    pendingPromotion ||
    game.isGameOver()
  ) {
    return;
  }

  clearSelection(false);
  planningState.isPlanning = true;
  planningState.baseFen = game.fen();
  planningState.hypotheticalBoard = new Chess(planningState.baseFen);
  planningState.predictor = new MovePredictor(planningState.baseFen);
  planningState.selectedSquare = null;
  planningState.highlightedSquares.clear();
  planningState.arrows = [];
  planningState.moveSequence = [];
  interactionMessage = "";
  syncBoard(false);
  render();
}

function exitPlanningMode() {
  pendingPromotion = null;
  if (elements.promotionDialog.open) {
    elements.promotionDialog.close();
  }
  planningState.isPlanning = false;
  planningState.selectedSquare = null;
  planningState.highlightedSquares.clear();
  planningState.arrows = [];
  planningState.moveSequence = [];
  planningState.hypotheticalBoard = null;
  planningState.baseFen = null;
  planningState.predictor = null;
  selectedMoves = [];
  interactionMessage = "";
  syncBoard(false);
  render();
}

function clearPlanningSequence() {
  if (!planningState.isPlanning) {
    return;
  }

  planningState.hypotheticalBoard = new Chess(planningState.baseFen);
  planningState.moveSequence = [];
  planningState.arrows = [];
  clearSelection(false);
  interactionMessage = "Planning reset to the live position.";
  syncBoard(false);
  render();
}

function undoPlannedMove() {
  if (!planningState.isPlanning || planningState.moveSequence.length === 0) {
    return;
  }

  const undoneMove = planningState.moveSequence.pop();
  planningState.arrows.pop();
  planningState.hypotheticalBoard = new Chess(undoneMove.beforeFen);
  clearSelection(false);
  focusedSquare = undoneMove.from;
  interactionMessage = `Removed ${undoneMove.san} from the plan.`;
  syncBoard(false);
  render();
}

async function copyPlanningSequence() {
  const notation = formatPlanningSequence();
  if (!notation) {
    interactionMessage = "Add at least one move before copying the plan.";
    render();
    return;
  }

  try {
    await navigator.clipboard.writeText(notation);
    interactionMessage = "Planned sequence copied to the clipboard.";
  } catch {
    interactionMessage = "The browser could not copy the sequence. Select the notation manually.";
  }
  render();
}

function formatPlanningSequence() {
  if (!planningState.baseFen || planningState.moveSequence.length === 0) {
    return "";
  }

  const fenParts = planningState.baseFen.split(" ");
  let turn = fenParts[1];
  let moveNumber = Number(fenParts[5]);
  const groups = [];

  planningState.moveSequence.forEach((move) => {
    if (turn === "w") {
      groups.push(`${moveNumber}. ${move.san}`);
      turn = "b";
    } else {
      if (groups.length > 0 && !groups.at(-1).includes("...")) {
        groups[groups.length - 1] += ` ${move.san}`;
      } else {
        groups.push(`${moveNumber}... ${move.san}`);
      }
      moveNumber += 1;
      turn = "w";
    }
  });

  return groups.join(" ");
}

async function requestGameAnalysis() {
  const history = game.history({ verbose: true });
  if (analysisState.isLoading || history.length === 0 || !game.isGameOver()) {
    return;
  }

  if (
    analysisState.data?.start_fen === gameStartFen &&
    analysisState.data?.final_fen === game.fen()
  ) {
    analysisState.isOpen = true;
    analysisState.selectedPly = analysisState.data.moves.length;
    analysisState.reviewBoard = new Chess(analysisState.data.final_fen);
    syncBoard(false);
    render();
    elements.analysisPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);
  analysisController = controller;
  analysisState.isLoading = true;
  analysisState.error = "";
  clearSelection(false);
  render();

  try {
    const response = await fetch("/analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_fen: gameStartFen,
        moves: history.map(toUciMove),
      }),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "The game analysis request failed.");
    }
    if (!Array.isArray(data.moves) || !Array.isArray(data.evaluations)) {
      throw new Error("The analysis response was incomplete.");
    }
    if (analysisController !== controller) {
      return;
    }

    analysisState.data = data;
    analysisState.isOpen = true;
    analysisState.selectedPly = data.moves.length;
    analysisState.reviewBoard = new Chess(data.final_fen);
    syncBoard(false);
    render();
    elements.analysisPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    if (analysisController !== controller) {
      return;
    }
    analysisState.error = error.name === "AbortError"
      ? "Game analysis timed out. Try again in a moment."
      : error.message || "The game could not be analyzed.";
  } finally {
    window.clearTimeout(timer);
    if (analysisController === controller) {
      analysisController = null;
      analysisState.isLoading = false;
      render();
    }
  }
}

function toUciMove(move) {
  return `${move.from}${move.to}${move.promotion || ""}`;
}

function closeGameAnalysis() {
  if (!analysisState.isOpen) {
    return;
  }
  analysisState.isOpen = false;
  analysisState.reviewBoard = null;
  analysisState.selectedPly = 0;
  syncBoard(false);
  render();
}

function selectAnalysisPly(ply) {
  if (!analysisState.isOpen) {
    return;
  }
  const maximum = analysisState.data.moves.length;
  const selectedPly = Math.min(maximum, Math.max(0, Number(ply)));
  const fen = selectedPly === 0
    ? analysisState.data.start_fen
    : analysisState.data.moves[selectedPly - 1].fen_after;
  analysisState.selectedPly = selectedPly;
  analysisState.reviewBoard = new Chess(fen);
  syncBoard(false);
  render();
}

function handleAnalysisSelection(event) {
  const target = event.target.closest("[data-analysis-ply]");
  if (target) {
    selectAnalysisPly(target.dataset.analysisPly);
  }
}

function handleAnalysisGraphKeydown(event) {
  if ((event.key === "Enter" || event.key === " ") && event.target.dataset.analysisPly) {
    event.preventDefault();
    selectAnalysisPly(event.target.dataset.analysisPly);
  }
}

async function loadOpponentSelection() {
  try {
    const response = await fetch("/select_bot");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Your opponent selection could not be loaded.");
    }
    if (data.needs_selection || !data.selected) {
      opponentSelected = false;
      openOpponentSelector(false);
      return;
    }

    opponentSelected = true;
    renderSelectedBot(data);
    try {
      window.localStorage.setItem(OPPONENT_STORAGE_KEY, data.selected);
    } catch (error) {
      // The server session remains authoritative when storage is unavailable.
    }
    render();
  } catch (error) {
    opponentSelected = false;
    openOpponentSelector(false);
    elements.opponentSelectionError.textContent =
      error.message || "Your opponent selection could not be loaded.";
    elements.opponentSelectionError.hidden = false;
  }
}

function openOpponentSelector(afterGame = false) {
  elements.botSelectorHeading.textContent = "Choose before playing";
  elements.botSelectionStatus.textContent = "Select a character to begin.";
  elements.lockedPill.hidden = true;
  elements.opponentDialogHeading.textContent = afterGame
    ? "Choose your next opponent"
    : "Choose your opponent";
  elements.opponentDialogDescription.textContent = afterGame
    ? "The game is complete. Pick a new challenge, or review the match before playing again."
    : "Pick a character before the first move. Your choice stays locked for the entire game.";
  elements.reviewFromSelectionButton.hidden = !(afterGame && game.history().length > 0);
  elements.opponentSelectionError.hidden = true;
  renderBotSelector();
  if (!elements.opponentDialog.open) {
    elements.opponentDialog.showModal();
  }
}

async function releaseCompletedGame() {
  if (!game.isGameOver()) {
    return;
  }
  opponentSelected = false;
  gameActive = false;
  try {
    window.localStorage.removeItem(OPPONENT_STORAGE_KEY);
  } catch (error) {
    // The server endpoint still releases the choice.
  }
  try {
    const response = await fetch("/end_game", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fen: game.fen() }),
    });
    const data = await response.json().catch(() => ({}));
    if (response.ok) {
      updateCommentary(data.commentary);
    }
  } catch (error) {
    // New game will retry server state if releasing the completed match failed.
  }
  elements.lockedPill.hidden = true;
  elements.botSelectionStatus.textContent =
    "Game complete. Review the board or choose New game for another opponent.";
  render();
}

async function startNewGame() {
  activeRequestId += 1;
  pendingController?.abort();
  pendingController = null;
  stopThinkingCommentary();
  evaluationRequestId += 1;
  evaluationController?.abort();
  evaluationController = null;
  analysisController?.abort();
  analysisController = null;
  isStartingGame = true;
  lastError = "";
  elements.botSelectionStatus.textContent = "Preparing a new game…";
  render();

  try {
    const response = await fetch("/new_game", { method: "POST" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "A new game could not be started.");
    }

    opponentSelected = false;
    gameActive = false;
    try {
      window.localStorage.removeItem(OPPONENT_STORAGE_KEY);
    } catch (error) {
      // The server session has already been cleared.
    }
  } catch (error) {
    lastError = error.message || "A new game could not be started.";
    elements.botSelectionStatus.textContent =
      "The new game could not be prepared. Try New game again.";
    return;
  } finally {
    isStartingGame = false;
    render();
  }

  resetLocalGameState();
  openOpponentSelector(false);
}

function resetLocalGameState() {
  activeRequestId += 1;
  pendingController?.abort();
  pendingController = null;
  stopThinkingCommentary();
  clearCommentary();
  elements.opponentAvatar.removeAttribute("src");
  elements.opponentAvatar.alt = "";
  elements.opponentAvatar.hidden = true;
  elements.opponentName.textContent = "Choose opponent";
  elements.opponentTier.textContent = "Plays Black";
  evaluationRequestId += 1;
  evaluationController?.abort();
  evaluationController = null;
  analysisController?.abort();
  analysisController = null;
  pendingPromotion = null;
  if (elements.promotionDialog.open) {
    elements.promotionDialog.close();
  }
  isThinking = false;
  lastError = "";
  lastEngineStats = null;
  lastMove = null;
  engineMoveAnnouncement = "";
  selectedSquare = null;
  selectedMoves = [];
  interactionMessage = "";
  analysisState.isLoading = false;
  analysisState.isOpen = false;
  analysisState.data = null;
  analysisState.selectedPly = 0;
  analysisState.reviewBoard = null;
  analysisState.error = "";
  planningState.isPlanning = false;
  planningState.selectedSquare = null;
  planningState.highlightedSquares.clear();
  planningState.arrows = [];
  planningState.moveSequence = [];
  planningState.hypotheticalBoard = null;
  planningState.baseFen = null;
  planningState.predictor = null;
  game = createInitialGame();
  gameStartFen = game.fen();
  focusedSquare = promotionTestFen
    ? "a7"
    : analysisTestFen
    ? "f7"
    : localTestName === "check"
    ? "a1"
    : localTestName === "castle"
    ? "e1"
    : localTestName === "loss"
    ? "a1"
    : "e2";
  syncBoard(false);
  render();
  requestLiveEvaluation();
}

async function requestLiveEvaluation() {
  const requestId = ++evaluationRequestId;
  evaluationController?.abort();
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), EVALUATION_TIMEOUT_MS);
  evaluationController = controller;

  try {
    const response = await fetch("/api/eval", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fen: game.fen() }),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Evaluation unavailable.");
    }
    if (requestId === evaluationRequestId) {
      updateEvalBar(data);
    }
  } catch (error) {
    if (requestId === evaluationRequestId && error.name !== "AbortError") {
      elements.evalBar.setAttribute("aria-label", "Position evaluation unavailable");
    }
  } finally {
    window.clearTimeout(timer);
    if (requestId === evaluationRequestId) {
      evaluationController = null;
    }
  }
}

function updateEvalBar(data) {
  const hasMate = data.mate !== null && data.mate !== undefined;
  let whitePercent;
  let label;
  let description;
  let whiteAhead = false;
  let blackAhead = false;

  if (hasMate) {
    const mate = Number(data.mate);
    const winner = data.winner || (mate > 0 ? "white" : "black");
    const moves = Math.ceil(Math.abs(mate) / 2);
    whiteAhead = winner === "white";
    blackAhead = winner === "black";
    whitePercent = whiteAhead ? 100 : 0;
    label = `M${moves}`;
    description = moves === 0
      ? `${whiteAhead ? "White" : "Black"} has won by checkmate`
      : `${whiteAhead ? "White" : "Black"} has mate in ${moves}`;
    elements.evalBar.setAttribute("aria-valuenow", whiteAhead ? "5" : "-5");
  } else {
    const evaluation = Number(data.eval);
    const safeEvaluation = Number.isFinite(evaluation) ? evaluation : 0;
    const clamped = Math.max(-EVALUATION_RANGE_CP, Math.min(EVALUATION_RANGE_CP, safeEvaluation));
    whitePercent = ((clamped + EVALUATION_RANGE_CP) / (2 * EVALUATION_RANGE_CP)) * 100;
    whiteAhead = safeEvaluation > 0;
    blackAhead = safeEvaluation < 0;
    label = `${safeEvaluation > 0 ? "+" : ""}${(safeEvaluation / 100).toFixed(2)}`;
    description = safeEvaluation === 0
      ? "Position evaluation: even"
      : `Position evaluation: ${label}, ${whiteAhead ? "White" : "Black"} ahead`;
    elements.evalBar.setAttribute("aria-valuenow", String(clamped / 100));
  }

  elements.evalBlackFill.style.height = `${100 - whitePercent}%`;
  elements.evalWhiteFill.style.height = `${whitePercent}%`;
  elements.evalBarScore.textContent = label;
  elements.evalBar.classList.toggle("is-white-ahead", whiteAhead);
  elements.evalBar.classList.toggle("is-black-ahead", blackAhead);
  elements.evalBar.setAttribute("aria-label", description);
  elements.evalBar.setAttribute("aria-valuetext", description);
}

function renderCapturedPieces() {
  const captures = game
    .history({ verbose: true })
    .filter((move) => move.color === "b" && move.captured)
    .map((move) => move.captured);
  elements.capturedPieces.textContent = captures
    .map((piece) => CAPTURED_PIECE_SYMBOLS[piece] || "")
    .join("");
  const names = captures.map((piece) => PIECE_NAMES[piece] || "piece");
  elements.capturedPieces.setAttribute(
    "aria-label",
    names.length > 0
      ? `${selectedBot.label} captured ${names.join(", ")}`
      : "No pieces captured by the opponent",
  );
}

function render() {
  renderStatus();
  renderHistory();
  renderStats();
  renderPlanningPanel();
  renderAnalysisPanel();
  renderBotSelector();
  renderCapturedPieces();

  const canRetry =
    !planningState.isPlanning &&
    Boolean(lastError) &&
    !game.isGameOver() &&
    game.turn() === "b";
  elements.retryButton.hidden = !canRetry;
  elements.errorBox.hidden = planningState.isPlanning || !lastError;
  elements.errorBox.textContent = lastError;
  const searchMessage = getSearchNotice();
  elements.searchNotice.hidden = planningState.isPlanning || !searchMessage;
  elements.searchNotice.textContent = searchMessage;
  elements.boardOverlay.hidden = !(
    isThinking || analysisState.isLoading || isStartingGame || botRequestInFlight
  );
  elements.thinkingPill.hidden = !isThinking;
  elements.planMovesButton.disabled =
    analysisState.isOpen ||
    analysisState.isLoading ||
    isThinking ||
    Boolean(pendingPromotion) ||
    game.isGameOver();
  elements.planMovesButton.setAttribute("aria-pressed", String(planningState.isPlanning));
  elements.planMovesButton.textContent = planningState.isPlanning
    ? "Exit planning"
    : "Plan moves";
  const canReview = game.isGameOver() && game.history().length > 0 && !analysisState.isOpen;
  elements.reviewGameButton.hidden = !canReview;
  elements.reviewGameButton.disabled = analysisState.isLoading;
  elements.reviewGameButton.textContent = analysisState.isLoading
    ? "Analyzing game\u2026"
    : "Review game";
  elements.analysisError.hidden = !analysisState.error;
  elements.analysisError.textContent = analysisState.error;
  scheduleBoardAccessibilityRender();
}

function renderPlanningPanel() {
  elements.planningCard.hidden = !planningState.isPlanning;
  if (!planningState.isPlanning) {
    return;
  }

  const count = planningState.moveSequence.length;
  elements.planningMoveCount.textContent = `${count} ${count === 1 ? "move" : "moves"}`;
  elements.planningSequence.textContent = formatPlanningSequence()
    || "Select the side-to-move's piece to begin.";
  elements.undoPlanButton.disabled = count === 0;
  elements.clearPlanButton.disabled = count === 0;
  elements.copyPlanButton.disabled = count === 0;
}

function renderAnalysisPanel() {
  elements.analysisPanel.hidden = !analysisState.isOpen;
  if (!analysisState.isOpen) {
    return;
  }

  const { data } = analysisState;
  elements.analysisEngineName.textContent =
    `Analyzed with ${data.engine} \u2022 ${data.moves.length} half-moves`;
  elements.whiteAccuracy.textContent = `${data.summary.white_accuracy.toFixed(1)}%`;
  elements.blackAccuracy.textContent = `${data.summary.black_accuracy.toFixed(1)}%`;
  elements.whiteCounts.textContent = formatClassificationCounts(data.summary.counts.white);
  elements.blackCounts.textContent = formatClassificationCounts(data.summary.counts.black);
  elements.analysisResult.textContent = formatAnalysisResult(data.result);
  renderAnalysisGraph();
  renderAnalysisMoveList();
  renderAnalysisDetails();
}

function renderAnalysisGraph() {
  const namespace = "http://www.w3.org/2000/svg";
  const width = 800;
  const height = 220;
  const left = 24;
  const right = 776;
  const top = 14;
  const bottom = 206;
  const zeroY = (top + bottom) / 2;
  const range = 800;
  const evaluations = analysisState.data.evaluations;
  const maximumPly = Math.max(1, evaluations.length - 1);
  const xFor = (ply) => left + (Number(ply) / maximumPly) * (right - left);
  const yFor = (centipawns) => {
    const clamped = Math.max(-range, Math.min(range, Number(centipawns)));
    return zeroY - (clamped / range) * (zeroY - top);
  };

  const whiteZone = createSvgElement(namespace, "rect", {
    x: 0,
    y: 0,
    width,
    height: zeroY,
    class: "graph-white-zone",
  });
  const blackZone = createSvgElement(namespace, "rect", {
    x: 0,
    y: zeroY,
    width,
    height: height - zeroY,
    class: "graph-black-zone",
  });
  const gridLines = [top, zeroY / 2 + top / 2, zeroY, zeroY + (bottom - zeroY) / 2, bottom]
    .map((y) => createSvgElement(namespace, "line", {
      x1: left,
      y1: y,
      x2: right,
      y2: y,
      class: y === zeroY ? "graph-zero-line" : "graph-grid-line",
    }));
  const points = evaluations.map((evaluation) =>
    `${xFor(evaluation.ply)},${yFor(evaluation.evaluation_cp)}`,
  );
  const line = createSvgElement(namespace, "polyline", {
    points: points.join(" "),
    class: "graph-evaluation-line",
  });
  const pointNodes = evaluations.map((evaluation) => {
    const circle = createSvgElement(namespace, "circle", {
      cx: xFor(evaluation.ply),
      cy: yFor(evaluation.evaluation_cp),
      r: evaluation.ply === analysisState.selectedPly ? 6 : 4,
      class: `graph-point${evaluation.ply === analysisState.selectedPly ? " is-selected" : ""}`,
      tabindex: 0,
      role: "button",
      "aria-label": `Position ${evaluation.ply}: ${formatEvaluation(evaluation.evaluation_cp)}`,
    });
    circle.dataset.analysisPly = String(evaluation.ply);
    return circle;
  });

  elements.analysisGraph.replaceChildren(
    whiteZone,
    blackZone,
    ...gridLines,
    line,
    ...pointNodes,
  );
}

function renderAnalysisMoveList() {
  const fragment = document.createDocumentFragment();
  analysisState.data.moves.forEach((move) => {
    const button = createElement(
      "button",
      `analysis-move${move.ply === analysisState.selectedPly ? " is-selected" : ""}`,
    );
    button.type = "button";
    button.dataset.analysisPly = String(move.ply);
    button.setAttribute("aria-pressed", String(move.ply === analysisState.selectedPly));
    const number = move.color === "white" ? `${move.move_number}.` : `${move.move_number}\u2026`;
    const badge = createElement(
      "span",
      `analysis-badge ${move.classification}`,
      capitalize(move.classification),
    );
    button.append(
      createElement("span", "analysis-move-number", number),
      createElement("span", "analysis-move-san", move.san),
      badge,
      createElement("span", "analysis-move-eval", formatEvaluation(move.evaluation_cp)),
    );
    fragment.append(button);
  });
  elements.analysisMoveList.replaceChildren(fragment);
  elements.analysisMoveList.querySelector(".is-selected")?.scrollIntoView({ block: "nearest" });
}

function renderAnalysisDetails() {
  const ply = analysisState.selectedPly;
  const point = analysisState.data.evaluations[ply];
  const move = ply > 0 ? analysisState.data.moves[ply - 1] : null;
  const recommendation = move || analysisState.data.moves[0];
  const classification = move?.classification || "";

  elements.analysisBadge.className = `analysis-badge ${classification}`.trim();
  elements.analysisBadge.textContent = move ? capitalize(classification) : "Start";
  elements.analysisMoveTitle.textContent = move
    ? `${move.move_number}${move.color === "white" ? "." : "\u2026"} ${move.san}`
    : "Starting position";
  elements.analysisMoveExplanation.textContent = move
    ? describeMoveReview(move)
    : "Select a move or graph point to inspect how the evaluation changed.";
  const evaluation = formatEvaluation(point.evaluation_cp);
  elements.selectedEvaluation.textContent = evaluation;
  elements.analysisEvaluationDetail.textContent = evaluation;
  elements.analysisMaterialDetail.textContent = formatMaterial(point.material_difference);
  elements.analysisLossDetail.textContent = move ? `${move.centipawn_loss} cp` : "\u2014";
  elements.analysisBestMove.textContent = recommendation?.best_move_san || "No move";
  elements.analysisBestLine.textContent = recommendation?.best_line_san?.length
    ? recommendation.best_line_san.join(" ")
    : "No continuation is available for this position.";
  elements.analysisPositionCount.textContent =
    `Position ${ply} of ${analysisState.data.moves.length}`;
  elements.previousAnalysisButton.disabled = ply === 0;
  elements.nextAnalysisButton.disabled = ply === analysisState.data.moves.length;
}

function describeMoveReview(move) {
  const label = capitalize(move.classification);
  if (move.classification === "best") {
    return `${label}: ${move.san} matched the engine's first choice.`;
  }
  const severity = {
    excellent: "kept nearly all of the position's value",
    good: "was sound, though a slightly stronger continuation existed",
    inaccuracy: "gave away a small part of the advantage",
    mistake: "changed the position substantially",
    blunder: "caused a major evaluation swing",
  }[move.classification];
  const alternative = move.best_move_san ? ` The engine preferred ${move.best_move_san}.` : "";
  return `${label}: ${move.san} ${severity}.${alternative}`;
}

function formatClassificationCounts(counts) {
  const strongMoves = counts.best + counts.excellent + counts.good;
  return `${strongMoves} strong \u2022 ${counts.inaccuracy} inaccuracies \u2022 `
    + `${counts.mistake} mistakes \u2022 ${counts.blunder} blunders`;
}

function formatAnalysisResult(result) {
  return { "1-0": "White won", "0-1": "Black won", "1/2-1/2": "Draw" }[result]
    || "Unfinished";
}

function formatEvaluation(centipawns) {
  const value = Number(centipawns);
  if (Math.abs(value) >= 10_000) {
    return value > 0 ? "+M" : "-M";
  }
  const pawns = value / 100;
  return `${pawns >= 0 ? "+" : ""}${pawns.toFixed(2)}`;
}

function formatMaterial(difference) {
  const value = Number(difference);
  if (value === 0) return "Equal";
  return value > 0 ? `White +${value}` : `Black +${Math.abs(value)}`;
}

function createSvgElement(namespace, tag, attributes) {
  const element = document.createElementNS(namespace, tag);
  Object.entries(attributes).forEach(([name, value]) => {
    element.setAttribute(name, String(value));
  });
  return element;
}

function getSearchNotice() {
  if (!lastEngineStats?.timedOut) {
    return "";
  }

  if (lastEngineStats.depth > 0) {
    return `Time limit reached — played the best move found at depth ${lastEngineStats.depth}.`;
  }

  return "Time limit reached — played a safe legal move so the game can continue.";
}

function renderStatus() {
  if (pendingPromotion) {
    elements.statusHeading.textContent = "Choose a promotion";
    elements.statusDescription.textContent =
      "Select a queen, rook, bishop, or knight to complete your move.";
    return;
  }

  if (planningState.isPlanning) {
    renderPlanningStatus();
    return;
  }

  if (analysisState.isLoading) {
    elements.statusHeading.textContent = "Analyzing game";
    elements.statusDescription.textContent =
      "Reviewing every move and calculating evaluations, classifications, and best lines\u2026";
    return;
  }

  if (analysisState.isOpen) {
    const move = analysisState.selectedPly > 0
      ? analysisState.data.moves[analysisState.selectedPly - 1]
      : null;
    elements.statusHeading.textContent = "Game review";
    elements.statusDescription.textContent = move
      ? `Reviewing ${move.san}, classified as ${move.classification}.`
      : "Reviewing the starting position.";
    return;
  }

  if (game.isCheckmate()) {
    const winner = game.turn() === "w" ? "Black" : "White";
    elements.statusHeading.textContent = `${winner} wins`;
    elements.statusDescription.textContent = "Checkmate. Start a new game to play again.";
    return;
  }

  if (game.isDraw()) {
    elements.statusHeading.textContent = "Draw";
    elements.statusDescription.textContent = drawDescription();
    return;
  }

  if (isThinking) {
    elements.statusHeading.textContent = "Engine is thinking";
    elements.statusDescription.textContent =
      `${selectedBot.label} is searching the position at depth ${selectedBot.depth}…`;
    return;
  }

  if (lastError) {
    elements.statusHeading.textContent = "Engine paused";
    elements.statusDescription.textContent = "Your move is safe. Retry when you are ready.";
    return;
  }

  if (selectedSquare) {
    const piece = game.get(selectedSquare);
    const destinations = [...new Set(selectedMoves.map((move) => move.to))];
    const legalMoveDescription = destinations.length > 0
      ? `Legal moves: ${destinations.join(", ")}.`
      : "This piece has no legal moves.";

    elements.statusHeading.textContent =
      `${capitalize(PIECE_NAMES[piece.type])} selected`;
    elements.statusDescription.textContent = interactionMessage
      ? `${interactionMessage} ${legalMoveDescription}`
      : legalMoveDescription;
    return;
  }

  if (interactionMessage) {
    elements.statusHeading.textContent = "Choose a White piece";
    elements.statusDescription.textContent = interactionMessage;
    return;
  }

  if (promotionTestFen && game.history().length === 0) {
    elements.statusHeading.textContent = "Promotion test";
    elements.statusDescription.textContent =
      localTestName === "promotion-capture"
        ? "Capture the rook from a7 to b8, then choose the pawn's new piece."
        : "Drag the pawn from a7 to a8, then choose its new piece.";
    return;
  }

  if (analysisTestFen && game.history().length === 0) {
    elements.statusHeading.textContent = "Analysis test";
    elements.statusDescription.textContent =
      "Move the queen from f7 to g7 to checkmate, then review the game.";
    return;
  }

  const side = game.turn() === "w" ? "White" : "Black";
  elements.statusHeading.textContent = game.turn() === "w" ? "Your move" : "Engine turn";
  const turnDescription = game.isCheck()
    ? `${side} is in check.`
    : `${side} to move.`;
  elements.statusDescription.textContent =
    engineMoveAnnouncement && game.turn() === "w"
      ? `${engineMoveAnnouncement} ${turnDescription}`
      : turnDescription;
}

function renderPlanningStatus() {
  const planningGame = planningState.hypotheticalBoard;
  const activeSelectedSquare = getSelectedSquare();
  const side = planningGame.turn() === "w" ? "White" : "Black";

  if (planningGame.isCheckmate()) {
    const winner = planningGame.turn() === "w" ? "Black" : "White";
    elements.statusHeading.textContent = `${winner} wins in this line`;
    elements.statusDescription.textContent =
      "The planned sequence ends in checkmate. Undo a move to explore another line.";
    return;
  }

  if (planningGame.isDraw()) {
    elements.statusHeading.textContent = "Draw in this line";
    elements.statusDescription.textContent =
      "The planned sequence reaches a drawn position. Undo a move to continue exploring.";
    return;
  }

  if (activeSelectedSquare) {
    const piece = planningGame.get(activeSelectedSquare);
    const destinations = [...new Set(getSelectedMoves().map((move) => move.to))];
    elements.statusHeading.textContent = `${capitalize(PIECE_NAMES[piece.type])} selected`;
    elements.statusDescription.textContent = destinations.length > 0
      ? `${interactionMessage ? `${interactionMessage} ` : ""}Plan ${side}'s move to ${destinations.join(", ")}.`
      : `This ${PIECE_NAMES[piece.type]} has no legal moves in the planned position.`;
    return;
  }

  elements.statusHeading.textContent = "Planning mode active";
  const turnDescription = planningGame.isCheck()
    ? `${side} is in check in the planned position.`
    : `${side} to move in the planned position.`;
  elements.statusDescription.textContent = interactionMessage
    ? `${interactionMessage} ${turnDescription}`
    : `${turnDescription} Select a piece to see legal moves.`;
}

function drawDescription() {
  if (game.isStalemate()) return "Draw by stalemate.";
  if (game.isInsufficientMaterial()) return "Draw by insufficient material.";
  if (game.isThreefoldRepetition()) return "Draw by threefold repetition.";
  return "The game ended in a draw.";
}

function renderHistory() {
  const history = game.history();
  elements.moveCount.textContent = `${history.length} ${history.length === 1 ? "move" : "moves"}`;

  if (history.length === 0) {
    elements.moveHistory.replaceChildren(createElement("p", "empty-history", "Your moves will appear here."));
    return;
  }

  const fragment = document.createDocumentFragment();
  for (let index = 0; index < history.length; index += 2) {
    const row = createElement("div", "move-row");
    row.append(
      createElement("span", "move-number", `${index / 2 + 1}.`),
      createElement("span", "move-san", history[index]),
      createElement("span", "move-san", history[index + 1] || ""),
    );
    fragment.append(row);
  }

  elements.moveHistory.replaceChildren(fragment);
  elements.moveHistory.scrollTop = elements.moveHistory.scrollHeight;
}

function renderStats() {
  if (!lastEngineStats) {
    elements.evaluationValue.textContent = "—";
    elements.nodesValue.textContent = "—";
    return;
  }

  const pawns = lastEngineStats.score / 100;
  elements.evaluationValue.textContent = `Engine ${pawns >= 0 ? "+" : ""}${pawns.toFixed(2)}`;
  elements.nodesValue.textContent = Number.isFinite(lastEngineStats.nodes)
    ? lastEngineStats.nodes.toLocaleString()
    : "—";
}

function showDependencyError() {
  elements.dependencyAlert.hidden = false;
  const missingDependencies = [];
  if (typeof window.jQuery !== "function") missingDependencies.push("jQuery");
  if (typeof window.Chessboard !== "function") missingDependencies.push("Chessboard");
  const detail = missingDependencies.length
    ? ` Missing: ${missingDependencies.join(", ")}.`
    : "";
  elements.dependencyAlert.textContent =
    `The chess board could not load because a required local chess library did not initialize.${detail}`;
  elements.dependencyAlert.classList.add("is-error");
}

function createInitialGame() {
  return initialTestFen ? new Chess(initialTestFen) : new Chess();
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function createElement(tag, className, text = "") {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

function debounce(callback, delay) {
  let timeout;
  return (...args) => {
    window.clearTimeout(timeout);
    timeout = window.setTimeout(() => callback(...args), delay);
  };
}

initialize();
