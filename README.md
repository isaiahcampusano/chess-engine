# Python Chess Engine

Play against a depth-3 minimax chess engine in the browser:
https://isaiahcampusano-chess-engine.onrender.com/

## Move planning

Use **Plan moves** to explore a legal line without changing the live game:

1. Select the side-to-move's piece. The square is highlighted in red and yellow arrows show every legal destination.
2. Choose a destination to add the move to the hypothetical board. Continue with the other side to build a sequence.
3. Use **Undo**, **Clear**, or **Copy** to revise or export the line.
4. Choose **Exit planning** to return to the live position. Planned moves are never sent to the engine or added to game history.

## Local development

```text
pip install -r requirements.txt
flask --app app run
```

Run the test suite with `python -m unittest discover -s tests -v`.
