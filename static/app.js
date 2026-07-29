import { Chess } from "https://cdn.jsdelivr.net/npm/chess.js@1.4.0/+esm";

const PIECE_THEME =
  "https://cdn.jsdelivr.net/gh/oakmac/chessboardjs@v1.0.0/website/img/chesspieces/wikipedia/{piece}.png";
const CLIENT_TIMEOUT_MS = 12_000;

const elements = {
  boardOverlay: document.querySelector("#boardOverlay"),
  dependencyAlert: document.querySelector("#dependencyAlert"),
  errorBox: document.querySelector("#errorBox"),
  evaluationValue: document.querySelector("#evaluationValue"),
  moveCount: document.querySelector("#moveCount"),
  moveHistory: document.querySelector("#moveHistory"),
  newGameButton: document.querySelector("#newGameButton"),
  nodesValue: document.querySelector("#nodesValue"),
  retryButton: document.querySelector("#retryButton"),
  searchNotice: document.querySelector("#searchNotice"),
  statusDescription: document.querySelector("#statusDescription"),
  statusHeading: document.querySelector("#statusHeading"),
  thinkingPill: document.querySelector("#thinkingPill"),
};

let game = new Chess();
let board;
let isThinking = false;
let lastError = "";
let lastEngineStats = null;
let activeRequestId = 0;
let pendingController = null;

function initialize() {
  if (typeof window.jQuery !== "function" || typeof window.Chessboard !== "function") {
    showDependencyError();
    return;
  }

  board = window.Chessboard("myBoard", {
    draggable: true,
    position: "start",
    orientation: "white",
    pieceTheme: PIECE_THEME,
    onDragStart,
    onDrop,
    onSnapEnd: () => board.position(game.fen()),
  });

  elements.newGameButton.addEventListener("click", startNewGame);
  elements.retryButton.addEventListener("click", requestEngineMove);
  window.addEventListener("resize", debounce(() => board.resize(), 100));

  window.chessAppReady = true;
  elements.dependencyAlert.hidden = true;
  elements.dependencyAlert.classList.remove("is-error");
  render();
}

function onDragStart(_source, piece) {
  if (
    isThinking ||
    game.isGameOver() ||
    game.turn() !== "w" ||
    piece.startsWith("b")
  ) {
    return false;
  }

  return true;
}

function onDrop(source, target) {
  let move;
  try {
    move = game.move({
      from: source,
      to: target,
      promotion: "q",
    });
  } catch {
    return "snapback";
  }

  if (!move) {
    return "snapback";
  }

  lastError = "";
  board.position(game.fen());
  render();

  if (!game.isGameOver() && game.turn() === "b") {
    requestEngineMove();
  }

  return undefined;
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
    try {
      game.move(engineMove);
    } catch {
      throw new Error("The engine returned a move the browser could not play.");
    }

    board.position(game.fen());
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
  isThinking = false;
  lastError = "";
  lastEngineStats = null;
  game = new Chess();
  board.start(false);
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

  const side = game.turn() === "w" ? "White" : "Black";
  elements.statusHeading.textContent = game.turn() === "w" ? "Your move" : "Engine turn";
  elements.statusDescription.textContent = game.isCheck()
    ? `${side} is in check.`
    : `${side} to move.`;
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
