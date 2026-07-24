import sys
import time
import argparse
import requests
import json
import io

# Force UTF-8 encoding for standard output and error to support Vietnamese characters on Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# Terminal colors for beautiful logs
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Test scenarios representing different routing branches
TEST_CASES = [
    {
        "name": "1. Automatic Semantic RAG (Suggestive Tutor)",
        "payload": {
            "prompt": "Con muốn làm bài 2 trang 15 tập 1 nhưng chưa biết bắt đầu thế nào. Cô gợi ý cho con được không?",
            "agent_mode": "default", # Will rely on Planner to detect 'suggestive_tutor' and 'requires_rag: true'
            "subject": "math"
        }
    },
    {
        "name": "2. Explicit Mode Override (Theory Explanation)",
        "payload": {
            "prompt": "Phép cộng là gì hả cô? Giải thích bằng hình ảnh trực quan nhé.",
            "agent_mode": "theory_explanation", # Bypasses planner and directly routes to theory explanation
            "subject": "math"
        }
    },
    {
        "name": "3. Non-RAG Path (General Chit-Chat / Simple Math)",
        "payload": {
            "prompt": "Chào cô giáo, chúc cô một ngày tốt lành! Cô khỏe không ạ?",
            "agent_mode": "default", # Planner should detect chitchat and route to Default Teacher with 'requires_rag: false'
            "subject": "math"
        }
    },
    {
        "name": "4. Direct Solver (Direct Answer + Steps)",
        "payload": {
            "prompt": "Giải giúp em bài ôn tập phép cộng trang 15, cho em đáp số nhanh luôn.",
            "agent_mode": "direct_solver",
            "subject": "math"
        }
    },
    {
        "name": "5. Fallback Guardrail (Out of Scope / Empty RAG)",
        "payload": {
            "prompt": "Giải giùm em bài toán vi phân lớp 12 nâng cao về tích phân bất định.",
            "agent_mode": "default", # Should lookup and find 0 chunks, hitting the Guardrail and returning fallback msg
            "subject": "math"
        }
    }
]

def run_tests(host, port, use_production, api_key):
    # Determine webhook path: n8n uses /webhook-test/ for active editor runs, and /webhook/ for active production workflows
    path = "webhook" if use_production else "webhook-test"
    url = f"http://{host}:{port}/{path}/COEDNaQ6fu6k1xeE/webhook/rag-math-assistant"
    
    print(f"{Colors.HEADER}{Colors.BOLD}=== RAG Pedagogical Math Assistant Workflow Test Suite ==={Colors.ENDC}")
    print(f"Target URL: {Colors.OKBLUE}{url}{Colors.ENDC}")
    if not use_production:
        print(f"{Colors.WARNING}Note: Make sure to click 'Listen for test event' or 'Execute workflow' in the n8n UI before running if you are in test editor mode.{Colors.ENDC}")
    print("=" * 60)

    for case in TEST_CASES:
        name = case["name"]
        payload = case["payload"].copy()
        
        # Inject API key if provided
        if api_key:
            payload["gemini_api_key"] = api_key
            
        print(f"\n{Colors.BOLD}Running: {name}{Colors.ENDC}")
        print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        start_time = time.time()
        try:
            headers = {
                "Content-Type": "application/json"
            }
            response = requests.post(url, json=payload, headers=headers, timeout=90)
            elapsed = time.time() - start_time
            
            print(f"Response Time: {elapsed:.2f} seconds")
            if response.status_code == 200:
                try:
                    res_data = response.json()
                    print(f"Status: {Colors.OKGREEN}200 OK (Success){Colors.ENDC}")
                    print(f"Output:\n{Colors.OKBLUE}{res_data.get('output', 'No output field found')}{Colors.ENDC}")
                except Exception as e:
                    print(f"Status: {Colors.WARNING}200 OK but JSON decode failed: {e}{Colors.ENDC}")
                    print(f"Raw Response: {response.text}")
            else:
                print(f"Status: {Colors.FAIL}{response.status_code} Error{Colors.ENDC}")
                print(f"Raw Response: {response.text}")
                
        except requests.exceptions.Timeout:
            print(f"{Colors.FAIL}Error: Request timed out after 90 seconds.{Colors.ENDC}")
        except requests.exceptions.ConnectionError:
            print(f"{Colors.FAIL}Error: Connection refused. Is n8n running on http://{host}:{port}?{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}Error: {e}{Colors.ENDC}")
        print("-" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test script for n8n RAG Multi-Agent Pedagogical Math Assistant")
    parser.add_argument("--host", default="localhost", help="n8n host (default: localhost)")
    parser.add_argument("--port", default="5678", help="n8n port (default: 5678)")
    parser.add_argument("--production", action="store_true", help="Send to production webhook (/webhook/...) instead of test editor webhook (/webhook-test/...)")
    parser.add_argument("--key", default="", help="Optional Google Gemini API key to override environment variable")
    
    args = parser.parse_args()
    run_tests(args.host, args.port, args.production, args.key)
