# Python Chess Engine

Terminal chess against a minimax AI, inspired by commonLuke's YouTube chess project and adapted to use `python-chess` for legal move generation.

## What This Builds

commonLuke manually built board dictionaries, per-piece movement, collision detection, castling, en passant, captures, and check detection. This version delegates those rules to `python-chess`, then adds the portfolio-worthy part: a minimax-based AI that evaluates positions and chooses legal moves.

## Run It

```bash
pip install -r requirements.txt
python main.py
```

Optional settings:

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
├── engine.py          # Minimax AI and board evaluation
├── game.py            # Terminal display, input, and game loop
├── main.py            # Command-line entry point
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
