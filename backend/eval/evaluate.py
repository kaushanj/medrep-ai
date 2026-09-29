"""Deterministic RAG evaluator against the golden dataset (issue #16)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from services.rag import ask_rag

DEFAULT_CASES_PATH = Path(__file__).resolve().parent / "cases.json"


def load_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    cases_path = Path(path) if path is not None else DEFAULT_CASES_PATH
    with cases_path.open(encoding="utf-8") as f:
        payload = json.load(f)
    return payload["cases"]


def check_source(actual_source: str, expected_source: str) -> dict[str, Any]:
    if actual_source == expected_source:
        return {"passed": True, "reason": ""}
    return {
        "passed": False,
        "reason": (
            f"expected source {expected_source!r}, got {actual_source!r}"
        ),
    }


def check_expected_facts(
    answer: str, expected_facts: list[str]
) -> dict[str, Any]:
    answer_lower = answer.lower()
    missing = [fact for fact in expected_facts if fact.lower() not in answer_lower]
    if not missing:
        return {"passed": True, "missing_facts": [], "reason": ""}
    return {
        "passed": False,
        "missing_facts": missing,
        "reason": f"missing expected facts: {missing}",
    }


def evaluate_case(
    case: dict[str, Any],
    ask_fn: Callable[[str], dict[str, str]] = ask_rag,
) -> dict[str, Any]:
    rag = ask_fn(case["question"])
    answer = rag.get("answer", "")
    source = rag.get("source", "")
    context = rag.get("context", "")

    source_check = check_source(source, case["expected_source"])
    facts_check = check_expected_facts(answer, case.get("expected_facts") or [])

    grounding: dict[str, Any]
    if case.get("allow_unsupported_claims") is False:
        grounding = {
            "status": "deferred",
            "reason": "grounding check deferred to DeepEval (issue #17)",
        }
    else:
        grounding = {"status": "skipped", "reason": ""}

    passed = source_check["passed"] and facts_check["passed"]
    failure_reasons = []
    if not source_check["passed"]:
        failure_reasons.append(source_check["reason"])
    if not facts_check["passed"]:
        failure_reasons.append(facts_check["reason"])

    return {
        "id": case["id"],
        "passed": passed,
        "answer": answer,
        "source": source,
        "context": context,
        "source_check": source_check,
        "facts_check": facts_check,
        "grounding": grounding,
        "failure_reasons": failure_reasons,
    }


def format_case_result(result: dict[str, Any]) -> str:
    source_status = "PASS" if result["source_check"]["passed"] else "FAIL"
    facts_status = "PASS" if result["facts_check"]["passed"] else "FAIL"
    overall = "PASS" if result["passed"] else "FAIL"
    lines = [
        f"Case: {result['id']} [{overall}]",
        f"  Source check: {source_status}",
        f"  Expected facts: {facts_status}",
    ]
    for reason in result.get("failure_reasons") or []:
        lines.append(f"  Failure: {reason}")
    grounding = result.get("grounding") or {}
    if grounding.get("status") == "deferred":
        lines.append(f"  Grounding: deferred ({grounding.get('reason', '')})")
    return "\n".join(lines)


def run(
    path: str | Path | None = None,
    ask_fn: Callable[[str], dict[str, str]] = ask_rag,
) -> int:
    cases = load_cases(path)
    results = [evaluate_case(case, ask_fn=ask_fn) for case in cases]
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count

    for result in results:
        print(format_case_result(result))
        print()

    print(f"Summary: {passed_count} passed, {failed_count} failed")
    return 0 if failed_count == 0 else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv else None
    return run(path=path)


if __name__ == "__main__":
    raise SystemExit(main())
