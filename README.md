# Python Chess Engine

Play against a depth-3 minimax chess engine in the browser:
https://isaiahcampusano-chess-engine.onrender.com/

## Move planning

Use **Plan moves** to explore a legal line without changing the live game:

1. Select the side-to-move's piece. The square is highlighted in red and yellow arrows show every legal destination.
2. Choose a destination to add the move to the hypothetical board. Continue with the other side to build a sequence.
3. Use **Undo**, **Clear**, or **Copy** to revise or export the line.
4. Choose **Exit planning** to return to the live position. Planned moves are never sent to the engine or added to game history.

## Post-game analysis

After checkmate or a draw, choose **Review game** to generate an interactive move-by-move review. The review includes:

- A centipawn evaluation graph with the equal-position line at `0.00`
- Best, excellent, good, inaccuracy, mistake, and blunder labels
- White and Black accuracy estimates and mistake counts
- Material balance after every move
- The engine's preferred move and principal variation
- Previous/Next navigation that replays each reviewed position on the board

The accuracy and classification formulas are transparent approximations; Chess.com's CAPS formula is proprietary.

### Stockfish configuration

Set `STOCKFISH_PATH` to a local Stockfish UCI executable to use Stockfish for reviews. You can optionally set `STOCKFISH_ANALYSIS_SECONDS` to control the per-position time budget (default: `0.08`). If Stockfish is unavailable, reviews automatically use the project's faster built-in minimax fallback.

## Local development

```text
pip install -r requirements.txt
flask --app app run
```

Run the test suite with `python -m unittest discover -s tests -v`.
