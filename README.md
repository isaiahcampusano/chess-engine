# Python Chess Engine

Play chess against a minimax AI in a polished web interface or directly in your terminal. The project is inspired by commonLuke's YouTube chess project and adapted to use `python-chess` for legal move generation.

## What This Builds

commonLuke manually built board dictionaries, per-piece movement, collision detection, castling, en passant, captures, and check detection. This version delegates those rules to `python-chess`, then adds the portfolio-worthy part: a minimax-based AI that evaluates positions and chooses legal moves.

## Run the Web App

Python 3.9 or newer is required.

```bash
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser. You play White and the engine plays Black at search depth 3.

The board uses pinned versions of chessboard.js, chess.js, and jQuery from public CDNs, so the browser needs an internet connection to load those assets. The Python engine and Flask API run entirely on your computer.

### Web API

The browser sends the current position to `POST /move`:

```json
{"fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2"}
```

A successful search returns the engine move in UCI notation with search statistics:

```json
{"engine_move": "g1f3", "score": 15, "nodes": 1248, "game_over": false}
```

Searches are limited to 10 seconds. If a search times out, the page keeps the current position and offers a retry button.

## Run in the Terminal

```bash
python main.py
```

Optional terminal settings:

```bash
python main.py --depth 2
python main.py --depth 3 --color black
```

Use UCI move notation at the prompt:

```text
e2e4
g1f3
e7e8q
```

## Milestone Mapping

| commonLuke milestone | This version |
| --- | --- |
| Board dictionaries and square coordinates | `chess.Board()` handles board state |
| Per-piece movement logic | `board.legal_moves` handles all pieces |
| Pathfinding and collision detection | Built into `python-chess` |
| Board flipping for local play | Skipped for v0 because this is solo vs AI |
| Capturing logic | `board.push(move)` updates captures |
| Castling and en passant | Built into `python-chess` |
| Check and checkmate detection | `board.is_check()` and `board.is_game_over()` |
| AI engine | Custom minimax search in `engine.py` |

## Project Structure

```text
chess-engine/
├── app.py             # Flask web server and engine API
├── engine.py          # Minimax AI and board evaluation
├── game.py            # Terminal display, input, and game loop
├── main.py            # Command-line entry point
├── static/            # Web interface (HTML, CSS, and JavaScript)
├── tests/             # Engine and web API tests
├── requirements.txt   # python-chess dependency
└── README.md
```

## Notes

The evaluation is intentionally simple: material count in centipawns, with checkmate scored as decisive. The move search uses minimax with alpha-beta pruning and searches captures/promotions first so depth 3 stays usable.

Good post-v0 upgrades:

- Add piece-square tables for positional play.
- Add an opening book.
- Add pygame or web UI.
- Add captured-piece display.
- Add local two-player board flipping.
