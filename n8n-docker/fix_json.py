"""
Comprehensive fix for rag_pedagogical_workflow.json:
1. Convert Planner Agent to keypair (build prompt in Parse Planner Decision)
2. Fix Parse Planner Decision to use .first().json
3. Convert Call Python Retrieval API to keypair
"""
import json

with open('rag_pedagogical_workflow.json', 'r', encoding='utf-8') as f:
    wf = json.load(f)

for node in wf['nodes']:
    name = node['name']

    # Fix 1: Planner Agent → keypair with a static planner_prompt built separately
    if name == 'Planner Agent':
        node['parameters']['specifyBody'] = 'keypair'
        node['parameters'].pop('jsonBody', None)
        node['parameters']['bodyParameters'] = {
            'parameters': [
                {'name': 'prompt', 'value': '={{ $json.planner_prompt }}'}
            ]
        }
        print(f"✅ Fixed: {name} → keypair")

    # Fix 2: Parse Planner Decision — prepend planner_prompt building + fix .item → .first()
    if name == 'Parse Planner Decision':
        planner_system_prompt = (
            "Bạn là một Điều phối viên học tập AI (Orchestrator Agent). "
            "Nhiệm vụ của bạn là phân tích câu hỏi của học sinh/phụ huynh để:\\n"
            "1. Chọn ra chuyên gia phù hợp nhất (selected_agent).\\n"
            "2. Xác định câu hỏi này có cần tra cứu ngữ cảnh SGK (RAG) hay không (requires_rag).\\n\\n"
            "Các chuyên gia sẵn có:\\n"
            "- \\\"barem_review\\\": Chuyên gia chấm điểm bài làm dựa trên barem điểm.\\n"
            "- \\\"theory_explanation\\\": Chuyên gia giảng giải lý thuyết khái niệm toán học lớp 3.\\n"
            "- \\\"exercise_generator\\\": Chuyên gia tạo bài tập luyện tập.\\n"
            "- \\\"suggestive_tutor\\\": Gia sư toán gợi mở, dắt tay học sinh.\\n"
            "- \\\"direct_solver\\\": Chuyên gia giải nhanh và đáp số ngay lập tức.\\n"
            "- \\\"default\\\": Giáo viên tiểu học thông thường (chào hỏi, trò chuyện xã giao).\\n\\n"
            "Quy tắc xác định requires_rag:\\n"
            "- true: câu hỏi đề cập đến bài toán lớp 3 cụ thể, bài học SGK, hoặc cần đối chiếu thông tin SGK.\\n"
            "- false: chào hỏi xã giao, câu hỏi thăm phi toán học, hoặc không liên quan đến SGK cụ thể.\\n\\n"
            "Câu hỏi của người dùng:\\n"
        )

        old_code = node['parameters']['jsCode']
        new_code = (
            "const webhookBody = $('Webhook').first().json.body;\n"
            "const userPrompt = webhookBody.prompt;\n\n"
            "// Build planner prompt safely in JS (avoid JSON body interpolation issues)\n"
            "const plannerPrompt = " + json.dumps(planner_system_prompt) + " + userPrompt +\n"
            "  \"\\n\\nHãy trả về chính xác định dạng JSON sau:\\n{\\n  \\\"selected_agent\\\": \\\"tên_agent\\\",\\n  \\\"requires_rag\\\": true | false\\n}\";\n\n"
            "return {\n"
            "  planner_prompt: plannerPrompt,\n"
            "  user_prompt: userPrompt,\n"
            "  body: webhookBody\n"
            "};"
        )
        node['parameters']['jsCode'] = new_code
        print(f"✅ Fixed: {name} → builds planner_prompt")

    # Fix 3: Call Python Retrieval API → keypair
    if name == 'Call Python Retrieval API':
        node['parameters']['specifyBody'] = 'keypair'
        node['parameters'].pop('jsonBody', None)
        node['parameters']['bodyParameters'] = {
            'parameters': [
                {'name': 'text', 'value': '={{ $json.body.prompt }}'},
                {'name': 'tag_name_uuids', 'value': '={{ JSON.stringify([$json.body.subject || "math"]) }}'},
                {'name': 'type', 'value': 'doc'},
                {'name': 'top_k', 'value': '3'}
            ]
        }
        print(f"✅ Fixed: {name} → keypair")

# Also fix Parse Planner Decision to read from its own output now
# Merge Context Nodes reads from $('Parse Planner Decision').first().json
# After our change, it outputs {planner_prompt, user_prompt, body}
# BUT: Parse Planner Decision now OUTPUTS the planner_prompt, and PLANNER AGENT reads it
# So we need a new node order. Actually:
# Webhook → Parse Planner Decision (build prompt) → Planner Agent (call LLM) → [old Parse step merged]
# We need a NEW node to parse the planner's response. Let's add it inline.
# 
# SIMPLER APPROACH: Keep the two-step:
# 1. Parse Planner Decision: just build planner_prompt from webhook, return {planner_prompt, body}
# 2. Planner Agent: call LLM with planner_prompt via keypair
# 3. NEW "Parse Planner Response" node: parse the LLM text into {selected_agent, requires_rag}
# 
# But we don't want to add new nodes. Instead, let's re-use the existing flow:
# Parse Planner Decision currently parses the LLM response.
# We need it to ALSO build the prompt first.
# 
# The cleanest solution: make Parse Planner Decision run BEFORE Planner Agent (build prompt),
# and add a second code node to parse the response. BUT the current node named
# "Parse Planner Decision" is the response-parser node, NOT a pre-processor.
#
# So the fix is: add a pre-processor Code node, or just pass the planner prompt from Webhook.
# 
# ACTUAL CLEANEST FIX: 
# - Keep Webhook → Planner Agent, but change Planner Agent to use keypair
# - Build the prompt in a new inline JS expression using n8n's $expression syntax
# - Use a Code node BEFORE Planner Agent to build the prompt
#
# For now, let's fix Parse Planner Decision to be the pre-processor
# AND update its downstream connections so Planner Agent reads from it.
# Then add a new "Parse Planner Response" code node after Planner Agent.
# 
# SIMPLEST WORKING FIX WITHOUT ADDING NEW NODES:
# Change Planner Agent to use a dynamic expression for the prompt field in keypair:
# value: "={{ 'SYSTEM PROMPT\\nUser: ' + $json.body.prompt }}"
# This way it reads from Webhook directly via $json.body.prompt expression.

# Override: use expression in keypair value directly - no pre-processor needed
for node in wf['nodes']:
    if node['name'] == 'Planner Agent':
        PLANNER_SYSTEM = (
            "Bạn là một Điều phối viên học tập AI (Orchestrator Agent). "
            "Nhiệm vụ là phân tích câu hỏi để:\\n"
            "1. Chọn chuyên gia phù hợp nhất (selected_agent).\\n"
            "2. Xác định có cần tra cứu SGK (requires_rag).\\n\\n"
            "Chuyên gia: barem_review | theory_explanation | exercise_generator | suggestive_tutor | direct_solver | default\\n\\n"
            "requires_rag=true: câu hỏi toán lớp 3 cụ thể / bài học SGK cần đối chiếu.\\n"
            "requires_rag=false: chào hỏi xã giao, câu hỏi thăm phi toán, không cần tra SGK.\\n\\n"
            "Câu hỏi: "
        )
        node['parameters']['bodyParameters'] = {
            'parameters': [
                {
                    'name': 'prompt',
                    'value': "={{ " + json.dumps(PLANNER_SYSTEM) + " + $('Webhook').first().json.body.prompt + \"\\n\\nJSON output:\\n{\\n  \\\"selected_agent\\\": \\\"tên_agent\\\",\\n  \\\"requires_rag\\\": true|false\\n}\" }}"
                }
            ]
        }
        print(f"✅ Updated: {name} → inline expression keypair")

    # Fix Parse Planner Decision back to just parsing the LLM response
    if node['name'] == 'Parse Planner Decision':
        node['parameters']['jsCode'] = (
            "const plannerRes = $('Planner Agent').first().json;\n\n"
            "let selected = \"default\";\n"
            "let requiresRag = false;\n\n"
            "try {\n"
            "  const text = plannerRes.text;\n"
            "  const cleanText = text.replace(/```json/gi, \"\").replace(/```/gi, \"\").trim();\n"
            "  const parsed = JSON.parse(cleanText);\n"
            "  selected = parsed.selected_agent || \"default\";\n"
            "  requiresRag = (parsed.requires_rag === true || parsed.requires_rag === \"true\");\n"
            "} catch (e) {\n"
            "  selected = \"default\";\n"
            "  requiresRag = false;\n"
            "}\n\n"
            "return {\n"
            "  selected_agent: selected,\n"
            "  requires_rag: requiresRag\n"
            "};"
        )
        print(f"✅ Fixed: {name} → uses .first().json")

with open('rag_pedagogical_workflow.json', 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

print("\nValidating JSON...")
with open('rag_pedagogical_workflow.json', 'r', encoding='utf-8') as f:
    test = json.load(f)
print(f"✅ JSON valid. {len(test['nodes'])} nodes.")
