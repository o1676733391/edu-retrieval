import unittest
import unittest.mock
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.vector_store.search import extract_hints_from_query, tokenize_vietnamese
from src import config

class TestEducationalAssistant(unittest.TestCase):

    def test_extract_hints_page_only(self):
        query = "bài tập số 2 trang 45"
        page, vol = extract_hints_from_query(query)
        self.assertEqual(page, 45)
        self.assertIsNone(vol)

    def test_extract_hints_volume_only(self):
        query = "các phép tính nhân chia trong tập 2"
        page, vol = extract_hints_from_query(query)
        self.assertIsNone(page)
        self.assertEqual(vol, "2")

    def test_extract_hints_both(self):
        query = "hướng dẫn giải bài 3 trang 120 tập 1"
        page, vol = extract_hints_from_query(query)
        self.assertEqual(page, 120)
        self.assertEqual(vol, "1")

    def test_extract_hints_variations(self):
        queries = [
            ("trang 15 tap 2", 15, "2"),          # ASCII non-accented volume abbr
            ("tr. 98 tập i", 98, "1"),             # tr. prefix + Vietnamese Roman numeral
            ("trang 14 tập hai", 14, "2"),         # Vietnamese word "hai" for vol 2
            ("giải bài tập 2 trang số 10", 10, None), # "trang số X" variation
            ("trang thứ 10", 10, None),             # "trang thứ X" variation
            ("trang một trăm lẻ năm tập 1", None, "1")  # text numbers not matched (expected)
        ]
        for q, expected_page, expected_vol in queries:
            page, vol = extract_hints_from_query(q)
            self.assertEqual(page, expected_page, f"Failed on page: {q}")
            self.assertEqual(vol, expected_vol, f"Failed on volume: {q}")

    def test_tokenization(self):
        text = "Bài 1. Đặt tính rồi tính: 235 + 412"
        tokens = tokenize_vietnamese(text)
        expected = ["bài", "1", "đặt", "tính", "rồi", "tính", "235", "412"]
        self.assertEqual(tokens, expected)

    def test_config_paths(self):
        self.assertTrue(config.DATA_SAMPLES_DIR.exists())
        self.assertTrue(config.DATA_DIR.exists())

    @unittest.mock.patch('src.api.main.run_ingest')
    def test_api_ingest_with_metadata(self, mock_run_ingest):
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        
        # Test basic ingest
        response = client.post("/api/ingest", json={
            "file_path": "data-samples/test.pdf",
            "volume": "1",
            "field": "math",
            "visibility": "public",
            "force": True
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        mock_run_ingest.assert_called_once_with(
            force_ocr=True,
            field="math",
            visibility="public",
            pdf_path="data-samples/test.pdf",
            volume="1",
            description=None,
            file_id=None,
            file_name=None,
            owner_id=None,
            allowed_group=None,
            allowed_user=None,
            mode="keep_cache",
            step_ocr=True,
            step_ingest=True,
            datetime_str=None,
            collection_name_override=None
        )
        
        # Test future metadata and tag_name mapping
        mock_run_ingest.reset_mock()
        response_meta = client.post("/api/ingest", json={
            "file_path": "data-samples/test2.pdf",
            "volume": "2",
            "field": "ignored_because_tag_name_is_present",
            "tag_name": "science",
            "visibility": "teacher_only",
            "description": "Science Grade 3",
            "file_id": "doc_science_3",
            "file_name": "toan-3-science.pdf",
            "owner_id": "user_admin",
            "allowed_group": "teachers_group",
            "allowed_user": "user_vip",
            "mode": "delete_first"
        })
        self.assertEqual(response_meta.status_code, 200)
        mock_run_ingest.assert_called_once_with(
            force_ocr=False,
            field="science",
            visibility="teacher_only",
            pdf_path="data-samples/test2.pdf",
            volume="2",
            description="Science Grade 3",
            file_id="doc_science_3",
            file_name="toan-3-science.pdf",
            owner_id="user_admin",
            allowed_group="teachers_group",
            allowed_user="user_vip",
            mode="delete_first",
            step_ocr=True,
            step_ingest=True,
            datetime_str=None,
            collection_name_override=None
        )

    @unittest.mock.patch('src.api.main.book_knowledge_search')
    def test_api_search(self, mock_search):
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        
        mock_search.return_value = [
            {"id": "test_id", "text": "matched text", "metadata": {"volume": "1", "physical_page": 10, "lesson_name": "Lesson 1"}}
        ]
        
        # Call API
        response = client.post("/api/search", json={
            "query": "bài 1 trang 10",
            "role": "student",
            "field": "math",
            "top_k": 3,
            "page_hint": 10,
            "volume_hint": "1",
            "user_id": "test_user_id",
            "groups": ["teacher", "hr"]
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["query"], "bài 1 trang 10")
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["id"], "test_id")
        
        mock_search.assert_called_once_with(
            query="bài 1 trang 10",
            page_hint=10,
            volume_hint="1",
            top_k=3,
            field="math",
            user_role="student",
            user_id="test_user_id",
            user_groups=["teacher", "hr"]
        )

    @unittest.mock.patch('src.api.main.get_vector_store')
    def test_api_list_documents(self, mock_get_store):
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        mock_store = unittest.mock.MagicMock()
        mock_get_store.return_value = mock_store
        
        # Mock Vector Store get_all return
        mock_store.get_all.return_value = {
            "metadatas": [
                {"file_id": "doc_1", "file_name": "File 1.pdf", "volume": "1", "visibility": "public"},
                {"file_id": "doc_1", "file_name": "File 1.pdf", "volume": "1", "visibility": "public"},
                {"file_id": "doc_2", "file_name": "File 2.pdf", "volume": "2", "visibility": "teacher_only"},
                {"file_id": None, "volume": "1", "visibility": "public"}  # default textbook chunk
            ]
        }
        
        response = client.get("/api/documents?field=math")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["field"], "math")
        self.assertEqual(data["total_documents"], 3)  # doc_1, doc_2, default_textbook
        
        # Check doc_1 count
        doc1 = next(d for d in data["documents"] if d["file_id"] == "doc_1")
        self.assertEqual(doc1["chunk_count"], 2)
        self.assertEqual(doc1["file_name"], "File 1.pdf")
        
        # Check default textbook
        default_doc = next(d for d in data["documents"] if d["file_id"] == "default_textbook")
        self.assertEqual(default_doc["chunk_count"], 1)

    @unittest.mock.patch('src.api.main.get_vector_store')
    def test_api_delete_document(self, mock_get_store):
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        mock_store = unittest.mock.MagicMock()
        mock_get_store.return_value = mock_store
        
        response = client.delete("/api/documents/doc_1?field=math")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        
        mock_store.delete.assert_called_once_with(where={"file_id": "doc_1"})

    @unittest.mock.patch('src.api.main.get_vector_store')
    def test_api_get_document_chunks(self, mock_get_store):
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        mock_store = unittest.mock.MagicMock()
        mock_get_store.return_value = mock_store
        mock_store.get_all.return_value = {
            "ids": ["doc_1_p15", "doc_1_p10"],
            "documents": ["Text page 15", "Text page 10"],
            "metadatas": [
                {"physical_page": 15, "pdf_page_index": 14, "lesson_name": "Lesson 2"},
                {"physical_page": 10, "pdf_page_index": 9, "lesson_name": "Lesson 1"}
            ]
        }
        
        response = client.get("/api/documents/doc_1?field=math")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["file_id"], "doc_1")
        self.assertEqual(data["total_chunks"], 2)
        # Verify chunks are sorted by page index (10 before 15)
        self.assertEqual(data["chunks"][0]["physical_page"], 10)
        self.assertEqual(data["chunks"][1]["physical_page"], 15)

    @unittest.mock.patch('src.vector_store.client.get_vector_store')
    def test_rbac_filtering_and_field_isolation(self, mock_get_store):
        from src.vector_store.search import book_knowledge_search
        
        # Setup mock vector store
        mock_store = unittest.mock.MagicMock()
        mock_get_store.return_value = mock_store
        
        # Mock query and get_all return
        mock_store.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_store.get_all.return_value = {"ids": [], "documents": [], "metadatas": []}
        
        # 1. Test student query for math field
        book_knowledge_search("bài toán", field="math", user_role="student")
        
        # Verify get_vector_store was called with correct field
        mock_get_store.assert_called_with("math")
        
        # Verify query was called with student visibility filter (public)
        args, kwargs = mock_store.query.call_args
        self.assertEqual(kwargs["where"], {"visibility": "public"})
        
        # 2. Test teacher query for science field
        mock_get_store.reset_mock()
        mock_store.query.reset_mock()
        book_knowledge_search("phản ứng hóa học", field="science", user_role="teacher")
        
        # Verify get_vector_store was called with correct field
        mock_get_store.assert_called_with("science")
        
        # Verify query was called with teacher visibility filter (public OR teacher_only)
        args, kwargs = mock_store.query.call_args
        self.assertEqual(kwargs["where"], {"$or": [{"visibility": "public"}, {"visibility": "teacher_only"}]})
        
        # 3. Test admin query
        mock_store.query.reset_mock()
        book_knowledge_search("bất kỳ", user_role="admin")
        args, kwargs = mock_store.query.call_args
        self.assertIsNone(kwargs["where"])

    @unittest.mock.patch('src.vector_store.client.get_vector_store')
    def test_rbac_acl_filtering(self, mock_get_store):
        from src.vector_store.search import book_knowledge_search
        
        # Setup mock vector store
        mock_store = unittest.mock.MagicMock()
        mock_get_store.return_value = mock_store
        
        # Mock query and get_all return
        mock_store.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_store.get_all.return_value = {"ids": [], "documents": [], "metadatas": []}
        
        # Test query as teacher with specific user_id and groups (should form OR filter)
        book_knowledge_search(
            "bài toán", 
            field="math", 
            user_role="teacher", 
            user_id="john_doe", 
            user_groups=["teachers_group", "hr_group"]
        )
        args, kwargs = mock_store.query.call_args
        expected_where = {
            "$or": [
                {"visibility": "public"},
                {"visibility": "teacher_only"},
                {"owner_id": "john_doe"},
                {"allowed_user": "john_doe"},
                {"allowed_group": "teachers_group"},
                {"allowed_group": "hr_group"}
            ]
        }
        self.assertEqual(kwargs["where"], expected_where)

    @unittest.mock.patch('src.api.main.config.VECTOR_DB_BACKEND', 'chromadb')
    @unittest.mock.patch('src.api.main.get_vector_db_client')
    @unittest.mock.patch('src.api.main.get_embedding_function')
    @unittest.mock.patch('src.api.main.get_or_create_collection')
    def test_api_create_domain(self, mock_get_coll, mock_get_emb, mock_get_client):
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        mock_client = unittest.mock.MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_collections.return_value = []
        
        response = client.post("/api/create-domain", json={"domain_name": "STEM_Science"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["domain_name"], "stem_science")
        self.assertIn("stem_science_doc", data["created_collections"])
        self.assertIn("stem_science_qa", data["created_collections"])

    @unittest.mock.patch('src.api.main.run_ingest')
    def test_api_ingestion_payload(self, mock_run_ingest):
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        
        response = client.post("/api/ingestion", json={
            "file_path": "data-samples/test.pdf",
            "tag_name_uuid": "tag_science_999",
            "description": "Science document",
            "datetime": "2026-07-19T14:00:00Z",
            "mode": "override",
            "doc_type": "doc"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["tag_name_uuid"], "tag_science_999")
        
        mock_run_ingest.assert_called_once_with(
            force_ocr=False,
            field="tag_science_999",
            pdf_path="data-samples/test.pdf",
            volume="1",
            description="Science document",
            file_id="tag_science_999",
            file_name="tag_science_999",
            mode="override",
            datetime_str="2026-07-19T14:00:00Z",
            doc_type="doc",
            collection_name_override="tag_science_999_doc",
            step_ocr=True,
            step_ingest=True,
            org_id="org_default"
        )

    @unittest.mock.patch('src.api.main.multi_domain_retrieval')
    def test_api_retrieval(self, mock_retrieval):
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        mock_retrieval.return_value = [
            {"id": "qa_1", "text": "Q: What is STEM? A: Science, Tech, Eng, Math", "metadata": {"created_at": "2026-07-19"}}
        ]
        
        response = client.post("/api/retrieval", json={
            "text": "What is STEM?",
            "tag_name_uuids": ["tag_science_999", "tag_math_111"],
            "type": "qa",
            "from_date": "2026-07-01",
            "to_date": "2026-07-31"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_results"], 1)
        
        mock_retrieval.assert_called_once_with(
            query="What is STEM?",
            tag_name_uuids=["tag_science_999", "tag_math_111"],
            doc_type="qa",
            from_date="2026-07-01",
            to_date="2026-07-31",
            top_k=5,
            org_ids=[]
        )

class TestPromptRegistry(unittest.TestCase):

    def setUp(self):
        from src.prompt_registry.registry import get_db_connection, initialize_prompt_db
        initialize_prompt_db()
        with get_db_connection() as conn:
            conn.execute("DELETE FROM prompt_registry")
            conn.commit()

    def test_database_initialization_and_seeding(self):
        from src.prompt_registry.registry import get_active_prompts, initialize_prompt_db
        initialize_prompt_db()
        prompts = get_active_prompts(profile="default")
        self.assertIn("planner", prompts)
        self.assertIn("default_teacher", prompts)
        self.assertIn("barem_review", prompts)
        self.assertIn("verifier", prompts)
        self.assertTrue(len(prompts["default_teacher"]) > 0)

    def test_create_and_activate_prompt(self):
        from src.prompt_registry.registry import (
            create_prompt_version, 
            activate_prompt_version, 
            get_active_prompts,
            CreatePromptRequest,
            ActivatePromptRequest
        )
        
        # 1. Create a version
        req = CreatePromptRequest(
            agent_name="default_teacher",
            profile="test_profile",
            prompt_text="Custom teacher prompt ver 1",
            is_active=True
        )
        new_prompt = create_prompt_version(req)
        self.assertEqual(new_prompt["version"], 1)
        self.assertEqual(new_prompt["is_active"], 1)
        
        # Verify active prompts for test_profile
        active = get_active_prompts(profile="test_profile")
        self.assertEqual(active["default_teacher"], "Custom teacher prompt ver 1")
        
        # 2. Create another version (inactive)
        req2 = CreatePromptRequest(
            agent_name="default_teacher",
            profile="test_profile",
            prompt_text="Custom teacher prompt ver 2",
            is_active=False
        )
        new_prompt2 = create_prompt_version(req2)
        self.assertEqual(new_prompt2["version"], 2)
        self.assertEqual(new_prompt2["is_active"], 0)
        
        # Active prompt should still be ver 1
        active = get_active_prompts(profile="test_profile")
        self.assertEqual(active["default_teacher"], "Custom teacher prompt ver 1")
        
        # 3. Activate ver 2
        act_req = ActivatePromptRequest(
            agent_name="default_teacher",
            profile="test_profile",
            version=2
        )
        activate_prompt_version(act_req)
        
        # Active prompt should now be ver 2
        active = get_active_prompts(profile="test_profile")
        self.assertEqual(active["default_teacher"], "Custom teacher prompt ver 2")

    def test_api_endpoints(self):
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        
        # Test active prompts endpoint
        response = client.get("/api/prompts/active?profile=default")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("planner", data)
        
        # Test create prompt endpoint
        response = client.post("/api/prompts", json={
            "agent_name": "barem_review",
            "profile": "api_test_profile",
            "prompt_text": "Custom barem review prompt for API test",
            "updated_by": "tester",
            "is_active": True
        })
        self.assertEqual(response.status_code, 200)
        new_prompt = response.json()
        self.assertEqual(new_prompt["profile"], "api_test_profile")
        self.assertEqual(new_prompt["version"], 1)
        
        # Test versions endpoint
        response = client.get("/api/prompts/versions?agent_name=barem_review&profile=api_test_profile")
        self.assertEqual(response.status_code, 200)
        versions = response.json()
        self.assertTrue(len(versions) >= 1)
        self.assertEqual(versions[0]["updated_by"], "tester")
        
        # Test activate endpoint
        response = client.post("/api/prompts/activate", json={
            "agent_name": "barem_review",
            "profile": "api_test_profile",
            "version": 1,
            "updated_by": "tester"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    @unittest.mock.patch('src.vector_store.client.get_vector_store')
    def test_get_document_outline(self, mock_get_store):
        from src.vector_store.search import get_document_outline
        
        # Setup mock vector store
        mock_store = unittest.mock.MagicMock()
        mock_get_store.return_value = mock_store
        
        # Mock get_all to return document chunks with lesson metadata
        mock_store.get_all.return_value = {
            "metadatas": [
                {
                    "file_id": "math3_t1",
                    "file_name": "Toan3_Tap1.pdf",
                    "lesson_name": "Bài 1: Ôn tập các số đến 1000",
                    "physical_page": 5,
                    "pdf_page_index": 4,
                    "volume": "1"
                },
                {
                    "file_id": "math3_t1",
                    "file_name": "Toan3_Tap1.pdf",
                    "lesson_name": "Bài 1: Ôn tập các số đến 1000",
                    "physical_page": 6,
                    "pdf_page_index": 5,
                    "volume": "1"
                },
                {
                    "file_id": "math3_t1",
                    "file_name": "Toan3_Tap1.pdf",
                    "lesson_name": "Bài 2: Cộng trừ trong phạm vi 1000",
                    "physical_page": 10,
                    "pdf_page_index": 9,
                    "volume": "1"
                },
                {
                    "file_id": "science3",
                    "file_name": "Science3.pdf",
                    "lesson_name": "Lesson 1: Plants and Animals",
                    "physical_page": 12,
                    "pdf_page_index": 11,
                    "volume": "1"
                }
            ]
        }
        
        # Test outline grouping and sorting
        outline = get_document_outline()
        self.assertEqual(len(outline), 2)  # Two files: Toan3_Tap1.pdf and Science3.pdf
        
        # Verify Toan3_Tap1.pdf structure
        math_lessons = outline["Toan3_Tap1.pdf"]
        self.assertEqual(len(math_lessons), 2)  # Two unique lessons
        self.assertEqual(math_lessons[0]["lesson_name"], "Bài 1: Ôn tập các số đến 1000")
        self.assertEqual(math_lessons[0]["physical_page"], 5)  # First occurrence page
        self.assertEqual(math_lessons[1]["lesson_name"], "Bài 2: Cộng trừ trong phạm vi 1000")
        self.assertEqual(math_lessons[1]["physical_page"], 10)
        
        # Verify Science3.pdf structure
        science_lessons = outline["Science3.pdf"]
        self.assertEqual(len(science_lessons), 1)
        self.assertEqual(science_lessons[0]["lesson_name"], "Lesson 1: Plants and Animals")

    @unittest.mock.patch('src.vector_store.client.get_vector_store')
    def test_get_document_outline_new_metadata(self, mock_get_store):
        from src.vector_store.search import get_document_outline
        
        mock_store = unittest.mock.MagicMock()
        mock_get_store.return_value = mock_store
        
        # Mock get_all to return document chunks with new metadata structure
        mock_store.get_all.return_value = {
            "metadatas": [
                {
                    "volume": "1",
                    "physical_page": 22,
                    "pdf_page_index": 16,
                    "pdf_page_number": 17,
                    "lesson_name": "LUYỆN TẬP CHUNG",
                    "visibility": "public",
                    "doc_type": "doc",
                    "tag_name_uuid": "4d0e34cc-a2e8-44ba-945b-c95d73cd86c1_1785060684",
                    "file_id": "4d0e34cc-a2e8-44ba-945b-c95d73cd86c1_1785060684",
                    "_original_id": "4d0e34cc-a2e8-44ba-945b-c95d73cd86c1_1785060684_p22_idx16",
                    "org_id": "org_default",
                    "file_name": "SGK_TOAN_4_T1_s1_2.pdf",
                    "file_path": "data/uploads/SGK_TOAN_4_T1_s1_2.pdf"
                }
            ]
        }
        
        outline = get_document_outline(tag_name_uuids=["4d0e34cc-a2e8-44ba-945b-c95d73cd86c1_1785060684"])
        self.assertIn("SGK_TOAN_4_T1_s1_2.pdf", outline)
        lessons = outline["SGK_TOAN_4_T1_s1_2.pdf"]
        self.assertEqual(len(lessons), 1)
        self.assertEqual(lessons[0]["lesson_name"], "LUYỆN TẬP CHUNG")
        self.assertEqual(lessons[0]["physical_page"], 22)
        self.assertEqual(lessons[0]["pdf_page_number"], 17)
        self.assertEqual(lessons[0]["tag_name_uuid"], "4d0e34cc-a2e8-44ba-945b-c95d73cd86c1_1785060684")

    @unittest.mock.patch('src.vector_store.search.get_document_outline')
    def test_outline_api_endpoints(self, mock_outline):
        from fastapi.testclient import TestClient
        from src.api.main import app
        api_client = TestClient(app)

        mock_outline.return_value = {
            "SGK_TOAN_4_T1_s1_2.pdf": [
                {
                    "lesson_name": "LUYỆN TẬP CHUNG",
                    "physical_page": 22,
                    "pdf_page_number": 17,
                    "volume": "1"
                }
            ]
        }
        
        # Test GET /api/outline
        res_get = api_client.get("/api/outline")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["status"], "success")
        self.assertIn("SGK_TOAN_4_T1_s1_2.pdf", res_get.json()["outline"])
        
        # Test POST /api/outline
        res_post = api_client.post("/api/outline", json={
            "tag_name_uuids": ["4d0e34cc-a2e8-44ba-945b-c95d73cd86c1_1785060684"],
            "doc_type": "doc"
        })
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(res_post.json()["status"], "success")
        self.assertIn("SGK_TOAN_4_T1_s1_2.pdf", res_post.json()["outline"])



if __name__ == "__main__":
    unittest.main()



