import json
import tempfile
import unittest
from pathlib import Path

from agent.adaptive_planner import AdaptivePlanner
from agent.approvals import ApprovalStore
from agent.skills import validate_skill
from agent.world_model import WorldModel


class AdaptiveAgentTests(unittest.TestCase):
    def test_planner_requires_review_for_side_effects(self):
        plan = AdaptivePlanner().choose("send an email", external_side_effects=True)
        self.assertEqual(plan["strategy"], "review_execute")
        self.assertTrue(plan["requires_approval"])

    def test_planner_rejects_invalid_scores(self):
        with self.assertRaises(ValueError):
            AdaptivePlanner().choose("task", complexity=1.5)

    def test_world_model_preserves_contradictions(self):
        with tempfile.TemporaryDirectory() as directory:
            model = WorldModel(Path(directory) / "world.json")
            model.observe("service.status", "up", source="healthcheck", confidence=.9)
            model.observe("service.status", "down", source="operator note", confidence=.7)
            self.assertTrue(model.contradictions("service.status"))
            self.assertEqual(len(model.query("service.status")), 2)
            reloaded = WorldModel(Path(directory) / "world.json")
            self.assertTrue(reloaded.contradictions("service.status"))

    def test_approval_is_single_use_and_tool_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ApprovalStore(Path(directory) / "approvals.json")
            request = store.request(tool="browser.read_page", arguments={"url": "https://example.com"},
                                    risk="low", reason="Read documentation")
            store.decide(request["id"], approve=True, actor="user")
            self.assertFalse(store.can_execute(request["id"], tool="browser.click"))
            self.assertTrue(store.consume(request["id"], tool="browser.read_page"))
            self.assertFalse(store.consume(request["id"], tool="browser.read_page"))

    def test_high_risk_cannot_use_low_risk_approval_path(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ApprovalStore(Path(directory) / "approvals.json")
            request = store.request(tool="shell.run", arguments={"command": "x"},
                                    risk="critical", reason="Test")
            store.decide(request["id"], approve=True, actor="user")
            self.assertFalse(store.can_execute(request["id"], tool="shell.run"))

    def test_skill_rejects_unlisted_tool(self):
        with self.assertRaises(ValueError):
            validate_skill({"name": "test_skill", "description": "Test",
                            "steps": [{"type": "tool", "tool": "shell.run"}]},
                           allowed_tools={"browser.read_page"})

    def test_skill_rejects_code_execution_step(self):
        with self.assertRaises(ValueError):
            validate_skill({"name": "test_skill", "description": "Test",
                            "steps": [{"type": "python", "code": "print(1)"}]})


if __name__ == "__main__":
    unittest.main()
