"""
Real Estate House Consultant Automated Test Suite
==================================================
Comprehensive automated test suite covering all components of the house part:
- House Ingestion Pipeline (Multimodal Vision OCR + Unified Description + Vector DB Indexing)
- House Search API (POST /api/houses/search)
- House Ingest API (POST /api/houses/ingest)
- n8n Real Estate Consultant Workflow Structure & Node Connections

Usage:
    python -m unittest tests/test_houses_suite.py
"""

import unittest
import unittest.mock
import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.pipeline.houses import run_houses_ingest, load_houses_cache
from src.api.main import app
from src import config


class TestHousesSuite(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.sample_house_data = [
            {
                "id": 118,
                "latitude": 21.0162,
                "longitude": 105.9052,
                "placeName": "Nhà riêng Bát Khối",
                "streetName": "Đường Bát Khối",
                "area": 40.0,
                "actualArea": 45.0,
                "floors": 6,
                "wide": 5.0,
                "depth": 10.0,
                "offeringPrice": 11.5,
                "bedrooms": 5,
                "bathrooms": 1,
                "hasCarParking": True,
                "media": [
                    {
                        "fileName": "house_118_img1.jpg",
                        "mediaType": "image"
                    }
                ]
            },
            {
                "id": 120,
                "latitude": 21.0285,
                "longitude": 105.9012,
                "placeName": "Chung cư Northern Diamond",
                "streetName": "Đường Cổ Linh",
                "area": 107.0,
                "actualArea": 107.0,
                "floors": 1,
                "wide": 0.0,
                "depth": 0.0,
                "offeringPrice": 5.2,
                "bedrooms": 3,
                "bathrooms": 2,
                "hasCarParking": True,
                "media": []
            }
        ]

    # ----------------------------------------------------------------------
    # 1. Test House Search API Endpoint (/api/houses/search)
    # ----------------------------------------------------------------------
    @unittest.mock.patch('src.api.main.get_vector_store')
    def test_api_houses_search_location(self, mock_get_vector_store):
        """Test location-based search query via POST /api/houses/search"""
        mock_vector_store = unittest.mock.MagicMock()
        mock_get_vector_store.return_value = mock_vector_store

        mock_vector_store.query.return_value = {
            "ids": [["house_118"]],
            "documents": [["Căn nhà riêng 6 tầng tuyệt đẹp tại đường Bát Khối"]],
            "metadatas": [[{
                "house_id": 118,
                "placeName": "Nhà riêng Bát Khối",
                "streetName": "Đường Bát Khối",
                "area": 40.0,
                "offeringPrice": 11.5,
                "bedrooms": 5,
                "hasCarParking": True,
                "unified_description": "Căn nhà riêng 6 tầng tuyệt đẹp tại đường Bát Khối"
            }]],
            "distances": [[0.12]]
        }

        response = self.client.post("/api/houses/search", json={
            "query": "Tìm nhà ở khu vực đường Bát Khối",
            "collection_name": "houses",
            "top_k": 3
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["query"], "Tìm nhà ở khu vực đường Bát Khối")
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["id"], "house_118")
        self.assertEqual(data["results"][0]["metadata"]["placeName"], "Nhà riêng Bát Khối")

    @unittest.mock.patch('src.api.main.get_vector_store')
    def test_api_houses_search_price_budget(self, mock_get_vector_store):
        """Test price budget search query via POST /api/houses/search"""
        mock_vector_store = unittest.mock.MagicMock()
        mock_get_vector_store.return_value = mock_vector_store

        mock_vector_store.query.return_value = {
            "ids": [["house_120"]],
            "documents": [["Căn hộ chung cư Northern Diamond 5.2 tỷ"]],
            "metadatas": [[{
                "house_id": 120,
                "placeName": "Chung cư Northern Diamond",
                "streetName": "Đường Cổ Linh",
                "offeringPrice": 5.2,
                "bedrooms": 3,
                "unified_description": "Căn hộ chung cư Northern Diamond 5.2 tỷ"
            }]],
            "distances": [[0.14]]
        }

        response = self.client.post("/api/houses/search", json={
            "query": "Chung cư tầm giá 5 tỷ",
            "top_k": 5
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["metadata"]["offeringPrice"], 5.2)

    # ----------------------------------------------------------------------
    # 2. Test House Ingestion API Endpoint (/api/houses/ingest)
    # ----------------------------------------------------------------------
    @unittest.mock.patch('src.api.main.run_houses_ingest')
    def test_api_houses_ingest_endpoint(self, mock_run_ingest):
        """Test POST /api/houses/ingest triggering the ingestion pipeline"""
        mock_run_ingest.return_value = {
            "status": "success",
            "total_houses": 2,
            "processed_houses": ["118", "120"],
            "errors": []
        }

        response = self.client.post("/api/houses/ingest", json={
            "collection_name": "test_collection",
            "force": False,
            "batch_size": 5
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["processed_houses"]), 2)
        mock_run_ingest.assert_called_once()

    # ----------------------------------------------------------------------
    # 3. Test Full House Ingest Pipeline Function Logic
    # ----------------------------------------------------------------------
    @unittest.mock.patch('src.pipeline.houses.get_gemini_client')
    @unittest.mock.patch('src.pipeline.houses.get_vector_store')
    def test_run_houses_ingest_pipeline(self, mock_get_vector_store, mock_get_gemini_client):
        """Test the run_houses_ingest function end-to-end with mocked Gemini client"""
        mock_vector_store = unittest.mock.MagicMock()
        mock_get_vector_store.return_value = mock_vector_store

        mock_client = unittest.mock.MagicMock()
        mock_get_gemini_client.return_value = mock_client

        # Mock image OCR response
        mock_img_resp = unittest.mock.MagicMock()
        mock_img_resp.text = json.dumps({
            "room_type": "Phòng khách",
            "ocr_text": "Sổ đỏ chính chủ",
            "visual_description": "Không gian rộng thoáng"
        })

        # Mock unified description response
        mock_desc_resp = unittest.mock.MagicMock()
        mock_desc_resp.text = json.dumps({
            "unified_description": "Căn nhà riêng 6 tầng tại đường Bát Khối..."
        })

        mock_client.models.generate_content.side_effect = [
            mock_img_resp,
            mock_desc_resp,
            mock_desc_resp  # Second house has no images, only desc
        ]

        # Temp files
        temp_json = config.DATA_DIR / "temp_houses_test.json"
        with open(temp_json, "w", encoding="utf-8") as f:
            json.dump(self.sample_house_data, f, indent=2)

        temp_img = config.DATA_DIR / "house_118_img1.jpg"
        with open(temp_img, "wb") as f:
            f.write(b"dummy image content")

        try:
            results = run_houses_ingest(
                houses_json_path=str(temp_json),
                images_dir=str(config.DATA_DIR),
                collection_name="test_houses_col",
                force_ocr=True
            )

            self.assertEqual(results["status"], "success")
            self.assertIn("118", results["processed_houses"])
            self.assertIn("120", results["processed_houses"])

            # Verify vector store upserts
            self.assertEqual(mock_vector_store.upsert.call_count, 2)

        finally:
            if temp_json.exists():
                temp_json.unlink()
            if temp_img.exists():
                temp_img.unlink()

    # ----------------------------------------------------------------------
    # 4. Test n8n Real Estate Consultant Workflow JSON Structure
    # ----------------------------------------------------------------------
    def test_n8n_real_estate_workflow_validity(self):
        """Validate n8n real estate workflow JSON file syntax and nodes"""
        workflow_path = config.BASE_DIR / "n8n-docker" / "real_estate_consultant_workflow.json"
        self.assertTrue(workflow_path.exists(), f"Workflow file missing at {workflow_path}")

        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)

        self.assertIn("nodes", workflow)
        self.assertIn("connections", workflow)

        node_names = [n["name"] for n in workflow["nodes"]]
        expected_nodes = ["Webhook", "Search Houses", "Format Context", "Consultant LLM", "Respond to Webhook"]
        for node in expected_nodes:
            self.assertIn(node, node_names, f"Node '{node}' missing from n8n workflow")


if __name__ == "__main__":
    unittest.main()
