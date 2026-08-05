import unittest
import unittest.mock
import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.pipeline.houses import run_houses_ingest, load_houses_cache, save_houses_cache
from src import config

class TestHousesWorkflow(unittest.TestCase):

    def setUp(self):
        # Setup paths for tests
        self.test_cache_path = config.DATA_DIR / "houses_cache.json"
        # Back up existing cache if any
        self.cache_backup = None
        if self.test_cache_path.exists():
            try:
                with open(self.test_cache_path, "r", encoding="utf-8") as f:
                    self.cache_backup = json.load(f)
                self.test_cache_path.unlink()
            except Exception:
                pass

    def tearDown(self):
        # Restore cache backup
        if self.test_cache_path.exists():
            try:
                self.test_cache_path.unlink()
            except Exception:
                pass
        if self.cache_backup is not None:
            try:
                with open(self.test_cache_path, "w", encoding="utf-8") as f:
                    json.dump(self.cache_backup, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    @unittest.mock.patch('src.pipeline.houses.get_gemini_client')
    @unittest.mock.patch('src.pipeline.houses.get_vector_store')
    def test_houses_ingest_workflow(self, mock_get_vector_store, mock_get_gemini_client):
        # Create a mock vector store
        mock_vector_store = unittest.mock.MagicMock()
        mock_get_vector_store.return_value = mock_vector_store

        # Create mock Gemini client
        mock_client = unittest.mock.MagicMock()
        mock_get_gemini_client.return_value = mock_client

        # Mock image analysis response
        mock_image_resp = unittest.mock.MagicMock()
        mock_image_resp.text = json.dumps({
            "room_type": "Phòng khách",
            "ocr_text": "Sổ đỏ chính chủ",
            "visual_description": "Không gian rộng rãi, lát gạch hoa cao cấp"
        })

        # Mock unified description response
        mock_unified_resp = unittest.mock.MagicMock()
        mock_unified_resp.text = json.dumps({
            "unified_description": "Căn nhà tuyệt đẹp tại Bát Khối, thiết kế hiện đại, diện tích 40 m² x 6 tầng."
        })

        # When client is called, return respective responses
        mock_client.models.generate_content.side_effect = [
            mock_image_resp,  # Image 1 response
            mock_unified_resp  # Unified house description response
        ]

        # Sample houses data to pass
        test_houses_data = [
            {
                "id": 999,
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
                        "fileName": "test_image.jpg",
                        "mediaType": "image"
                    }
                ]
            }
        ]

        # Write sample houses file
        temp_houses_json = config.DATA_DIR / "temp_test_houses.json"
        with open(temp_houses_json, "w", encoding="utf-8") as f:
            json.dump(test_houses_data, f, indent=2)

        # Create a dummy image file so it exists locally
        temp_img_path = config.DATA_DIR / "test_image.jpg"
        with open(temp_img_path, "wb") as f:
            f.write(b"dummy image bytes")

        try:
            # Run ingestion
            results = run_houses_ingest(
                houses_json_path=str(temp_houses_json),
                images_dir=str(config.DATA_DIR),
                collection_name="test_houses",
                force_ocr=True,
                api_key="mock_key"
            )

            # Assertions
            self.assertEqual(results["status"], "success")
            self.assertIn("999", results["processed_houses"])
            self.assertEqual(len(results["errors"]), 0)

            # Verify Gemini client calls
            self.assertEqual(mock_client.models.generate_content.call_count, 2)

            # Verify Vector Store upsert was called with expected payload
            mock_vector_store.upsert.assert_called_once()
            called_args, called_kwargs = mock_vector_store.upsert.call_args
            
            self.assertEqual(called_kwargs["ids"], ["house_999"])
            self.assertIn("THÔNG TIN CHUNG VÀ MÔ TẢ TỔNG QUÁT CĂN NHÀ", called_kwargs["documents"][0])
            self.assertIn("Căn nhà tuyệt đẹp tại Bát Khối", called_kwargs["documents"][0])
            self.assertIn("MÔ TẢ CHI TIẾT TỪNG HÌNH ẢNH THỰC TẾ", called_kwargs["documents"][0])
            
            meta = called_kwargs["metadatas"][0]
            self.assertEqual(meta["house_id"], 999)
            self.assertEqual(meta["placeName"], "Nhà riêng Bát Khối")
            self.assertEqual(meta["streetName"], "Đường Bát Khối")
            self.assertEqual(meta["area"], 40.0)
            self.assertEqual(meta["actualArea"], 45.0)
            self.assertEqual(meta["floors"], 6)
            self.assertEqual(meta["wide"], 5.0)
            self.assertEqual(meta["depth"], 10.0)
            self.assertEqual(meta["offeringPrice"], 11.5)
            self.assertEqual(meta["bedrooms"], 5)
            self.assertEqual(meta["bathrooms"], 1)
            self.assertEqual(meta["hasCarParking"], True)
            self.assertEqual(meta["doc_type"], "house")
            self.assertEqual(meta["unified_description"], "Căn nhà tuyệt đẹp tại Bát Khối, thiết kế hiện đại, diện tích 40 m² x 6 tầng.")

            # Verify cache was written
            cache = load_houses_cache()
            self.assertIn("test_image.jpg", cache["images"])
            self.assertIn("999", cache["houses"])
            self.assertEqual(cache["houses"]["999"]["unified_description"], "Căn nhà tuyệt đẹp tại Bát Khối, thiết kế hiện đại, diện tích 40 m² x 6 tầng.")

        finally:
            # Clean up temp files
            if temp_houses_json.exists():
                temp_houses_json.unlink()
            if temp_img_path.exists():
                temp_img_path.unlink()

    @unittest.mock.patch('src.api.main.get_vector_store')
    def test_api_endpoints(self, mock_get_vector_store):
        from fastapi.testclient import TestClient
        from src.api.main import app

        # Mock vector store
        mock_vector_store = unittest.mock.MagicMock()
        mock_get_vector_store.return_value = mock_vector_store

        # Mock vector store query results
        mock_vector_store.query.return_value = {
            "ids": [["house_120"]],
            "documents": [["Mô tả căn hộ Northern Diamond"]],
            "metadatas": [[{
                "house_id": 120,
                "placeName": "Chung cư Northern Diamond",
                "unified_description": "Mô tả căn hộ Northern Diamond"
            }]],
            "distances": [[0.15]]
        }

        client = TestClient(app)

        # Test Search Endpoint
        response = client.post("/api/houses/search", json={
            "query": "căn hộ cao cấp Northern Diamond",
            "collection_name": "test_collection",
            "top_k": 3
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["query"], "căn hộ cao cấp Northern Diamond")
        self.assertEqual(data["collection_name"], "test_collection")
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["id"], "house_120")
        self.assertEqual(data["results"][0]["distance"], 0.15)
        self.assertEqual(data["results"][0]["unified_description"], "Mô tả căn hộ Northern Diamond")

        # Verify query parameters
        mock_get_vector_store.assert_called_with("houses", collection_name_override="test_collection")
        mock_vector_store.query.assert_called_with(query_text="căn hộ cao cấp Northern Diamond", top_k=3)


if __name__ == "__main__":
    unittest.main()
