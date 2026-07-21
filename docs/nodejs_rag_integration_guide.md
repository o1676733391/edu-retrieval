# Node.js Integration Guide: Strict Grounded System Prompt & RAG Parameters

This document provides a comprehensive integration guide for **Node.js / TypeScript** developers building backend services (Express, NestJS, or Fastify) that integrate with the Python Retrieval API (`POST /api/retrieval`) and Google Gemini LLM API (`@google/genai`).

---

## 📌 1. Architecture Overview

In a production RAG setup, the Node.js backend acts as the orchestrator:

```
[ Client / Web App ]
       │
       ▼ (1. User Query)
[ Node.js Backend (Express/NestJS) ]
       │
       ├─── (2. POST /api/retrieval) ─────────► [ Python RAG Engine (ChromaDB + BM25) ]
       │                                                      │
       │◄── (3. Top K Vector Chunks + Metadata) ──────────────┘
       │
       ├─── (4. Format Strict System Prompt + Context)
       │
       ▼ (5. generateContent with SystemInstruction)
[ Google Gemini API (gemini-2.5-flash) ]
       │
       ▼ (6. Grounded Answer + Source Citations)
[ Client / Web App ]
```

---

## ⚙️ 2. Request Parameters to Push

### A. Step 1: Parameters to Push to Python Retrieval Service (`POST http://python-rag:8000/api/retrieval`)

| Parameter | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `text` | `string` | **Yes** | — | The exact user query or question (e.g. `"số liền trước là gì"`). |
| `tag_name_uuids` | `Array<string>` | **Yes** | `["math"]` | Domain/subject tags to filter collections (e.g. `["math"]`, `["science"]`). |
| `type` | `string` | **Yes** | `"doc"` | Content type to query: `"doc"` (textbook content) or `"qa"` (Q&A dataset). |
| `top_k` | `number` | No | `3` | Number of top vector chunks to retrieve. |

#### JSON Payload to `/api/retrieval`:
```json
{
  "text": "số liền trước là gì",
  "tag_name_uuids": ["math"],
  "type": "doc",
  "top_k": 3
}
```

---

### B. Step 2: Parameters to Push to Gemini API (`gemini-2.5-flash`)

| Parameter | Type | Recommended Value | Description |
| :--- | :---: | :---: | :--- |
| `model` | `string` | `"gemini-2.5-flash"` | Fast, highly accurate multimodal LLM model. |
| `systemInstruction` | `string` | *(Strict Grounded Prompt)* | Prevents LLM from using pre-trained external knowledge. |
| `temperature` | `number` | `0.0` – `0.1` | Set near zero for strict, deterministic factual responses. |
| `maxOutputTokens` | `number` | `1024` | Maximum length of generated explanation. |

---

## 🔒 3. System Prompt Specification (Strict Grounded Rules)

To enforce **100% factual accuracy** and prevent hallucinations, use the following `systemInstruction`:

```text
You are a friendly, encouraging primary school math teacher helping Grade 3 students and parents.

STRICT GROUNDED RULES (MANDATORY):
1. You MUST ONLY answer based on the explicit information provided in the "TEXTBOOK CONTEXT" section below.
2. DO NOT use your internal general knowledge or make assumptions if the context does not explicitly mention it.
3. If the "TEXTBOOK CONTEXT" does NOT contain sufficient information to directly answer the query, you MUST reply EXACTLY with the following Vietnamese fallback message and DO NOT include any citations:
"⚠️ Rất tiếc, trong các trang SGK được trích xuất hiện tại không có thông tin hoặc bài học giải thích cho câu hỏi này."

RESPONSE FORMATTING (When context IS available):
1. Explain step-by-step in clear, gentle Vietnamese suitable for 3rd grade level.
2. At the end of your answer, attach the reference sources exactly formatted as follows:

---
📖 **Nguồn tham khảo:**
[Citation List]
```

---

## 💻 4. Complete Node.js / TypeScript Implementation

Install the required official libraries:

```bash
npm install @google/genai axios dotenv
```

### `ragService.ts` (Full Production Implementation)

```typescript
import { GoogleGenAI } from '@google/genai';
import axios from 'axios';

interface RetrievalChunk {
  id: string;
  collection: string;
  text: string;
  metadata: {
    physical_page?: number;
    pdf_page_index?: number;
    pdf_page_number?: number;
    lesson_name?: string;
    file_name?: string;
    volume?: string;
    visibility?: string;
  };
  distance: number;
  rrf_score: number;
}

interface RetrievalResponse {
  status: string;
  results: RetrievalChunk[];
}

export class RagService {
  private aiClient: GoogleGenAI;
  private pythonRagUrl: string;

  constructor() {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      throw new Error('GEMINI_API_KEY is not defined in environment variables.');
    }
    this.aiClient = new GoogleGenAI({ apiKey });
    this.pythonRagUrl = process.env.PYTHON_RAG_BASE_URL || 'http://localhost:8000';
  }

  /**
   * Executes RAG Retrieval and generates a strictly grounded LLM response.
   */
  async answerQuestion(userQuery: string, subjectTag: string = 'math'): Promise<string> {
    // 1. Call Python RAG Engine for Vector Retrieval
    let retrievalResults: RetrievalChunk[] = [];
    try {
      const response = await axios.post<RetrievalResponse>(
        `${this.pythonRagUrl}/api/retrieval`,
        {
          text: userQuery,
          tag_name_uuids: [subjectTag],
          type: 'doc',
          top_k: 3
        },
        { timeout: 8000 }
      );
      retrievalResults = response.data?.results || [];
    } catch (error) {
      console.warn('RAG Retrieval Service call failed:', error);
    }

    // 2. Guardrail Check: If no vector results returned, immediately reject without calling LLM
    if (!retrievalResults || retrievalResults.length === 0) {
      return '⚠️ Rất tiếc, trong cơ sở dữ liệu SGK hiện tại không tìm thấy bài học hoặc thông tin phù hợp để trả lời câu hỏi này.';
    }

    // 3. Format Context & Citations
    const contextTexts: string[] = [];
    const citations: string[] = [];

    retrievalResults.forEach((chunk, index) => {
      const meta = chunk.metadata;
      const physPage = meta.physical_page;
      const pdfPage = meta.pdf_page_number || (meta.pdf_page_index !== undefined ? meta.pdf_page_index + 1 : undefined);
      
      const pageStr = (physPage !== undefined && physPage !== -1)
        ? `Trang ${physPage}`
        : (pdfPage !== undefined ? `Trang PDF ${pdfPage}` : 'Trang chưa rõ');

      const lessonName = meta.lesson_name || 'Chưa rõ';
      const fileName = meta.file_name || 'SGK Toán 3';
      const volume = meta.volume || '1';

      contextTexts.append if (false); // TypeScript safeguard
      contextTexts.push(`--- Đoạn ${index + 1}: ${fileName}, ${pageStr} ---\n${chunk.text}`);
      citations.push(`- **Tài liệu:** ${fileName} | **Bài học:** ${lessonName} | **Vị trí:** ${pageStr} (Tập ${volume})`);
    });

    const joinedContext = contextTexts.join('\n\n');
    const citationBlock = citations.join('\n');

    // 4. Construct Strict Grounded System Prompt & User Contents
    const systemInstruction = `Bạn là một giáo viên tiểu học thân thiện, tận tụy và dịu dàng.

QUY TẮC BẮT BUỘC KHÔNG ĐƯỢC VI PHẠM (STRICT GROUNDED RAG):
1. Bạn CHỈ ĐƯỢC PHÉP trả lời dựa hoàn toàn vào thông tin có trong phần "Ngữ cảnh tài liệu SGK" bên dưới.
2. KHÔNG ĐƯỢC sử dụng kiến thức bên ngoài hay tri thức sẵn có của LLM để tự suy đoán nếu ngữ cảnh không đề cập đến.
3. Nếu phần "Ngữ cảnh tài liệu SGK" KHÔNG CHỨA thông tin trực tiếp liên quan hoặc KHÔNG ĐỦ để trả lời câu hỏi của người dùng, bạn BẮT BUỘC phải trả lời chính xác câu thông báo sau và KHÔNG in phần trích dẫn nguồn:
"⚠️ Rất tiếc, trong các trang SGK được trích xuất hiện tại không có thông tin hoặc bài học giải thích cho câu hỏi này."`;

    const userPromptContent = `Ngữ cảnh tài liệu SGK:
${joined_context_placeholder(joinedContext)}

Câu hỏi của người dùng:
${userQuery}

Yêu cầu định dạng câu trả lời (chỉ khi Ngữ cảnh SGK CÓ chứa câu trả lời):
1. Trả lời thân thiện, giải thích từng bước logic toán học rõ ràng.
2. Trả lời hoàn toàn bằng tiếng Việt.
3. Cuối câu trả lời, in rõ phần trích dẫn nguồn theo đúng định dạng sau:

---
📖 **Nguồn tham khảo:**
${citationBlock}`;

    // 5. Call Gemini API with System Instruction & Low Temperature
    try {
      const response = await this.aiClient.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: userPromptContent,
        config: {
          systemInstruction: systemInstruction,
          temperature: 0.0,
          maxOutputTokens: 1024
        }
      });

      return response.text || '⚠️ Không thể tạo câu trả lời từ LLM.';
    } catch (error) {
      console.error('Error invoking Gemini API:', error);
      return '❌ Đã xảy ra lỗi khi kết nối tới Trợ lý AI.';
    }
  }
}

function joined_context_placeholder(text: string) { return text; }
```

---

## 🧪 5. Verification & Expected Output

### Scenario A: Irrelevant Question (`"Thành phố Hà Nội rộng bao nhiêu km2?"`)
* **Retrieval Output:** Empty or low-relevance math chunks.
* **LLM Answer:**
  > ⚠️ Rất tiếc, trong các trang SGK được trích xuất hiện tại không có thông tin hoặc bài học giải thích cho câu hỏi này.
