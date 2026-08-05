import unittest
import json
from pathlib import Path

class TestHousesN8NWorkflow(unittest.TestCase):

    def test_n8n_json_syntactically_valid(self):
        workflow_path = Path(__file__).parent.parent / "n8n-docker" / "real_estate_consultant_workflow.json"
        self.assertTrue(workflow_path.exists(), f"n8n workflow file not found at {workflow_path}")

        # Try to parse the JSON
        with open(workflow_path, "r", encoding="utf-8") as f:
            try:
                workflow = json.load(f)
            except json.JSONDecodeError as e:
                self.fail(f"n8n workflow is not a valid JSON file: {e}")

        # Validate top-level keys
        self.assertIn("name", workflow)
        self.assertIn("nodes", workflow)
        self.assertIn("connections", workflow)

        # Validate nodes list
        nodes = workflow["nodes"]
        self.assertIsInstance(nodes, list)
        self.assertGreater(len(nodes), 0)

        # Ensure all required nodes exist by name
        node_names = [node["name"] for node in nodes]
        required_names = ["Webhook", "Search Houses", "Format Context", "Consultant LLM", "Respond to Webhook"]
        for name in required_names:
            self.assertIn(name, node_names, f"Required node '{name}' is missing from workflow")

        # Validate connections dict
        connections = workflow["connections"]
        self.assertIsInstance(connections, dict)
        
        # Verify connections are correctly structured
        for source_node, conn_types in connections.items():
            self.assertIn(source_node, node_names, f"Connection source '{source_node}' refers to a non-existent node")
            self.assertIn("main", conn_types)
            for path in conn_types["main"]:
                for dest in path:
                    self.assertIn(dest["node"], node_names, f"Connection target '{dest['node']}' refers to a non-existent node")

        # Specific node property check: Webhook path
        webhook_node = next(node for node in nodes if node["name"] == "Webhook")
        self.assertEqual(webhook_node["parameters"].get("path"), "real-estate-consultant")
        self.assertEqual(webhook_node["parameters"].get("httpMethod"), "POST")

        # Specific node property check: Search Houses HTTP Request URL
        search_node = next(node for node in nodes if node["name"] == "Search Houses")
        self.assertIn("api/houses/search", search_node["parameters"].get("url", ""))

        # Specific node property check: Consultant LLM HTTP Request URL
        llm_node = next(node for node in nodes if node["name"] == "Consultant LLM")
        self.assertIn("api/llm", llm_node["parameters"].get("url", ""))


if __name__ == "__main__":
    unittest.main()
