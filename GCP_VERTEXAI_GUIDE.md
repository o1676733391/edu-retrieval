# Google Cloud Vertex AI & Gemini Models Setup Guide

This document provides a step-by-step guide for configuring, authenticating, and using Google Cloud Vertex AI and Gemini models using the Service Account key file `data/gcp-key.json`.

---

## 🔑 Key Information & Credentials Summary

The `data/gcp-key.json` file contains Google Cloud IAM Service Account credentials:

- **Project ID:** `gemini-chatbot-436001`
- **Service Account Email:** `vinh-freelancer@gemini-chatbot-436001.iam.gserviceaccount.com`
- **Key Type:** Service Account Private Key (`service_account`)
- **Default Recommended Region:** `us-central1` (or `asia-southeast1`)

> [!WARNING]
> `data/gcp-key.json` contains sensitive private keys. Never commit this file to version control. Ensure it is listed in `.gitignore`.

---

## ⚙️ 1. Environment Configuration

### Step 1: Place Key File
Ensure the service account file is located at:
```text
d:/Project Local/OCR-STEM/data/gcp-key.json
```

### Step 2: Configure `.env` File
Create or update the `.env` file in the project root:

```env
# Enable Vertex AI Authentication
USE_VERTEXAI=true

# Google Cloud Settings
GOOGLE_CLOUD_PROJECT=gemini-chatbot-436001
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=data/gcp-key.json

# (Optional) Direct Gemini API Key fallback
GEMINI_API_KEY=
```

---

## 🐍 2. Python Code Integration Examples

### Example A: Initializing Google GenAI Client (Vertex AI Mode)

```python
import os
from google import genai
from src import config

# 1. Set environment variables
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(config.DATA_DIR / "gcp-key.json")
os.environ["GOOGLE_CLOUD_PROJECT"] = "gemini-chatbot-436001"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

# 2. Instantiate Client in Vertex AI Mode
client = genai.Client(
    vertexai=True,
    project="gemini-chatbot-436001",
    location="us-central1"
)
```

---

### Example B: Text Embedding Generation (`text-embedding-004`)

Generates 768-dimensional vector embeddings for indexing into ChromaDB:

```python
from google import genai

client = genai.Client(
    vertexai=True,
    project="gemini-chatbot-436001",
    location="us-central1"
)

# Single text embedding
response = client.models.embed_content(
    model="text-embedding-004",
    contents="Giải bài tập toán 3 trang 15"
)

embedding_vector = response.embeddings[0].values
print("Embedding dimension:", len(embedding_vector))  # Output: 768
```

---

### Example C: Multimodal Vision OCR (`gemini-2.5-flash`)

Parses scanned PDF images into structured JSON text and page metadata:

```python
from google import genai
from google.genai import types
from PIL import Image

client = genai.Client(
    vertexai=True,
    project="gemini-chatbot-436001",
    location="us-central1"
)

# Load image page
image = Image.open("data-samples/page_15.png")

prompt = """
Bạn là một chuyên gia OCR tài liệu giáo khoa. 
Hãy đọc trang sách này và trích xuất nội dung thành JSON:
{
  "physical_page": int,
  "lesson_name": "string",
  "text": "string"
}
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[image, prompt],
    config=types.GenerateContentConfig(
        response_mime_type="application/json"
    )
)

print(response.text)
```

---

### Example D: RAG Chatbot Reasoning (`gemini-2.5-flash`)

Synthesizes step-by-step mathematical answers with textbook citations:

```python
from google import genai

client = genai.Client(
    vertexai=True,
    project="gemini-chatbot-436001",
    location="us-central1"
)

prompt = """
Bạn là giáo viên tiểu học. Giải thích bài toán sau dựa trên SGK:
Câu hỏi: Giải bài 2 trang 15 tập 1
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)

print(response.text)
```

---

## 🐳 3. Docker & Container Deployment

When running inside Docker containers using `docker-compose.yml`, mount `data/gcp-key.json` as a read-only volume and set environment variables:

```yaml
version: '3.8'

services:
  web_app:
    build: .
    ports:
      - "8080:8080"
      - "8501:8501"
    environment:
      - USE_VERTEXAI=true
      - GOOGLE_CLOUD_PROJECT=gemini-chatbot-436001
      - GOOGLE_CLOUD_LOCATION=us-central1
      - GOOGLE_APPLICATION_CREDENTIALS=/app/data/gcp-key.json
    volumes:
      - ./data/gcp-key.json:/app/data/gcp-key.json:ro
```

---

## 🛠️ 4. Troubleshooting & Security

| Issue / Error | Root Cause | Solution |
| :--- | :--- | :--- |
| **`403 PermissionDenied`** | Vertex AI API not enabled | Enable **Vertex AI API** in [Google Cloud Console](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com) for project `gemini-chatbot-436001`. |
| **`404 NotFound`** | Invalid model or region | Use region `us-central1` and valid model names (`text-embedding-004`, `gemini-2.5-flash`, `gemini-1.5-flash`). |
| **`FileNotFoundError`** | `gcp-key.json` missing | Copy key file to `data/gcp-key.json` or verify `GOOGLE_APPLICATION_CREDENTIALS` path. |
| **`429 Rate Limit`** | Quota limit reached | Ingestion pipeline automatically handles backoff retries. |

---

## 🧪 5. Verification Test Script

Run this verification script to test Vertex AI authentication with `gcp-key.json`:

```bash
python -c "
import os
from google import genai
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'data/gcp-key.json'
client = genai.Client(vertexai=True, project='gemini-chatbot-436001', location='us-central1')
res = client.models.embed_content(model='text-embedding-004', contents='Hello Vertex AI')
print('SUCCESS! Vector dimension:', len(res.embeddings[0].values))
"
```
