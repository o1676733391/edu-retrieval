# Conversational Query Condensation Guide

This guide documents the technical design, system prompt, input/output structures, and code implementations for the **Session History Condenser** module.

In a Conversational RAG (Retrieval-Augmented Generation) system, users frequently ask follow-up questions containing coreferences or elliptical phrases (e.g., *"Giải thích giúp mình phần đó với"*, *"Trang này có câu hỏi ôn tập nào không?"*, *"Ví dụ khác"*). The Condenser module rewrites the chat history and the latest user prompt into a single, self-contained standalone search query that can be queried against the vector database.

---

## 1. Architectural Flow

The following diagram illustrates how the Session History Condenser sits between the user chat interface and the primary vector retrieval pipeline:

```mermaid
graph TD
    A[User Chat Input] --> B(Session History Condenser Module)
    C[(Session Chat History)] --> B
    B -->|Calls LLM with Condensation Prompt| D{Does it need search?}
    D -->|Yes| E[Standalone Search Query]
    D -->|No| F[Bypass Search & Return Response Directly]
    E --> G[Vector Store Hybrid Search / BM25]
    G --> H[Retrieve Context / Page Metadata]
    H --> I[Primary Teacher Agent]
    I --> J[Vietnamese Chatbot Response]
```

---

## 2. System Instructions & Prompt

The model must be instructed to act as a linguistic analyzer. Its sole responsibility is to extract context and construct a clear, standalone search query in **Vietnamese**.

### System Prompt (Vietnamese)
```markdown
Bạn là một trợ lý phân tích ngôn ngữ chuyên nghiệp cho hệ thống Giáo dục RAG.
Nhiệm vụ của bạn là nhận vào:
1. Lịch sử cuộc trò chuyện giữa Người dùng (User) và Trợ lý (Assistant).
2. Câu hỏi mới nhất của Người dùng (Latest Message).

Hãy phân tích và viết lại Câu hỏi mới nhất thành một câu truy vấn độc lập, rõ ràng bằng tiếng Việt (Standalone Query) dùng để tìm kiếm tài liệu học tập trong sách giáo khoa.

### QUY TẮC PHÂN TÍCH:
1. **Giải quyết đại từ chỉ trỏ (Coreference Resolution):** Tìm các từ thay thế như "phần đó", "bài này", "nó", "trang trên", "phần trước" trong câu hỏi mới nhất và thay thế chúng bằng thông tin thực tế từ lịch sử cuộc trò chuyện (ví dụ: "câu hỏi thảo luận 3", "trang 24", "tập 1").
2. **Bảo toàn ngữ cảnh địa lý sách (Location context):** Nếu lịch sử có đề cập đến một trang cụ thể (ví dụ: Trang 15) hoặc tập cụ thể (Tập 1 hoặc Tập 2), hãy gộp thông tin trang và tập này vào câu truy vấn độc lập để lọc chính xác.
3. **Phân loại nhu cầu tìm kiếm (Search Intent Classify):**
   - Đặt `needs_search = true` nếu câu hỏi hỏi về bài tập, định nghĩa, kiến thức học tập, thí nghiệm, hoặc yêu cầu giải thích nội dung trong sách giáo khoa.
   - Đặt `needs_search = false` nếu câu hỏi chỉ là chào hỏi xã giao (ví dụ: "Chào bạn", "Tạm biệt"), câu hỏi ngoài lề không liên quan bài học, hoặc lời cảm ơn đơn thuần (ví dụ: "Cảm ơn bạn").
4. **Không trả lời câu hỏi:** Tuyệt đối KHÔNG trả lời câu hỏi của người dùng. Bạn chỉ đang viết lại câu truy vấn tìm kiếm.
5. **Đầu ra bắt buộc:** Trả về định dạng JSON đúng cấu trúc được mô tả bên dưới.
```

---

## 3. Request & Response Specification

### Input Parameters
* `latest_message` (String, Required): The raw new input text sent by the user.
* `chat_history` (Array of Message Objects, Optional): The list of prior messages in the current session.
  * `role` (String): Either `"user"` or `"model"`.
  * `content` (String): The text content of the message.

### Output JSON Schema
The output from the module must strictly follow this JSON format:
```json
{
  "type": "object",
  "properties": {
    "standalone_query": {
      "type": "string",
      "description": "The rewritten, self-contained query in Vietnamese containing all resolved page/volume contexts."
    },
    "needs_search": {
      "type": "boolean",
      "description": "True if the query requires database search/retrieval; False if it is a greeting, farewell, or off-topic conversational text."
    },
    "context_summary": {
      "type": "string",
      "description": "A short summary of current session anchors, e.g., 'Trang 24, Tập 1'."
    }
  },
  "required": ["standalone_query", "needs_search", "context_summary"]
}
```

---

## 4. Execution Examples

### Example 1: Resolving Pronouns and Page References
* **Chat History:**
  ```json
  [
    { "role": "user", "content": "Tìm cho mình nội dung về quang hợp ở trang 45 tập 2" },
    { "role": "model", "content": "Dưới đây là nội dung Câu hỏi thảo luận 2 và Câu hỏi 3 trang 45 sách giáo khoa Khoa học Tự nhiên Tập 2..." }
  ]
  ```
* **Latest Message:** `"Giải thích cho mình câu số 2 đi"`
* **Expected Output JSON:**
  ```json
  {
    "standalone_query": "Giải thích chi tiết câu hỏi thảo luận số 2 về quang hợp trang 45 sách giáo khoa tập 2",
    "needs_search": true,
    "context_summary": "Trang 45, Tập 2, Quang hợp"
  }
  ```

### Example 2: Greeting & Off-topic (No Search Needed)
* **Chat History:** `[]`
* **Latest Message:** `"Chào bạn, bạn có khỏe không?"`
* **Expected Output JSON:**
  ```json
  {
    "standalone_query": "Chào bạn, bạn có khỏe không?",
    "needs_search": false,
    "context_summary": "Greeting"
  }
  ```

### Example 3: Context Retention across Multiple Turns
* **Chat History:**
  ```json
  [
    { "role": "user", "content": "Sách Khoa học tập 1 có bài nào về các trạng thái của chất không?" },
    { "role": "model", "content": "Có bài 'Các trạng thái của chất' ở trang 64 Tập 1..." },
    { "role": "user", "content": "Cho mình xem các câu hỏi thảo luận ở trang đó" },
    { "role": "model", "content": "Các câu hỏi thảo luận trang 64 bao gồm..." }
  ]
  ```
* **Latest Message:** `"Giải câu 1 phần b"`
* **Expected Output JSON:**
  ```json
  {
    "standalone_query": "Giải câu hỏi thảo luận 1 phần b trang 64 sách giáo khoa khoa học tự nhiên tập 1 về các trạng thái của chất",
    "needs_search": true,
    "context_summary": "Trang 64, Tập 1, Trạng thái của chất"
  }
  ```

---

## 5. Developer Implementation

Here are reference implementations for python and Node.js using the official Google GenAI SDK configured for **Vertex AI**.

### Node.js Implementation (`gemini-2.5-flash`)

Ensure you have `@google/genai` installed:
```bash
npm install @google/genai
```

```javascript
import { GoogleGenAI, Type } from '@google/genai';

// Initialize the client configured for Vertex AI
const ai = new GoogleGenAI({
  vertex: true,
  project: process.env.GOOGLE_CLOUD_PROJECT,
  location: process.env.GOOGLE_CLOUD_LOCATION
});

async function condenseSessionHistory(latestMessage, chatHistory = []) {
  const systemInstruction = `
Bạn là một trợ lý phân tích ngôn ngữ chuyên nghiệp cho hệ thống Giáo dục RAG.
Nhiệm vụ của bạn là nhận vào lịch sử cuộc trò chuyện và câu hỏi mới nhất của người dùng.
Hãy viết lại câu hỏi đó thành một câu truy vấn tìm kiếm tiếng Việt độc lập (Standalone Query) chứa đầy đủ ngữ cảnh trang sách, chương, tập được nhắc tới trong lịch sử.

Tuyệt đối không tự trả lời câu hỏi của người dùng.
  `.trim();

  // Format the history & latest message as user prompt
  const formattedPrompt = `
LỊCH SỬ CHAT:
${chatHistory.map(msg => `- ${msg.role === 'user' ? 'Người dùng' : 'Trợ lý'}: ${msg.content}`).join('\n')}

CÂU HỎI MỚI NHẤT:
${latestMessage}
  `.trim();

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: formattedPrompt,
      config: {
        systemInstruction: systemInstruction,
        temperature: 0.1,
        // Enforce Structured JSON Output
        responseMimeType: 'application/json',
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            standalone_query: { 
              type: Type.STRING, 
              description: 'Câu truy vấn tiếng Việt độc lập chứa đầy đủ ngữ cảnh đã giải quyết.' 
            },
            needs_search: { 
              type: Type.BOOLEAN, 
              description: 'True nếu câu hỏi cần truy vấn DB; False nếu là lời chào xã giao.' 
            },
            context_summary: { 
              type: Type.STRING, 
              description: 'Tóm tắt ngắn gọn ngữ cảnh trang/tập hiện tại.' 
            }
          },
          required: ['standalone_query', 'needs_search', 'context_summary']
        }
      }
    });

    const result = JSON.parse(response.text);
    return result;
  } catch (error) {
    console.error('Error during history condensation:', error);
    // Fallback safely to original message
    return {
      standalone_query: latestMessage,
      needs_search: true,
      context_summary: 'Fallback'
    };
  }
}
```

### Python Implementation (`gemini-2.5-flash`)

Ensure you have `google-genai` installed:
```bash
pip install google-genai pydantic
```

```python
import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

class CondensationOutput(BaseModel):
    standalone_query: str = Field(description="Câu truy vấn tiếng Việt độc lập chứa ngữ cảnh đã giải quyết.")
    needs_search: bool = Field(description="True nếu cần tra cứu sách khoa; False nếu là xã giao/chào hỏi.")
    context_summary: str = Field(description="Tóm tắt ngắn gọn ngữ cảnh trang/tập sách hiện tại.")

def condense_session_history(latest_message: str, chat_history: list = []) -> CondensationOutput:
    # Initialize the client configured for Vertex AI
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION")
    )
    
    system_instruction = (
        "Bạn là một trợ lý phân tích ngôn ngữ cho hệ thống Giáo dục RAG.\n"
        "Nhận vào lịch sử chat và câu hỏi mới nhất, viết lại câu hỏi thành một câu truy vấn tìm kiếm tiếng Việt "
        "độc lập chứa đầy đủ ngữ cảnh địa lý trang sách từ lịch sử. Không trả lời câu hỏi."
    )
    
    # Format conversational context
    history_lines = []
    for msg in chat_history:
        role = "Người dùng" if msg.get("role") == "user" else "Trợ lý"
        history_lines.append(f"- {role}: {msg.get('content')}")
        
    formatted_prompt = f"LỊCH SỬ CHAT:\n" + "\n".join(history_lines) + f"\n\nCÂU HỎI MỚI NHẤT:\n{latest_message}"
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=formatted_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=CondensationOutput
            )
        )
        return CondensationOutput.model_validate_json(response.text)
    except Exception as e:
        print(f"Error during condensation: {e}")
        return CondensationOutput(
            standalone_query=latest_message,
            needs_search=True,
            context_summary="Fallback"
        )
```

---

## 6. Advanced Architecture: Three-Role Message Compression

### Database Design
#### Table 2: `active_session_chat` (Active Context-Aware History)
Stores the active conversational window. It shares the same table structure as Table 1 but supports a third role: `"compact"`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID (PK) | Unique message identifier. |
| `session_id` | String (Index) | Identifies the unique chat session. |
| `role` | String | `'user'`, `'assistant'`, or `'compact'`. |
| `content` | String | The message text (raw input or compacted summary). |
| `created_at` | Timestamp | Sequence order of active chat. |

---

### Step-by-Step Compaction Workflow

For a configured threshold of $n$ message pairs (e.g., $n = 10$, meaning 20 messages):

```mermaid
sequenceDiagram
    autonumber
    User->>Backend: Send message 21 (Pair 11)
    Backend->>Database: Query Table 2 count for session
    Database-->>Backend: Returns count = 20 (Threshold reached: 2n messages!)
    Note over Backend: Trigger Compaction Step
    Backend->>LLM: Call GenerateContent (Send all 20 messages currently in Table 2)
    LLM-->>Backend: Returns a single consolidated summary text
    Backend->>Database: DELETE all 20 messages from Table 2 for session
    Backend->>Database: INSERT 1 new message in Table 2 (role: 'compact', content: 'Tóm tắt hội thoại trước đó: ...')
    Backend->>Database: INSERT User Message 21 into Table 2 (role: 'user')
    Backend->>Backend: Query RAG using Standalone Query generated from (Compact + Message 21)
    Backend->>User: Generate and return assistant response (Save response to Table 2 role: 'assistant')
```

---

### Compactor Prompt (Three-Role Context)

When compaction is triggered, send the message list from Table 2 to the LLM with this instruction:

```markdown
Bạn là một trợ lý tóm tắt và quản lý ngữ cảnh trò chuyện chuyên nghiệp cho hệ thống Giáo dục RAG.
Nhiệm vụ của bạn là đọc toàn bộ lịch sử trò chuyện được gửi kèm (có thể chứa tin nhắn 'compact' trước đó ở đầu và các cặp tin nhắn 'user'/'assistant' mới tiếp nối).

Hãy tổng hợp và tạo ra một bản tóm tắt mới ngắn gọn nhất dưới dạng danh sách gạch đầu dòng ghi nhận:
- Các chủ đề và khái niệm chính sách giáo khoa đang thảo luận trong phiên.
- Các vị trí tài liệu đã được xác lập (trang sách nào, tập sách nào).
- Các câu hỏi chưa được giải quyết hoặc trọng tâm người dùng đang hỏi tiếp theo.

Đầu ra của bạn phải là một câu tóm tắt bằng tiếng Việt rõ ràng, chuẩn ngữ pháp để chèn lại vào tin nhắn với vai trò 'compact'. Không trả lời câu hỏi của người dùng.
```

---

### Compactor Concrete Example

#### 1. Table 2 State before Compaction (At $n = 4$ pairs / 8 messages)
Table 2 contains the following message list:
```json
[
  { "role": "user", "content": "Tìm giúp em bài học về các trạng thái của chất ở tập 1" },
  { "role": "assistant", "content": "Bài 'Các trạng thái của chất' nằm ở trang 64 sách Khoa học Tự nhiên Tập 1 em nhé." },
  { "role": "user", "content": "Trang đó có câu hỏi thảo luận số 1 là gì ạ?" },
  { "role": "assistant", "content": "Câu hỏi 1 trang 64 yêu cầu em mô tả đặc điểm hình dạng và thể tích của nước đá, nước lỏng và hơi nước." },
  { "role": "user", "content": "Giải giúp em phần nước đá trước" },
  { "role": "assistant", "content": "Nước đá ở trạng thái rắn, có hình dạng cố định và thể tích xác định." },
  { "role": "user", "content": "Thế còn hơi nước?" },
  { "role": "assistant", "content": "Hơi nước ở trạng thái khí, không có hình dạng cố định và không có thể tích xác định (nó chiếm toàn bộ thể tích bình chứa)." }
]
```

#### 2. Compacted Output & Table 2 Cleanup
The backend calls the Compactor API with the list above. The LLM returns a single string:
> *"Tóm tắt hội thoại trước đó: Học sinh đang tìm hiểu bài 'Các trạng thái của chất' trang 64 tập 1. Đã giải đáp câu hỏi thảo luận 1 về nước đá (trạng thái rắn, có hình dạng/thể tích cố định) và hơi nước (trạng thái khí, không hình dạng/thể tích cố định)."*

The backend executes a transaction:
1. `DELETE FROM active_session_chat WHERE session_id = 'session_123'` (Clears all 8 messages).
2. `INSERT INTO active_session_chat` with the single compacted message:
   ```json
   {
     "session_id": "session_123",
     "role": "compact",
     "content": "Tóm tắt hội thoại trước đó: Học sinh đang tìm hiểu bài 'Các trạng thái của chất' trang 64 tập 1. Đã giải đáp câu hỏi thảo luận 1 về nước đá (trạng thái rắn, có hình dạng/thể tích cố định) và hơi nước (trạng thái khí, không hình dạng/thể tích cố định)."
   }
   ```

#### 3. Subsequent Turn Processing (Turn 9 / Next User Prompt)
* **User inputs:** `"Thế còn nước lỏng?"`
* **Table 2 state before calling the Query Condenser:**
  ```json
  [
    {
      "role": "compact",
      "content": "Tóm tắt hội thoại trước đó: Học sinh đang tìm hiểu bài 'Các trạng thái của chất' trang 64 tập 1. Đã giải đáp câu hỏi thảo luận 1 về nước đá (trạng thái rắn, có hình dạng/thể tích cố định) và hơi nước (trạng thái khí, không hình dạng/thể tích cố định)."
    },
    {
      "role": "user",
      "content": "Thế còn nước lỏng?"
    }
  ]
  ```
* **Condenser Standalone Query Output:**
  `"Đặc điểm hình dạng và thể tích của nước lỏng ở trang 64 sách giáo khoa khoa học tự nhiên tập 1"` (passed directly to ChromaDB RAG search).

---

### Ingestion & Query Condensation Benefits

By keeping Table 2 structured as a message log with a `"compact"` prefix role, we achieve:
* **80%+ API Cost Reduction:** Keeps the active token window extremely small.
* **Low Latency:** Fast prompt evaluation due to minimal conversational history sizes.
* **No Custom DB Schema:** Leverages standard message storage schemas with a simple role-enum extension.
* **Easy API Integration:** Easily mapped to standard chat completion message formats (e.g. mapping `"compact"` to a system prompt or a prefixed user/assistant message).

---

## 7. PostgreSQL & Node.js Database Implementation

This section provides production-ready database schemas for PostgreSQL and execution scripts for Node.js (using the standard `pg` pool driver) to manage this sliding window memory and compaction workflow.

### 1. PostgreSQL Schema (DDL)

Run these DDL scripts to initialize the tables in your PostgreSQL database:

```sql
-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table 1: Raw Conversation Audit Trail
CREATE TABLE raw_chat_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast session history lookback lookup
CREATE INDEX idx_raw_chat_session ON raw_chat_history(session_id);
CREATE INDEX idx_raw_chat_created ON raw_chat_history(created_at);


-- Table 2: Active Chat Memory Window (with Compaction support)
CREATE TABLE active_session_chat (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant', 'compact')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for session active window retrieval
CREATE INDEX idx_active_chat_session ON active_session_chat(session_id);
CREATE INDEX idx_active_chat_created ON active_session_chat(created_at ASC);
```

---

### 2. Node.js Database Client Code

Below is the JavaScript logic using the `pg` client pool to write to both tables, verify threshold counts, invoke compaction via the Gemini API, and perform the table swap transaction.

```javascript
import pg from 'pg';
import { GoogleGenAI } from '@google/genai';

const { Pool } = pg;
const dbPool = new Pool({
  connectionString: process.env.DATABASE_URL // e.g., postgresql://user:pass@localhost:5432/dbname
});

const ai = new GoogleGenAI({
  vertex: true,
  project: process.env.GOOGLE_CLOUD_PROJECT,
  location: process.env.GOOGLE_CLOUD_LOCATION
});

/**
 * Inserts a new user or assistant message and triggers history compaction if the threshold is met.
 * @param {string} sessionId The active session UUID
 * @param {'user' | 'assistant'} role The message sender role
 * @param {string} content The message text
 * @param {number} nThreshold The message pair threshold (e.g. 10 pairs = 20 messages)
 */
export async function addChatMessageAndHandleCompaction(sessionId, role, content, nThreshold = 10) {
  const messageLimit = nThreshold * 2; // Convert pairs to message count
  const client = await dbPool.connect();

  try {
    // Start Transaction
    await client.query('BEGIN');

    // 1. Insert message into Table 1 (Full History)
    const insertRawQuery = `
      INSERT INTO raw_chat_history (session_id, role, content)
      VALUES ($1, $2, $3);
    `;
    await client.query(insertRawQuery, [sessionId, role, content]);

    // 2. Insert message into Table 2 (Active Memory)
    const insertActiveQuery = `
      INSERT INTO active_session_chat (session_id, role, content)
      VALUES ($1, $2, $3);
    `;
    await client.query(insertActiveQuery, [sessionId, role, content]);

    // 3. Count messages in Table 2 for this session
    const countQuery = `
      SELECT COUNT(*) FROM active_session_chat WHERE session_id = $1;
    `;
    const countRes = await client.query(countQuery, [sessionId]);
    const activeCount = parseInt(countRes.rows[0].count, 10);

    // If threshold is reached, execute compaction
    if (activeCount >= messageLimit) {
      console.log(`[Memory Manager] Compaction threshold reached (${activeCount} messages). Compacting...`);

      // 4. Retrieve all current active messages for compaction
      const selectActiveQuery = `
        SELECT role, content FROM active_session_chat 
        WHERE session_id = $1 
        ORDER BY created_at ASC;
      `;
      const activeMessagesRes = await client.query(selectActiveQuery, [sessionId]);
      const messageList = activeMessagesRes.rows;

      // 5. Call LLM to Compact the message list
      const compactedText = await runHistoryCompactor(messageList);

      // 6. Delete all active messages for this session
      const deleteActiveQuery = `
        DELETE FROM active_session_chat WHERE session_id = $1;
      `;
      await client.query(deleteActiveQuery, [sessionId]);

      // 7. Insert the single new 'compact' message
      const insertCompactedQuery = `
        INSERT INTO active_session_chat (session_id, role, content)
        VALUES ($1, 'compact', $2);
      `;
      await client.query(insertCompactedQuery, [sessionId, compactedText]);
    }

    // Commit Transaction
    await client.query('COMMIT');
    console.log(`[Memory Manager] Message saved successfully. Active count: ${activeCount}`);
  } catch (error) {
    // Rollback on failure
    await client.query('ROLLBACK');
    console.error('[Memory Manager] Transaction error, rolling back:', error);
    throw error;
  } finally {
    client.release();
  }
}

/**
 * Helper to call Gemini/Vertex AI to generate the summary text
 */
async function runHistoryCompactor(messages) {
  const systemInstruction = `
Bạn là một trợ lý tóm tắt và quản lý ngữ cảnh trò chuyện chuyên nghiệp cho hệ thống Giáo dục RAG.
Nhiệm vụ của bạn là đọc toàn bộ lịch sử trò chuyện được gửi kèm (chứa tin nhắn 'compact' trước đó ở đầu và các cặp tin nhắn 'user'/'assistant' mới).

Hãy tổng hợp và tạo ra một bản tóm tắt mới ngắn gọn dưới dạng danh sách gạch đầu dòng ghi nhận:
- Các chủ đề cốt lõi đang thảo luận trong phiên.
- Các vị trí tài liệu học tập đã được nhắc tới (trang sách nào, tập sách nào).
- Các câu hỏi chưa được giải quyết hoặc trọng tâm người dùng đang quan tâm tiếp theo.

Đầu ra phải là một câu tóm tắt bằng tiếng Việt rõ ràng để chèn vào tin nhắn với vai trò 'compact'. Không tự trả lời câu hỏi.
  `.trim();

  const formattedPrompt = messages
    .map(msg => `- ${msg.role.toUpperCase()}: ${msg.content}`)
    .join('\n');

  const response = await ai.models.generateContent({
    model: 'gemini-2.5-flash',
    contents: formattedPrompt,
    config: {
      systemInstruction: systemInstruction,
      temperature: 0.2
    }
  });

  return `Tóm tắt hội thoại trước đó: ${response.text.trim()}`;
}

/**
 * Retrieves the active messages to build prompts for the Query Condenser
 * @param {string} sessionId 
 * @returns {Promise<Array<{role: string, content: string}>>}
 */
export async function prepareActiveSessionPrompt(sessionId) {
  const selectQuery = `
    SELECT role, content FROM active_session_chat
    WHERE session_id = $1
    ORDER BY created_at ASC;
  `;
  const res = await dbPool.query(selectQuery, [sessionId]);
  return res.rows;
}
```

