import unittest
from unittest.mock import patch

import chess

import app as web_app
from engine import SearchResult


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        web_app.app.config.update(TESTING=True)
        self.client = web_app.app.test_client()

    def test_home_page_is_served(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Python Chess Engine", response.data)

    def test_home_page_includes_all_promotion_choices(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="promotionDialog"', response.data)
            for piece in (b"q", b"r", b"b", b"n"):
                with self.subTest(piece=piece):
                    self.assertIn(b'data-promotion="' + piece + b'"', response.data)

    def test_home_page_includes_accessible_board_instructions(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="boardInstructions"', response.data)
            self.assertIn(b'aria-describedby="boardInstructions"', response.data)
            self.assertIn(b"Use the arrow keys", response.data)

    def test_home_page_includes_move_planning_controls(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            for element_id in (
                b"planningArrows",
                b"planningCard",
                b"planningSequence",
                b"planMovesButton",
                b"undoPlanButton",
                b"clearPlanButton",
                b"copyPlanButton",
            ):
                with self.subTest(element_id=element_id):
                    self.assertIn(b'id="' + element_id + b'"', response.data)

            self.assertIn(b'aria-pressed="false"', response.data)

    def test_home_page_includes_post_game_analysis_ui(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            for element_id in (
                b"reviewGameButton",
                b"analysisPanel",
                b"analysisGraph",
                b"analysisMoveList",
                b"whiteAccuracy",
                b"blackAccuracy",
                b"analysisBestLine",
                b"previousAnalysisButton",
                b"nextAnalysisButton",
            ):
                with self.subTest(element_id=element_id):
                    self.assertIn(b'id="' + element_id + b'"', response.data)

    def test_home_page_includes_live_evaluation_bar(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            for element_id in (b"evalBar", b"evalBlackFill", b"evalWhiteFill", b"evalBarScore"):
                with self.subTest(element_id=element_id):
                    self.assertIn(b'id="' + element_id + b'"', response.data)

    def test_home_page_includes_bot_selector(self) -> None:
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'data-bot="novice"', response.data)
            self.assertIn(b'data-bot="expert"', response.data)
            self.assertIn(b'id="botSelectionStatus"', response.data)

    def test_bot_selection_defaults_to_expert(self) -> None:
        response = self.client.get("/select_bot")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "status": "ok",
                "selected": "expert",
                "depth": 3,
                "label": "Expert",
                "active_game_bot": "expert",
                "game_active": False,
            },
        )

    def test_bot_selection_is_stored_in_session(self) -> None:
        response = self.client.post("/select_bot", json={"bot_id": "novice"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["selected"], "novice")
        self.assertEqual(self.client.get("/select_bot").get_json()["selected"], "novice")

    def test_bot_selection_rejects_invalid_bot(self) -> None:
        response = self.client.post("/select_bot", json={"bot_id": "grandmaster"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid bot ID", response.get_json()["error"])

    def test_new_game_uses_preferred_bot_and_opens_selection(self) -> None:
        self.client.post("/select_bot", json={"bot_id": "novice"})

        response = self.client.post("/new_game")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["bot"], "novice")
        self.assertFalse(response.get_json()["game_active"])
        with self.client.session_transaction() as game_session:
            self.assertEqual(game_session["active_game_bot"], "novice")
            self.assertFalse(game_session["game_started"])

    def test_static_assets_are_served(self) -> None:
        for path in ("/static/styles.css", "/static/app.js"):
            with self.subTest(path=path):
                with self.client.get(path) as response:
                    self.assertEqual(response.status_code, 200)

    def test_move_endpoint_returns_engine_result(self) -> None:
        board = chess.Board()
        board.push_uci("e2e4")
        result = SearchResult(
            move=chess.Move.from_uci("e7e5"),
            score=24,
            nodes=1_234,
            depth=3,
        )

        with patch("app.choose_best_move", return_value=result) as search:
            response = self.client.post("/move", json={"fen": board.fen()})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "engine_move": "e7e5",
                "score": 24,
                "nodes": 1_234,
                "depth": 3,
                "timed_out": False,
                "game_over": False,
            },
        )
        searched_board = search.call_args.args[0]
        self.assertEqual(searched_board.fen(), board.fen())
        self.assertEqual(search.call_args.kwargs["depth"], 3)
        self.assertEqual(search.call_args.kwargs["time_limit_seconds"], 8.0)

    def test_move_endpoint_uses_selected_bot_depth(self) -> None:
        board = chess.Board()
        result = SearchResult(
            move=chess.Move.from_uci("e2e4"),
            score=12,
            nodes=20,
            depth=1,
        )
        self.client.post("/select_bot", json={"bot_id": "novice"})

        with patch("app.choose_best_move", return_value=result) as search:
            response = self.client.post("/move", json={"fen": board.fen()})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(search.call_args.kwargs["depth"], 1)

    def test_active_game_bot_stays_frozen_when_preference_changes(self) -> None:
        board = chess.Board()
        novice_result = SearchResult(
            move=chess.Move.from_uci("e2e4"),
            score=12,
            nodes=20,
            depth=1,
        )
        self.client.post("/select_bot", json={"bot_id": "novice"})
        self.client.post("/new_game")

        with patch("app.choose_best_move", return_value=novice_result) as search:
            first_move = self.client.post("/move", json={"fen": board.fen()})
            selection = self.client.post("/select_bot", json={"bot_id": "expert"})
            second_move = self.client.post("/move", json={"fen": board.fen()})

        self.assertEqual(first_move.status_code, 200)
        self.assertEqual(second_move.status_code, 200)
        self.assertEqual(selection.get_json()["status"], "preference_saved")
        self.assertEqual(selection.get_json()["current_game_bot"], "novice")
        self.assertEqual([call.kwargs["depth"] for call in search.call_args_list], [1, 1])

    def test_saved_preference_applies_to_the_next_new_game(self) -> None:
        board = chess.Board()
        result = SearchResult(
            move=chess.Move.from_uci("e2e4"),
            score=12,
            nodes=20,
            depth=3,
        )
        self.client.post("/select_bot", json={"bot_id": "novice"})
        self.client.post("/new_game")
        with patch("app.choose_best_move", return_value=result):
            self.client.post("/move", json={"fen": board.fen()})
        self.client.post("/select_bot", json={"bot_id": "expert"})

        new_game_response = self.client.post("/new_game")
        with patch("app.choose_best_move", return_value=result) as search:
            move_response = self.client.post("/move", json={"fen": board.fen()})

        self.assertEqual(new_game_response.get_json()["bot"], "expert")
        self.assertEqual(move_response.status_code, 200)
        self.assertEqual(search.call_args.kwargs["depth"], 3)

    def test_move_endpoint_rejects_missing_json(self) -> None:
        response = self.client.post("/move")

        self.assertEqual(response.status_code, 400)
        self.assertIn("JSON object", response.get_json()["error"])

    def test_move_endpoint_rejects_missing_fen(self) -> None:
        response = self.client.post("/move", json={})

        self.assertEqual(response.status_code, 400)
        self.assertIn("'fen'", response.get_json()["error"])

    def test_move_endpoint_rejects_invalid_fen(self) -> None:
        response = self.client.post("/move", json={"fen": "not-a-fen"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid", response.get_json()["error"].lower())

    def test_move_endpoint_rejects_invalid_position(self) -> None:
        response = self.client.post(
            "/move",
            json={"fen": "8/8/8/8/8/8/8/8 w - - 0 1"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid chess position", response.get_json()["error"])

    def test_game_over_position_returns_no_move(self) -> None:
        checkmate_fen = "7k/5Q2/7K/8/8/8/8/8 b - - 0 1"

        response = self.client.post("/move", json={"fen": checkmate_fen})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "engine_move": None,
                "score": 0,
                "nodes": 0,
                "depth": 0,
                "timed_out": False,
                "game_over": True,
            },
        )

    def test_engine_failure_returns_server_error(self) -> None:
        with patch("app.choose_best_move", side_effect=RuntimeError("boom")):
            response = self.client.post("/move", json={"fen": chess.STARTING_FEN})

        self.assertEqual(response.status_code, 500)
        self.assertIn("could not calculate", response.get_json()["error"])

    def test_illegal_engine_move_returns_server_error(self) -> None:
        result = SearchResult(
            move=chess.Move.from_uci("a1a8"),
            score=0,
            nodes=1,
        )
        with patch("app.choose_best_move", return_value=result):
            response = self.client.post("/move", json={"fen": chess.STARTING_FEN})

        self.assertEqual(response.status_code, 500)
        self.assertIn("legal move", response.get_json()["error"])

    def test_timed_out_search_returns_best_available_move(self) -> None:
        result = SearchResult(
            move=chess.Move.from_uci("e2e4"),
            score=12,
            nodes=80,
            depth=1,
            timed_out=True,
        )
        with patch("app.choose_best_move", return_value=result):
            response = self.client.post("/move", json={"fen": chess.STARTING_FEN})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["engine_move"], "e2e4")
        self.assertEqual(response.get_json()["depth"], 1)
        self.assertTrue(response.get_json()["timed_out"])

    def test_analysis_endpoint_returns_review_data(self) -> None:
        analysis_result = {
            "engine": "Test engine",
            "moves": [{"san": "e4", "classification": "best"}],
            "evaluations": [{"ply": 0, "evaluation_cp": 0}],
            "summary": {"white_accuracy": 100.0, "black_accuracy": 100.0},
        }
        with patch("app.analyse_game", return_value=analysis_result) as analyze:
            response = self.client.post(
                "/analysis",
                json={"moves": ["e2e4"], "start_fen": chess.STARTING_FEN},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), analysis_result)
        analyze.assert_called_once_with(["e2e4"], start_fen=chess.STARTING_FEN)

    def test_analysis_endpoint_rejects_missing_moves(self) -> None:
        response = self.client.post("/analysis", json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("'moves'", response.get_json()["error"])

    def test_analysis_endpoint_rejects_invalid_game(self) -> None:
        with patch("app.analyse_game", side_effect=ValueError("Move 1 is not legal.")):
            response = self.client.post("/analysis", json={"moves": ["e2e5"]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("not legal", response.get_json()["error"])

    def test_evaluation_endpoint_returns_engine_evaluation(self) -> None:
        result = {"eval": 35, "mate": None, "winner": None}
        with patch("app.get_evaluation", return_value=result) as evaluate:
            response = self.client.post("/api/eval", json={"fen": chess.STARTING_FEN})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), result)
        evaluated_board = evaluate.call_args.args[0]
        self.assertEqual(evaluated_board.fen(), chess.STARTING_FEN)
        self.assertEqual(evaluate.call_args.kwargs["depth"], 3)

    def test_evaluation_endpoint_rejects_invalid_fen(self) -> None:
        response = self.client.post("/api/eval", json={"fen": "not-a-fen"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid", response.get_json()["error"].lower())


if __name__ == "__main__":
    unittest.main()
