import { Chess } from "https://cdn.jsdelivr.net/npm/chess.js@1.4.0/+esm";

const PIECE_THEME =
  "https://cdn.jsdelivr.net/gh/oakmac/chessboardjs@v1.0.0/website/img/chesspieces/wikipedia/{piece}.png";
const CLIENT_TIMEOUT_MS = 12_000;
const PROMOTION_TEST_FEN = "7k/P7/8/8/8/8/8/7K w - - 0 1";
const PROMOTION_CAPTURE_TEST_FEN = "1r5k/P7/8/8/8/8/8/7K w - - 0 1";
const PROMOTION_PIECES = new Set(["q", "r", "b", "n"]);
const BOARD_FILES = "abcdefgh";
const PIECE_NAMES = {
  p: "pawn",
  n: "knight",
  b: "bishop",
  r: "rook",
  q: "queen",
  k: "king",
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
}[localTestName] || null;

const elements = {
  board: document.querySelector("#myBoard"),
  boardOverlay: document.querySelector("#boardOverlay"),
  clearPlanButton: document.querySelector("#clearPlanButton"),
  copyPlanButton: document.querySelector("#copyPlanButton"),
  cancelPromotionButton: document.querySelector("#cancelPromotionButton"),
  dependencyAlert: document.querySelector("#dependencyAlert"),
  errorBox: document.querySelector("#errorBox"),
  evaluationValue: document.querySelector("#evaluationValue"),
  moveCount: document.querySelector("#moveCount"),
  moveHistory: document.querySelector("#moveHistory"),
  newGameButton: document.querySelector("#newGameButton"),
  nodesValue: document.querySelector("#nodesValue"),
  promotionDialog: document.querySelector("#promotionDialog"),
  promotionOptions: document.querySelectorAll("[data-promotion]"),
  planMovesButton: document.querySelector("#planMovesButton"),
  planningArrows: document.querySelector("#planningArrows"),
  planningCard: document.querySelector("#planningCard"),
  planningMoveCount: document.querySelector("#planningMoveCount"),
  planningSequence: document.querySelector("#planningSequence"),
  retryButton: document.querySelector("#retryButton"),
  searchNotice: document.querySelector("#searchNotice"),
  statusDescription: document.querySelector("#statusDescription"),
  statusHeading: document.querySelector("#statusHeading"),
  thinkingPill: document.querySelector("#thinkingPill"),
  undoPlanButton: document.querySelector("#undoPlanButton"),
};

let game = createInitialGame();
let board;
let isThinking = false;
let lastError = "";
let lastEngineStats = null;
let activeRequestId = 0;
let pendingController = null;
let pendingPromotion = null;
let selectedSquare = null;
let selectedMoves = [];
let focusedSquare = promotionTestFen ? "a7" : "e2";
let lastMove = null;
let interactionMessage = "";
let engineMoveAnnouncement = "";
let dragInProgress = false;
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

function initialize() {
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
  elements.newGameButton.addEventListener("click", startNewGame);
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
  window.addEventListener("resize", debounce(() => {
    board.resize();
    scheduleBoardAccessibilityRender();
    renderPlanningArrows();
  }, 100));

  window.chessAppReady = true;
  elements.dependencyAlert.hidden = true;
  elements.dependencyAlert.classList.remove("is-error");
  render();
}

function onDragStart(source, piece) {
  const activeGame = getActiveGame();
  if (
    isThinking ||
    pendingPromotion ||
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
  syncBoard();
  render();

  if (!game.isGameOver() && game.turn() === "b") {
    requestEngineMove();
  }

  return true;
}

function playActiveMove(moveOptions) {
  return planningState.isPlanning
    ? playPlannedMove(moveOptions)
    : playPlayerMove(moveOptions);
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
  render();
}

function selectPiece(square) {
  const activeGame = getActiveGame();
  const piece = activeGame.get(square);
  if (
    !piece ||
    piece.color !== activeGame.turn() ||
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
  return planningState.isPlanning ? planningState.hypotheticalBoard : game;
}

function getSelectedSquare() {
  return planningState.isPlanning ? planningState.selectedSquare : selectedSquare;
}

function getSelectedMoves() {
  return selectedMoves;
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
      square === lastMove?.from || square === lastMove?.to,
    );

    element.setAttribute("role", "gridcell");
    element.setAttribute("aria-rowindex", String(9 - Number(square[1])));
    element.setAttribute("aria-colindex", String(BOARD_FILES.indexOf(square[0]) + 1));
    element.setAttribute("aria-selected", String(square === activeSelectedSquare));
    element.setAttribute(
      "aria-disabled",
      String(
        isThinking ||
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
  if (square === lastMove?.from) {
    descriptions.push("last move started here");
  }
  if (square === lastMove?.to) {
    descriptions.push("last move ended here");
  }

  return descriptions.join(", ");
}

function syncBoard(useAnimation = true) {
  board.position(getActiveGame().fen(), useAnimation);
  scheduleBoardAccessibilityRender();
}

async function requestEngineMove() {
  if (planningState.isPlanning || isThinking || game.isGameOver() || game.turn() !== "b") {
    return;
  }

  const requestId = ++activeRequestId;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), CLIENT_TIMEOUT_MS);

  pendingController = controller;
  isThinking = true;
  lastError = "";
  render();

  try {
    const response = await fetch("/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fen: game.fen() }),
      signal: controller.signal,
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "The engine request failed.");
    }

    if (requestId !== activeRequestId) {
      return;
    }

    if (data.game_over || !data.engine_move) {
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
    syncBoard();
    lastEngineStats = {
      score: Number(data.score),
      nodes: Number(data.nodes),
      depth: Number(data.depth),
      timedOut: Boolean(data.timed_out),
    };
  } catch (error) {
    if (requestId !== activeRequestId) {
      return;
    }

    lastError =
      error.name === "AbortError"
        ? "The engine request timed out. You can retry from this position."
        : error.message || "The engine could not calculate a move.";
  } finally {
    window.clearTimeout(timer);
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

  if (isThinking || pendingPromotion || game.isGameOver()) {
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

function startNewGame() {
  activeRequestId += 1;
  pendingController?.abort();
  pendingController = null;
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
  planningState.isPlanning = false;
  planningState.selectedSquare = null;
  planningState.highlightedSquares.clear();
  planningState.arrows = [];
  planningState.moveSequence = [];
  planningState.hypotheticalBoard = null;
  planningState.baseFen = null;
  planningState.predictor = null;
  game = createInitialGame();
  focusedSquare = promotionTestFen ? "a7" : "e2";
  syncBoard(false);
  render();
}

function render() {
  renderStatus();
  renderHistory();
  renderStats();
  renderPlanningPanel();

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
  elements.boardOverlay.hidden = !isThinking;
  elements.thinkingPill.hidden = !isThinking;
  elements.planMovesButton.disabled = isThinking || Boolean(pendingPromotion) || game.isGameOver();
  elements.planMovesButton.setAttribute("aria-pressed", String(planningState.isPlanning));
  elements.planMovesButton.textContent = planningState.isPlanning
    ? "Exit planning"
    : "Plan moves";
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
    elements.statusDescription.textContent = "Searching the position at depth 3…";
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
  elements.dependencyAlert.textContent =
    "The chess board could not load. Check your internet connection and refresh the page.";
  elements.dependencyAlert.classList.add("is-error");
}

function createInitialGame() {
  return promotionTestFen ? new Chess(promotionTestFen) : new Chess();
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
