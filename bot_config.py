"""Playing profiles keyed by the stable browser/personality identifiers."""

BOT_CONFIGS = {
    "rookie": dict(depth=1, blunder_chance=0.15, book_policy="never", book_chance=0.0, time_limit_seconds=1.0),
    "hustler": dict(depth=2, blunder_chance=0.25, book_policy="sometimes", book_chance=0.5, time_limit_seconds=2.0),
    "professor": dict(depth=5, blunder_chance=0.0, book_policy="always", book_chance=1.0, time_limit_seconds=8.0),
    "martin": dict(depth=3, blunder_chance=0.08, book_policy="sometimes", book_chance=0.5, time_limit_seconds=3.0),
}
