# Python Chess Engine

Play against a depth-3 minimax chess engine in the browser:
https://isaiahcampusano-chess-engine.onrender.com/

Post-game reviews use Stockfish when `STOCKFISH_PATH` points to a UCI
executable, with the built-in minimax evaluator as the local fallback. The
Render Blueprint installs a pinned, checksum-verified Stockfish 18 binary and
sets `REQUIRE_STOCKFISH=true` so production cannot silently use the fallback.
