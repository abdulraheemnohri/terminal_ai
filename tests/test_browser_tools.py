import unittest

from agent.browser_tools import register_browser_tools
from agentic_runtime import ToolRegistry


class BrowserToolTests(unittest.TestCase):
    def test_only_injected_handlers_are_registered(self):
        registry = ToolRegistry()
        registered = register_browser_tools(registry, {
            "browser.search": lambda query: {"query": query},
            "browser.submit_form": lambda page_id, selector: "submitted",
        })
        self.assertEqual(registered, ["browser.search", "browser.submit_form"])
        self.assertEqual(registry.execute("browser.search", {"query": "docs"}).ok, True)
        blocked = registry.execute("browser.submit_form", {"page_id": "p1", "selector": "button"})
        self.assertFalse(blocked.ok)
        self.assertIn("Approval required", blocked.error)

    def test_browser_schema_rejects_unknown_arguments(self):
        registry = ToolRegistry()
        register_browser_tools(registry, {"browser.search": lambda query: query})
        result = registry.execute("browser.search", {"query": "docs", "execute": True})
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
