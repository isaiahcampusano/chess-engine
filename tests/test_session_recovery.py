import importlib.util
import os
import unittest
from unittest.mock import patch

import chess

import app as web_app
from engine import SearchResult


class SessionRecoveryTests(unittest.TestCase):
    def test_missing_and_stale_sessions_return_recoverable_error(self):
        for stale in (False, True):
            with self.subTest(stale=stale):
                client = web_app.app.test_client()
                if stale:
                    with client.session_transaction() as state:
                        state.update(opponent_selected=True, active_game_bot="removed")
                with patch.object(web_app, "choose_move_with_skill") as search:
                    response = client.post("/move", json={"fen": chess.STARTING_FEN})
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json, {
                    "error": "Choose an opponent before starting the game.",
                    "code": "opponent_selection_required",
                    "needs_selection": True,
                })
                search.assert_not_called()

    def test_reselection_resumes_each_bot_at_existing_position(self):
        board = chess.Board()
        board.push_uci("e2e4")
        for bot_id in web_app.BOTS:
            with self.subTest(bot_id=bot_id):
                client = web_app.app.test_client()
                self.assertEqual(client.post("/move", json={"fen": board.fen()}).status_code, 409)
                self.assertEqual(client.post("/select_bot", json={"bot_id": bot_id}).json["selected"], bot_id)
                result = SearchResult(move=chess.Move.from_uci("e7e5"), score=0, nodes=1, depth=1)
                with patch.object(web_app, "choose_move_with_skill", return_value=result) as search:
                    response = client.post("/move", json={"fen": board.fen()})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json["engine_move"], "e7e5")
                self.assertEqual(search.call_args.args[0].fen(), board.fen())
                conflict = client.post("/select_bot", json={"bot_id": "rookie"})
                self.assertEqual(conflict.status_code, 409)
                self.assertNotIn("code", conflict.json)

    def test_cookie_survives_new_app_instance_only_with_same_key(self):
        def instance(key):
            spec = importlib.util.spec_from_file_location("session_test_app", web_app.__file__)
            module = importlib.util.module_from_spec(spec)
            with patch.dict(os.environ, {"SECRET_KEY": key}):
                spec.loader.exec_module(module)
            module.app.config.update(TESTING=True)
            return module.app.test_client()

        first = instance("test-only-persistent-key")
        first.post("/select_bot", json={"bot_id": "martin"})
        cookie = first.get_cookie("session").value
        restarted = instance("test-only-persistent-key")
        restarted.set_cookie("session", cookie)
        self.assertEqual(restarted.get("/select_bot").json["selected"], "martin")
        changed = instance("test-only-different-key")
        changed.set_cookie("session", cookie)
        response = changed.post("/move", json={"fen": chess.STARTING_FEN})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["code"], "opponent_selection_required")
