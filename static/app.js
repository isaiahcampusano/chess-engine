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
  retryButton: document.querySelector("#retryButton"),
  searchNotice: document.querySelector("#searchNotice"),
  statusDescription: document.querySelector("#statusDescription"),
  statusHeading: document.querySelector("#statusHeading"),
  thinkingPill: document.querySelector("#thinkingPill"),
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
  }, 100));

  window.chessAppReady = true;
  elements.dependencyAlert.hidden = true;
  elements.dependencyAlert.classList.remove("is-error");
  render();
}

function onDragStart(source, piece) {
  if (
    isThinking ||
    pendingPromotion ||
    game.isGameOver() ||
    game.turn() !== "w" ||
    piece.startsWith("b")
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

  if (playPlayerMove({ from: source, to: target })) {
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

function isPromotionAttempt(source, target) {
  const piece = game.get(source);
  return piece?.type === "p" && piece.color === "w" && target.endsWith("8");
}

function isLegalPromotionTarget(source, target) {
  return game.moves({ verbose: true }).some(
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

  if (!playPlayerMove(moveOptions)) {
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

  if (event.key === "Escape" && selectedSquare) {
    event.preventDefault();
    clearSelection();
  }
}

function activateSquare(square) {
  if (isThinking || pendingPromotion || game.isGameOver() || game.turn() !== "w") {
    return;
  }

  const piece = game.get(square);
  if (!selectedSquare) {
    selectPiece(square);
    return;
  }

  if (square === selectedSquare) {
    clearSelection();
    return;
  }

  const matchingMoves = selectedMoves.filter((move) => move.to === square);
  if (matchingMoves.length > 0) {
    if (matchingMoves.some((move) => PROMOTION_PIECES.has(move.promotion))) {
      openPromotionChooser(selectedSquare, square);
      return;
    }

    playPlayerMove({ from: selectedSquare, to: square });
    return;
  }

  if (piece?.color === "w") {
    selectPiece(square);
    return;
  }

  interactionMessage = `${square} is not a legal destination for the selected piece.`;
  render();
}

function selectPiece(square) {
  const piece = game.get(square);
  if (
    !piece ||
    piece.color !== "w" ||
    isThinking ||
    pendingPromotion ||
    game.isGameOver() ||
    game.turn() !== "w"
  ) {
    interactionMessage = piece
      ? "You can only select one of your White pieces."
      : `${square} is empty. Select one of your White pieces first.`;
    render();
    return false;
  }

  selectedSquare = square;
  selectedMoves = game.moves({ square, verbose: true });
  focusedSquare = square;
  interactionMessage = "";
  render();
  return true;
}

function clearSelection(shouldRender = true) {
  selectedSquare = null;
  selectedMoves = [];
  interactionMessage = "";
  if (shouldRender) {
    render();
  }
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
  window.requestAnimationFrame(renderBoardAccessibility);
}

function renderBoardAccessibility() {
  const squares = elements.board.querySelectorAll(".square-55d63");
  squares.forEach((element) => {
    const square = squareNameFromElement(element);
    if (!square) {
      return;
    }

    const matchingMoves = selectedMoves.filter((move) => move.to === square);
    const isCapture = matchingMoves.some((move) => Boolean(move.captured));

    element.classList.toggle("is-selected", square === selectedSquare);
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
    element.setAttribute("aria-selected", String(square === selectedSquare));
    element.setAttribute(
      "aria-disabled",
      String(isThinking || game.isGameOver() || game.turn() !== "w"),
    );
    element.setAttribute("aria-label", describeSquare(square, matchingMoves));
    element.tabIndex = square === focusedSquare ? 0 : -1;
  });
}

function describeSquare(square, matchingMoves) {
  const piece = game.get(square);
  const descriptions = [
    square,
    piece ? `${piece.color === "w" ? "White" : "Black"} ${PIECE_NAMES[piece.type]}` : "empty",
  ];

  if (square === selectedSquare) {
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
  board.position(game.fen(), useAnimation);
  scheduleBoardAccessibilityRender();
}

async function requestEngineMove() {
  if (isThinking || game.isGameOver() || game.turn() !== "b") {
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
  game = createInitialGame();
  focusedSquare = promotionTestFen ? "a7" : "e2";
  syncBoard(false);
  render();
}

function render() {
  renderStatus();
  renderHistory();
  renderStats();

  const canRetry = Boolean(lastError) && !game.isGameOver() && game.turn() === "b";
  elements.retryButton.hidden = !canRetry;
  elements.errorBox.hidden = !lastError;
  elements.errorBox.textContent = lastError;
  const searchMessage = getSearchNotice();
  elements.searchNotice.hidden = !searchMessage;
  elements.searchNotice.textContent = searchMessage;
  elements.boardOverlay.hidden = !isThinking;
  elements.thinkingPill.hidden = !isThinking;
  scheduleBoardAccessibilityRender();
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

  if (pendingPromotion) {
    elements.statusHeading.textContent = "Choose a promotion";
    elements.statusDescription.textContent =
      "Select a queen, rook, bishop, or knight to complete your move.";
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
