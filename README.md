# Chess Engine

[play now]https://isaiahcampusano-chess-engine.onrender.com/

<img width="862" height="786" alt="image" src="https://github.com/user-attachments/assets/fd68e33a-c9d0-4903-b2a0-636ed743e651" />


## Opponents

Each bot has its own playing profile, defined in `bot_config.py` and shared by
personality metadata and browser move selection:

| Opponent | Maximum search depth | Blunder chance | Opening book | Move time limit |
| --- | ---: | ---: | --- | ---: |
| Rookie Randy | 1 | 15% | Never | 1 second |
| Sandbag Sam | 2 | 25% | 50% probability | 2 seconds |
| The Professor | 5 | 0% | Always when available | 8 seconds |
| Martin | 3 | 8% | 50% probability | 3 seconds |

Randy is a cheerful beginner. Sam calculates further but takes more risks.
The Professor is the strongest, most consistent opponent. Martin combines
shorter calculation with occasional mistakes and wisecracks. These settings
produce different behavior; they are not calibrated Elo ratings.

Each character reacts with offline, curated commentary. Placeholder avatars
live under `static/avatars/`. The final reaction remains visible during review.

## Opening play and search

Book policy is applied before search and blunders. If the policy permits a book
move and one exists, the existing frequency-weighted selection is retained.
A book miss resumes search. Randy never consults the book; Sam and Martin make
an independent 50% book decision on each turn. Missing or corrupt book data
logs a warning and permits normal play. The default book is loaded once per
process from the module directory, independently of the working directory.

After leaving the book, bots use iterative deepening under one per-move
deadline. A timeout returns the deepest fully completed iteration, including
its complete move rankings when needed. The browser does not restart at depth
1. If even depth 1 cannot finish, a legal emergency move reports `depth=0` and
`timed_out=True`. Configured depths are maximums, not guaranteed on every move.

When an error is triggered, 70% of the time the bot chooses uniformly among the
top three alternatives to the best move (or all alternatives if fewer exist).
The remaining 30% samples all legal moves, which can happen to select the best
move. Rankings use full-window root searches from the last completed depth;
ordinary turns retain the faster best-move search. A zero blunder probability
performs no blunder random draw. Equal-scoring alternatives can still be chosen.

Evaluation keeps material and piece-square tables and adds small terms for
legal mobility, pawn structure, bishop pairs, rook files, and king safety.
Weights are centralized in `engine.POSITIONAL_WEIGHTS`, in centipawns. King
safety scales with remaining non-pawn material. These terms add computation;
the per-move deadlines still bound search, and completed depth can vary.

`choose_best_move()` retains its public API. `choose_move_with_skill()` retains
`blunder_chance`, `rng`, and `opening_book`, and additionally accepts `depth`,
`time_limit_seconds`, `book_policy`, and `book_chance`. Its direct-call defaults
remain depth 1, 35% blunders, and a 90% book probability; browser bots explicitly
pass every profile setting. Skill search now uses negamax with quiescence,
rather than the previous static one-ply ranking.

Both selectors return `SearchResult`. Book moves report `depth=0`, `nodes=0`,
`timed_out=False`, and a static score after the move from the mover's perspective.
HTTP response fields are unchanged. `opening_book=None` (the default) means pure
search. Supply `rng=random.Random(seed)` for reproducible choices, using no time
limit when reproducibility must also be independent of machine speed.

The terminal opponent keeps its shared book and `--depth` behavior (default 3).
The live evaluation bar stays at depth 3; game review and evaluation never use
the book.

Run all tests from the repository directory:

```sh
python -m unittest discover -s tests
```

## Rebuilding the book

The bundled data is derived from all twelve 2013 standard rated-game archives in
the [Lichess open database](https://database.lichess.org/), released under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
`opening_book.sources.json` records each archive URL, SHA-256 checksum, game counts,
build settings, and the generated book checksum. These are online games, not a
master-only or engine-certified repertoire; frequency is a diversity heuristic,
not a guarantee that every move is optimal.

Download the archives to a directory outside this repository and verify them against
[Lichess's published checksums](https://database.lichess.org/standard/sha256sums.txt).
Install the regular requirements plus `requirements-book.txt` to read `.pgn.zst`.
Uncompressed `.pgn` files require only the regular requirements. Python 3.11+ is
required for the builder. From the repository directory, rebuild in PowerShell:

```powershell
python -m pip install -r requirements.txt -r requirements-book.txt
$archives = Get-ChildItem /path/to/archives/lichess_db_standard_rated_2013-*.pgn.zst | Select-Object -ExpandProperty FullName
python build_opening_book.py @archives --source-base-url https://database.lichess.org/standard --license CC0-1.0
```

Defaults require both ratings ≥2000, base time ≥180 seconds, and a standard starting
position. Variants, custom starts, and parser-reported malformed games are skipped.
The builder counts the first 20 plies of accepted games, combines transpositions,
keeps at most five moves per position with at least three occurrences, and uses
frequency as the weight. Equal-frequency moves are ordered by UCI for reproducible
output. Four-field FEN keys exclude counters and retain castling rights and only
legally available en-passant targets. The 20-ply limit applies when extracting
games; runtime lookup is position-based and does not impose a move-counter cutoff.

Run verification with `python -m unittest discover -s tests`. Compression tests are
skipped if the optional builder dependency is absent.

