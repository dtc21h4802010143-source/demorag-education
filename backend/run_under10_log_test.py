import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_CATEGORIES = [
    "chuong_trinh_dao_tao",
    "co_so_vat_chat",
    "hoc_phi_chinh_sach",
    "hoi_dong_tot_nghiep",
    "sinh_vien_quoc_te",
    "the_sinh_vien",
    "tuyen_sinh_tu_xa",
]


def load_cases(file_path: Path, categories: list[str], per_category: int) -> list[dict]:
    data = json.loads(file_path.read_text(encoding="utf-8"))
    all_categories = data.get("categories", {})

    cases: list[dict] = []
    for category in categories:
        rows = all_categories.get(category, [])[: max(1, per_category)]
        for row in rows:
            cases.append(
                {
                    "category": category,
                    "id": row.get("id", ""),
                    "question": row.get("question", ""),
                }
            )
    return cases


def call_chat_stream(base_url: str, question: str, client_id: str, timeout: int) -> tuple[str, int]:
    payload = {"question": question, "client_id": client_id}
    req = urllib.request.Request(
        url=f"{base_url}/chat/stream",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    answer_parts: list[str] = []
    status_code = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status_code = resp.status
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[6:])
            except json.JSONDecodeError:
                continue

            if event.get("type") == "token":
                answer_parts.append(event.get("content", ""))
            elif event.get("type") == "done":
                break

    return "".join(answer_parts).strip(), status_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Run chat stream smoke test for under-10 categories.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--per-category", type=int, default=2, help="Number of questions per category")
    parser.add_argument("--timeout", type=int, default=90, help="Request timeout seconds")
    parser.add_argument(
        "--input",
        default="selected_qa_under10_categories.json",
        help="Input file generated from selected QA",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1

    cases = load_cases(input_path, DEFAULT_CATEGORIES, args.per_category)
    if not cases:
        print("No test cases found.")
        return 1

    print(f"Loaded {len(cases)} cases from {input_path}")
    success = 0

    for idx, case in enumerate(cases, start=1):
        client_id = f"smoke-{case['category']}-{idx}"
        print(f"\n[{idx}/{len(cases)}] category={case['category']} id={case['id']}")
        print(f"Q: {case['question']}")
        try:
            answer, status_code = call_chat_stream(
                base_url=args.base_url,
                question=case["question"],
                client_id=client_id,
                timeout=args.timeout,
            )
            preview = (answer[:180] + "...") if len(answer) > 180 else answer
            print(f"HTTP {status_code} | answer_preview: {preview}")
            success += 1
        except urllib.error.HTTPError as ex:
            body = ex.read().decode("utf-8", errors="ignore")
            print(f"HTTPError {ex.code}: {body}")
        except Exception as ex:
            print(f"Request failed: {ex}")

    print(f"\nDone. success={success}/{len(cases)}")
    return 0 if success == len(cases) else 2


if __name__ == "__main__":
    sys.exit(main())
