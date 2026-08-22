const STORAGE_KEY = "chess-engine-muted";

const SOUND_PATHS = {
  move: "/static/sounds/move.ogg",
  capture: "/static/sounds/capture.ogg",
  check: "/static/sounds/check.ogg",
  castle: "/static/sounds/castle.ogg",
  promote: "/static/sounds/promote.ogg",
  illegal: "/static/sounds/illegal.ogg",
  game_start: "/static/sounds/game-start.ogg",
  game_win: "/static/sounds/game-win.ogg",
  game_lose: "/static/sounds/game-lose.ogg",
  game_draw: "/static/sounds/game-draw.ogg",
};

const sounds = Object.fromEntries(
  Object.entries(SOUND_PATHS).map(([eventType, path]) => {
    const audio = new Audio(path);
    audio.preload = "auto";
    audio.volume = 0.6;
    return [eventType, audio];
  }),
);

let muted = readMutedPreference();
let lastPlayedSound = null;
const playedSounds = [];
syncDocumentSoundState();

function readMutedPreference() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function saveMutedPreference() {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(muted));
  } catch {
    // Audio still works for this session if storage is unavailable.
  }
}

function syncDocumentSoundState() {
  document.documentElement.dataset.soundMuted = String(muted);
  if (lastPlayedSound) {
    document.documentElement.dataset.lastSound = lastPlayedSound;
  }
  document.documentElement.dataset.soundEvents = playedSounds.join(",");
}

export function isMuted() {
  return muted;
}

export function toggleMuted() {
  muted = !muted;
  saveMutedPreference();
  syncDocumentSoundState();
  return muted;
}

export function playSound(eventType) {
  const audio = sounds[eventType];
  if (muted || !audio) {
    return;
  }

  lastPlayedSound = eventType;
  playedSounds.push(eventType);
  if (playedSounds.length > 20) {
    playedSounds.shift();
  }
  syncDocumentSoundState();
  audio.currentTime = 0;
  audio.play().catch(() => {
    // Browsers may block audio until the first user interaction.
  });
}

export function moveSoundType(flags = {}) {
  if (flags.is_check) return "check";
  if (flags.is_capture) return "capture";
  if (flags.is_castle) return "castle";
  if (flags.is_promotion) return "promote";
  return "move";
}

export function playMoveSound(flags) {
  playSound(moveSoundType(flags));
}

export function playOutcomeSound(outcome, playerColor = "white") {
  if (!outcome || outcome.winner == null) {
    playSound("game_draw");
    return;
  }
  playSound(outcome.winner === playerColor ? "game_win" : "game_lose");
}
