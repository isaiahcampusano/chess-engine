"""Entry point for the terminal chess engine."""

from __future__ import annotations

import argparse

import chess

from game import play


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play terminal chess against a minimax AI.")
    parser.add_argument("--depth", type=int, default=3, help="AI search depth. Start with 3.")
    parser.add_argument(
        "--color",
        choices=("white", "black"),
        default="white",
        help="Human player color.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.depth < 1:
        raise SystemExit("--depth must be at least 1")

    human_color = chess.WHITE if args.color == "white" else chess.BLACK
    play(depth=args.depth, human_color=human_color)


if __name__ == "__main__":
    main()
