"""
Mentor/Instructor Test Generator Workflow Integration Test Suite
===============================================================
Tests the mentor_test_generator_workflow.json workflow.

Usage:
    python tests/test_mentor_workflow.py
    python tests/test_mentor_workflow.py --url http://localhost:5678
    python tests/test_mentor_workflow.py --verbose
    python tests/test_mentor_workflow.py --test-mode   # use /webhook-test/ path
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_N8N_URL      = "http://localhost:5678"
WEBHOOK_SLUG         = "mentor-test-generator"
WORKFLOW_ID          = "MENTOR_TEST_GENERATOR_WF"
WEBHOOK_PROD_PATH    = f"/webhook/{WORKFLOW_ID}/webhook/{WEBHOOK_SLUG}"
WEBHOOK_TEST_PATH    = f"/webhook-test/{WORKFLOW_ID}/webhook/{WEBHOOK_SLUG}"
TIMEOUT_SECONDS      = 90   # Test generation can take some time


@dataclass
class TestCase:
    name: str
    description: str
    payload: dict
    expect_status: int = 200
    expect_keys: list = field(default_factory=list)
    expect_contains: list = field(default_factory=list)
    expect_not_contains: list = field(default_factory=list)
    skip: bool = False
    skip_reason: str = ""


TEST_CASES = [
    TestCase(
        name="math_test_multi_choice_essay",
        description="Create a grade 3 Math test on multiplication and division with 4 MCQs (4pts) and 2 Essays (6pts)",
        payload={
            "subject": "Toán học",
            "grade": "Lớp 3",
            "topic": "Phép nhân và phép chia trong phạm vi 1000",
            "knowledge_tested": "Bảng nhân 6, bảng chia 6, tính giá trị biểu thức và toán có lời văn giải bằng hai phép tính",
            "difficulty": "Trung bình",
            "thoi_gian": "40 phút",
            "mcq_count": 4,
            "essay_count": 2,
            "mcq_score_total": 4.0,
            "essay_score_total": 6.0,
            "additional_instructions": "Đặt câu hỏi trắc nghiệm thực tế sinh động, phần tự luận có một câu toán đố về số mét vải hoặc lít dầu.",
            "conversation_id": "mentor_conv_999"
        },
        expect_status=200,
        expect_keys=["output", "conversation_id"],
        expect_contains=["TRẮC NGHIỆM", "TỰ LUẬN", "ĐÁP ÁN", "BAREM", "Toán học", "Lớp 3", "mentor_conv_999"],
    ),
    TestCase(
        name="science_test_vietnamese",
        description="Create a grade 4 Science test on water states with 5 MCQs (5pts) and 1 Essay (5pts)",
        payload={
            "mon_hoc": "Khoa học tự nhiên",
            "khoi_lop": "Lớp 4",
            "chu_de": "Nước và các thể của nước",
            "kien_thuc": "Sự chuyển thể của nước, sự bay hơi, ngưng tụ, đông đặc và nóng chảy. Vòng tuần hoàn của nước trong tự nhiên",
            "muc_do": "Khó",
            "thoi_gian": "35 phút",
            "so_cau_trac_nghiem": 5,
            "so_cau_tu_luan": 1,
            "diem_trac_nghiem": 5.0,
            "diem_tu_luan": 5.0,
            "yeu_cau_them": "Phần tự luận yêu cầu học sinh vẽ sơ đồ hoặc giải thích chi tiết hiện tượng vòng tuần hoàn của nước."
        },
        expect_status=200,
        expect_keys=["output"],
        expect_contains=["TRẮC NGHIỆM", "TỰ LUẬN", "ĐÁP ÁN", "BAREM", "Khoa học", "Lớp 4"],
    )
]


@dataclass
class TestResult:
    name: str
    passed: bool
    status_code: object
    elapsed_ms: float
    failures: list
    response_preview: str


def run_test(tc: TestCase, base_url: str, webhook_path: str, verbose: bool) -> TestResult:
    url = base_url + webhook_path
    failures = []
    status_code = None
    elapsed_ms = 0.0
    response_preview = ""

    try:
        t0 = time.monotonic()
        resp = requests.post(url, json=tc.payload, timeout=TIMEOUT_SECONDS)
        elapsed_ms = (time.monotonic() - t0) * 1000
        status_code = resp.status_code

        if status_code != tc.expect_status:
            failures.append(f"HTTP {status_code} != expected {tc.expect_status}")

        try:
            data: Any = resp.json()
        except Exception:
            data = {}
            failures.append("Response is not valid JSON")

        response_preview = json.dumps(data, ensure_ascii=False)[:400]

        for key in tc.expect_keys:
            if key not in data:
                failures.append(f"Missing key {key!r} in response")

        output_text = str(data.get("output", ""))
        response_str = response_preview

        for needle in tc.expect_contains:
            if needle.lower() not in response_str.lower() and needle.lower() not in output_text.lower():
                failures.append(f"Expected substring not found: {needle!r}")

        for needle in tc.expect_not_contains:
            if needle.lower() in response_str.lower() or needle.lower() in output_text.lower():
                failures.append(f"Forbidden substring found: {needle!r}")

    except requests.exceptions.ConnectionError:
        failures.append(f"Connection refused — is n8n running at {base_url}?")
    except requests.exceptions.Timeout:
        failures.append(f"Timed out after {TIMEOUT_SECONDS}s")
    except Exception as exc:
        failures.append(f"Unexpected error: {exc}")

    return TestResult(
        name=tc.name,
        passed=(len(failures) == 0),
        status_code=status_code,
        elapsed_ms=elapsed_ms,
        failures=failures,
        response_preview=response_preview,
    )


def print_result(tc: TestCase, result: TestResult, verbose: bool) -> None:
    icon  = "[PASS]" if result.passed else "[FAIL]"
    sc    = f"HTTP {result.status_code}" if result.status_code else "     N/A"
    ms    = f"{result.elapsed_ms:>7.0f}ms"
    print(f"  {icon} {tc.name:<42} {sc}  {ms}")
    print(f"         {tc.description}")
    if not result.passed:
        for f in result.failures:
            print(f"         ! {f}")
    if verbose and result.response_preview:
        print(f"         preview: {result.response_preview[:300]}...")
    print()


def pre_flight_check(base_url: str, test_mode: bool) -> str:
    try:
        h = requests.get(f"{base_url}/healthz", timeout=5)
        if h.status_code != 200:
            print(f"[!] n8n health check returned HTTP {h.status_code} at {base_url}/healthz")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"""\n[ERROR] Cannot connect to n8n at {base_url}

  Make sure n8n is running:
    cd n8n-docker && docker compose up -d

  Then open http://localhost:5678 and import the new workflow file (mentor_test_generator_workflow.json).
""")
        sys.exit(1)

    prod_path = WEBHOOK_PROD_PATH
    test_path = WEBHOOK_TEST_PATH

    if test_mode:
        print(f"  [INFO] Using TEST webhook path: {test_path}")
        return test_path
    else:
        print(f"  [INFO] Using PRODUCTION webhook path: {prod_path}")
        print("         Make sure the workflow is ACTIVE in the n8n editor.")
        return prod_path


def main():
    parser = argparse.ArgumentParser(description="Mentor/Instructor Test Generator Workflow Integration Test Suite")
    parser.add_argument("--url", default=DEFAULT_N8N_URL, help=f"Base URL of n8n server (default: {DEFAULT_N8N_URL})")
    parser.add_argument("--verbose", action="store_true", help="Print response preview even on success")
    parser.add_argument("--case", help="Run only a specific test case by name")
    parser.add_argument("--test-mode", action="store_true", help="Send to test webhook endpoint instead of production")

    args = parser.parse_args()

    print(f"\n======================================================================")
    print("  Mentor Test Generator Workflow Integration Test Suite")
    print(f"======================================================================\n")

    webhook_path = pre_flight_check(args.url, args.test_mode)
    print(f"  [INFO] Targeting: {args.url}\n")

    cases_to_run = TEST_CASES
    if args.case:
        cases_to_run = [tc for tc in TEST_CASES if tc.name == args.case]
        if not cases_to_run:
            print(f"[ERROR] Test case {args.case!r} not found in TEST_CASES.")
            sys.exit(1)

    passed_count = 0
    total_count = 0

    for tc in cases_to_run:
        if tc.skip:
            print(f"  [SKIP] {tc.name:<42} (Reason: {tc.skip_reason})\n")
            continue

        total_count += 1
        print(f"Running: {tc.name}...")
        result = run_test(tc, args.url, webhook_path, args.verbose)
        print_result(tc, result, args.verbose or not result.passed)

        if result.passed:
            passed_count += 1

    print(f"======================================================================")
    print(f"Result: {passed_count}/{total_count} passed.")
    print(f"======================================================================\n")

    if passed_count < total_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
