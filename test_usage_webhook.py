import json
import requests
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

original_post = requests.post

def mock_post(url, json=None, **kwargs):
    if "webhooks/ai-usage" in url:
        print("\n--- AI Usage Webhook Payload ---")
        print(json)
        print("--------------------------------\n")
        class MockResponse:
            status_code = 200
        return MockResponse()
    return original_post(url, json=json, **kwargs)

requests.post = mock_post

print("Testing /api/create-domain...")
res_domain = client.post("/api/create-domain", json={
    "domain_name": "test_domain_123",
    "user_id": "user_test_001"
})
print("Create Domain Status:", res_domain.status_code)

print("Testing /api/retrieval...")
res_retrieval = client.post("/api/retrieval", json={
    "text": "What is 1 + 1?",
    "tag_name_uuids": ["math"],
    "user_id": "user_test_002"
})
print("Retrieval Status:", res_retrieval.status_code)
