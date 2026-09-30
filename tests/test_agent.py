import unittest
from unittest.mock import Mock

from desktop_agent.agent import Agent


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.client, self.desktop = Mock(), Mock()
        self.agent = Agent(self.client, {"firefox": {"command": ["firefox"], "aliases": ["browser"]}},
            self.desktop, {"confidence_threshold": 0.8, "probability_threshold": 0.8})
        self.answer = {"type": "choice", "choice": "open_firefox", "confidence": 0.95,
                       "probabilities": {"open_firefox": 0.98, "unsupported": 0.02}}
        self.desktop.open_app.return_value = {"success": True, "verified": True}

    def process(self, answer=None):
        self.client.evaluate.return_value = {"launch": self.answer if answer is None else answer}
        return self.agent.process("Open browser")

    def test_only_code_owned_candidate_executes(self):
        self.assertTrue(self.process()["verified"])
        self.desktop.open_app.assert_called_once_with("firefox")
        state, questions = self.client.evaluate.call_args.args
        self.assertEqual(state, {"command": "Open browser"})
        self.assertIn("browser", questions["launch"]["criteria"]["open_firefox"])

    def test_dry_run_never_calls_api_or_desktop(self):
        self.assertTrue(self.agent.process("Open browser", dry_run=True)["success"])
        self.client.evaluate.assert_not_called()
        self.desktop.open_app.assert_not_called()

    def test_low_confidence_does_not_launch(self):
        answer = {**self.answer, "confidence": 0.5}
        self.assertEqual(self.process(answer)["error"], "LOW_CONFIDENCE")
        self.desktop.open_app.assert_not_called()

    def test_events_show_validated_selection_before_execution(self):
        self.client.evaluate.return_value = {"launch": self.answer}
        events = []
        def observe(event, data):
            self.desktop.open_app.assert_not_called()
            events.append((event, data))
        self.assertTrue(self.agent.process("Open browser", on_event=observe)["success"])
        self.assertEqual([event for event, _ in events], ["evaluating", "selected", "executing"])
        self.assertEqual(events[1][1]["application"], "firefox")

    def test_unknown_or_malformed_decisions_never_execute(self):
        variants = [{**self.answer, "choice": "shell"}, {**self.answer, "confidence": float("nan")},
                    {**self.answer, "confidence": True}, {**self.answer, "probabilities": {}}, None]
        for answer in variants:
            with self.subTest(answer=answer):
                self.client.evaluate.return_value = {"launch": answer}
                self.assertEqual(self.agent.process("Open browser")["error"], "INVALID_RESPONSE")
        self.desktop.open_app.assert_not_called()

    def test_unsupported_stops(self):
        answer = {**self.answer, "choice": "unsupported", "probabilities": {"open_firefox": 0.01, "unsupported": 0.99}}
        self.assertEqual(self.process(answer)["error"], "UNSUPPORTED_COMMAND")
        self.desktop.open_app.assert_not_called()

    def test_model_does_not_receive_launch_arguments(self):
        question = self.agent.question()
        self.assertNotIn("shell", question["criteria"]["open_firefox"])
