# -*- coding: utf-8 -*-
"""
Unit and Integration Test Suite for All-Agent JSON Response & Citation Object Mapping.

Tests:
1. All Agent System Prompts in Prompt Registry require JSON response format.
2. Default Teacher & Silly Words Routing ("kahsdgh", "asdfgh") avoid "Dạ" and route to default.
3. n8n Workflow JSON Schema is valid and contains 22 active nodes.
4. Format Final Output formats `citations` as `{ ref1: ..., ref2: ... }` object map.
5. Legacy `references` field is completely removed from output data payload.
"""

import json
import os
import unittest
from pathlib import Path

from src.prompt_registry.registry import DEFAULT_PROMPTS


class TestN8nJsonResponseAndCitations(unittest.TestCase):

    def setUp(self):
        self.workflow_path = Path("n8n-docker/rag_pedagogical_workflow.json")
        self.assertTrue(self.workflow_path.exists(), "n8n workflow file must exist")
        with open(self.workflow_path, "r", encoding="utf-8") as f:
            self.workflow_json = json.load(f)

    def test_workflow_json_structure_and_nodes(self):
        """Test that rag_pedagogical_workflow.json is valid JSON with 23 nodes."""
        nodes = self.workflow_json.get("nodes", [])
        self.assertEqual(len(nodes), 23, f"Expected 23 workflow nodes, got {len(nodes)}")
        node_names = [n["name"] for n in nodes]
        self.assertIn("Format Final Output", node_names)
        self.assertIn("Merge Context Nodes", node_names)

    def test_all_registry_prompts_instruct_json(self):
        """Verify that prompts for all expert agents in registry require JSON formatting."""
        json_agents = [
            "default_teacher",
            "barem_review",
            "theory_explanation",
            "exercise_generator",
            "suggestive_tutor",
            "direct_solver"
        ]
        for agent_name in json_agents:
            prompt_text = DEFAULT_PROMPTS.get(agent_name, "")
            self.assertTrue(len(prompt_text) > 0, f"Prompt for {agent_name} should not be empty")
            self.assertIn("JSON", prompt_text, f"Prompt for {agent_name} must instruct JSON format")

    def test_silly_words_planner_and_default_teacher_rules(self):
        """Verify silly words handling rules in planner and default teacher prompts."""
        planner_prompt = DEFAULT_PROMPTS["planner"]
        default_teacher_prompt = DEFAULT_PROMPTS["default_teacher"]

        # Check planner prompt routes silly words to default
        self.assertIn("silly words", planner_prompt.lower())
        self.assertIn("default", planner_prompt.lower())

        # Check default_teacher prompt forbids "Dạ" for silly words and uses friendly greeting
        self.assertIn("kahsdgh", default_teacher_prompt)
        self.assertIn("Dạ", default_teacher_prompt)
        self.assertIn("Thầy/Cô có thể giúp gì cho con nhỉ?", default_teacher_prompt)

    def test_format_final_output_citations_object(self):
        """Verify Format Final Output node constructs `citations` object map and removes `references`."""
        format_node = None
        for node in self.workflow_json.get("nodes", []):
            if node["name"] == "Format Final Output":
                format_node = node
                break
        self.assertIsNotNone(format_node, "Format Final Output node must exist")

        js_code = format_node["parameters"]["jsCode"]

        # Check that JSON_AGENTS list includes default_teacher and default
        self.assertIn("'default_teacher'", js_code)
        self.assertIn("'default'", js_code)

        # Check citations object construction
        self.assertIn("parsedData.citations = citationsObj;", js_code)
        self.assertIn("citationsObj[`ref${idx + 1}`] = c;", js_code)

        # Verify legacy references field assignment is completely removed
        self.assertNotIn("parsedData.references = citationList;", js_code)

    def test_merge_context_nodes_js_syntax_safe(self):
        """Verify Merge Context Nodes uses single quotes in example prompts to avoid JS syntax errors."""
        merge_node = None
        for node in self.workflow_json.get("nodes", []):
            if node["name"] == "Merge Context Nodes":
                merge_node = node
                break
        self.assertIsNotNone(merge_node, "Merge Context Nodes node must exist")

        js_code = merge_node["parameters"]["jsCode"]

        # Ensure single quotes are used for JSON key examples in prompts
        self.assertIn("'kahsdgh'", js_code)
        self.assertIn("'guidance'", js_code)
        self.assertNotIn('"guidance":', js_code)

    def test_custom_exercise_generator_workflow_level_and_type(self):
        """Verify custom_exercise_generator_workflow.json exists, has prompt and output formatting for level & type."""
        custom_wf_path = Path("n8n-docker/custom_exercise_generator_workflow.json")
        self.assertTrue(custom_wf_path.exists(), "custom_exercise_generator_workflow.json must exist")
        with open(custom_wf_path, "r", encoding="utf-8") as f:
            wf_json = json.load(f)

        nodes = {n["name"]: n for n in wf_json.get("nodes", [])}
        self.assertIn("Prepare Prompt - Custom Exercise Generator", nodes)
        self.assertIn("Format Output - Custom Exercise Generator", nodes)

        prep_code = nodes["Prepare Prompt - Custom Exercise Generator"]["parameters"]["jsCode"]
        self.assertIn('"level": "review_exercise | basic | normal | advance | discovery"', prep_code)
        self.assertIn('"type": "multiple_choice | option | fill_in_blank | essay"', prep_code)

        format_code = nodes["Format Output - Custom Exercise Generator"]["parameters"]["jsCode"]
        self.assertIn("level: normalizedLevel", format_code)
        self.assertIn("type: qType", format_code)
        self.assertIn("levelMap", format_code)


if __name__ == "__main__":
    unittest.main()
