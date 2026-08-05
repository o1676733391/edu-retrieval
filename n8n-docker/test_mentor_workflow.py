import sys
import time
import argparse
import requests
import json
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

SAMPLE_TEST_CASES = [
    {
        "name": "1. Generate Exam & Barem (JSON Output)",
        "payload": {
            "action": "generate",
            "subject": "Toán học",
            "grade": "Lớp 3",
            "topic": "Phép nhân và phép chia trong phạm vi 1000",
            "difficulty": "Trung bình",
            "time_limit": "30 phút",
            "mcq_count": 4,
            "essay_count": 2,
            "mcq_score_total": 4.0,
            "essay_score_total": 6.0,
            "additional_instructions": "Cho 1 câu bài toán có lời văn thực tế."
        }
    },
    {
        "name": "2. Grade Student Submission against Barem",
        "payload": {
            "action": "grade",
            "test_id": "TEST_MATH3_SAMPLE_01",
            "student_id": "HS_NGUYEN_VAN_A",
            "barem": {
                "test_id": "TEST_MATH3_SAMPLE_01",
                "mcq_answers": [
                    {"question_id": "MCQ_1", "correct_option": "B", "score": 1.0},
                    {"question_id": "MCQ_2", "correct_option": "A", "score": 1.0}
                ],
                "essay_answers": [
                    {
                        "question_id": "ESSAY_1",
                        "score": 3.0,
                        "solution_steps": [
                            {"step": 1, "description": "Tìm số kilôgam gạo trong mỗi bao: 45 : 5 = 9 (kg)", "score": 1.5},
                            {"step": 2, "description": "Tìm số kilôgam gạo trong 8 bao: 9 x 8 = 72 (kg). Đáp số: 72 kg", "score": 1.5}
                        ]
                    }
                ]
            },
            "student_submission": {
                "MCQ_1": "B",
                "MCQ_2": "C",
                "ESSAY_1": "Lời giải:\nMỗi bao có số kg gạo là:\n45 : 5 = 9 (kg)\n8 bao có số kg gạo là:\n9 x 8 = 72 (kg)\nĐáp số: 72 kg"
            }
        }
    }
]

def run_tests(host, port, use_production):
    path = "webhook" if use_production else "webhook-test"
    url = f"http://{host}:{port}/{path}/mentor-test-generator"

    print(f"{Colors.HEADER}{Colors.BOLD}=== Mentor Test Generator & Grading Workflow Test Suite ==={Colors.ENDC}")
    print(f"Target URL: {Colors.OKBLUE}{url}{Colors.ENDC}")
    print("=" * 60)

    for case in SAMPLE_TEST_CASES:
        name = case["name"]
        payload = case["payload"]

        print(f"\n{Colors.BOLD}Running: {name}{Colors.ENDC}")
        print(f"Payload:\n{json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        start_time = time.time()
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=payload, headers=headers, timeout=90)
            elapsed = time.time() - start_time
            
            print(f"Response Time: {elapsed:.2f} seconds")
            if response.status_code == 200:
                try:
                    res_data = response.json()
                    print(f"Status: {Colors.OKGREEN}200 OK (Success){Colors.ENDC}")
                    print(f"Parsed JSON Output:\n{Colors.OKBLUE}{json.dumps(res_data, ensure_ascii=False, indent=2)}{Colors.ENDC}")
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
    parser = argparse.ArgumentParser(description="Test script for Mentor Test Generator & Grading n8n workflow")
    parser.add_argument("--host", default="localhost", help="n8n host (default: localhost)")
    parser.add_argument("--port", default="5678", help="n8n port (default: 5678)")
    parser.add_argument("--production", action="store_true", help="Send to production webhook (/webhook/...)")

    args = parser.parse_args()
    run_tests(args.host, args.port, args.production)
