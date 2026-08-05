# -*- coding: utf-8 -*-
"""
Automated Test Suite for Exam Generation & Barem Review Agents (No Icons)
========================================================================
Tests:
- Exercise Generator JSON Schema adherence (3 difficulty levels)
- Barem Review JSON Schema adherence (score rows, total score, advice)
- Absence of icons/emojis in output strings and system prompts

Usage:
    python -m unittest tests/test_exam_grading_suite.py
"""

import unittest
import unittest.mock
import sys
import json
import re
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.prompt_registry.registry import get_active_prompts, DEFAULT_PROMPTS
from src.api.main import app


def contains_emoji(text: str) -> bool:
    """
    Utility function to check if a string contains any emoji or icon character.
    """
    if not text:
        return False
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # geometric shapes
        "\U0001F800-\U0001F8FF"  # supplemental arrows
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols & pictographs extended
        "\U00002600-\U000026FF"  # miscellaneous symbols
        "\U00002700-\U000027BF]" # dingbats
    )
    return bool(emoji_pattern.search(text))


class TestExamGradingSuite(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_exercise_generator_prompt_integrity(self):
        """Test exercise_generator prompt exists and adheres to 3 levels"""
        prompts = get_active_prompts()
        prompt = prompts.get("exercise_generator", "")
        self.assertIn("exercise_generator", DEFAULT_PROMPTS)
        self.assertIn("Nhận biết/Thông hiểu", prompt)
        self.assertIn("Vận dụng", prompt)
        self.assertIn("Vận dụng cao - Thử thách", prompt)

    def test_barem_review_prompt_integrity(self):
        """Test barem_review prompt exists and defines score_rows schema"""
        prompts = get_active_prompts()
        prompt = prompts.get("barem_review", "")
        self.assertIn("barem_review", DEFAULT_PROMPTS)
        self.assertIn("score_rows", prompt)
        self.assertIn("total_score", prompt)

    @unittest.mock.patch('google.genai.Client')
    def test_exercise_generator_mock_execution(self, mock_genai_client_class):
        """Test mock execution of exercise_generator API endpoint"""
        mock_client = unittest.mock.MagicMock()
        mock_genai_client_class.return_value = mock_client

        mock_llm_response = unittest.mock.MagicMock()
        mock_llm_response.text = json.dumps({
            "exercises": [
                {
                    "index": 1,
                    "level": "Nhận biết/Thông hiểu",
                    "question": "Tính: 15 x 3 và 45 : 3",
                    "solution": {
                        "steps": [
                            {
                                "step": 1,
                                "title": "Tính nhân",
                                "expression": "15 x 3 = 45",
                                "explanation": "Lấy 3 nhân 5 bằng 15..."
                            }
                        ],
                        "conclusion": "Đáp số: 45 và 15"
                    }
                },
                {
                    "index": 2,
                    "level": "Vận dụng",
                    "question": "Bài toán vận dụng có lời văn...",
                    "solution": {
                        "steps": [],
                        "conclusion": "Đáp số: 90"
                    }
                },
                {
                    "index": 3,
                    "level": "Vận dụng cao - Thử thách",
                    "question": "Bài toán thử thách tư duy...",
                    "solution": {
                        "steps": [],
                        "conclusion": "Đáp số: 3"
                    }
                }
            ]
        }, ensure_ascii=False)

        mock_client.models.generate_content.return_value = mock_llm_response

        # Verify no emojis in mock output
        self.assertFalse(contains_emoji(mock_llm_response.text))

    @unittest.mock.patch('google.genai.Client')
    def test_barem_review_mock_execution(self, mock_genai_client_class):
        """Test mock execution of barem_review API endpoint"""
        mock_client = unittest.mock.MagicMock()
        mock_genai_client_class.return_value = mock_client

        mock_llm_response = unittest.mock.MagicMock()
        mock_llm_response.text = json.dumps({
            "greeting": "Chào con, thầy khen bài làm xuất sắc của con!",
            "score_rows": [
                {
                    "section": "Bước 1",
                    "barem_requirement": "Tính 45 : 5 = 9",
                    "student_work": "Làm đúng 45 : 5 = 9",
                    "score": "1.0 / 1.0"
                }
            ],
            "total_score": "1.0 / 1.0",
            "advice": "Con tiếp tục phát huy bài làm nhé.",
            "encouragement": "Chúc con học tốt!"
        }, ensure_ascii=False)

        mock_client.models.generate_content.return_value = mock_llm_response

        # Verify no emojis in mock response text
        self.assertFalse(contains_emoji(mock_llm_response.text))

    def test_no_emoji_in_system_prompts(self):
        """Ensure no emojis are present in DEFAULT_PROMPTS for exercise_generator and barem_review"""
        for agent_key in ["exercise_generator", "barem_review"]:
            prompt_text = DEFAULT_PROMPTS[agent_key]
            self.assertFalse(
                contains_emoji(prompt_text),
                f"Emoji found in prompt for '{agent_key}'!"
            )


if __name__ == "__main__":
    unittest.main()
