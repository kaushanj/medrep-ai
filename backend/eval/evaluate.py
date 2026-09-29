"""Deterministic RAG evaluator against the golden dataset (issues #16, #17)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from services.rag import ask_rag

DEFAULT_CASES_PATH = Path(__file__).resolve().parent / "cases.json"
BACKEND_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
CONTROLLED_EMPTY_ANSWER = "No relevant documents found."


def _default_metrics_fn(
    question: str, answer: str, context: str, **kwargs: Any
) -> dict[str, dict[str, Any]]:
    """Lazy import so main-deps unit tests collect without deepeval installed."""
    from eval.metrics import run_deepeval_metrics

    return run_deepeval_metrics(question, answer, context, **kwargs)



_REQUIRED_CASE_FIELDS = ("id", "question", "expected_source", "expected_facts")


def load_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    cases_path = Path(path) if path is not None else DEFAULT_CASES_PATH
    with cases_path.open(encoding="utf-8") as f:
        try:
            payload = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid JSON in evaluation cases file {cases_path}: {exc}"
            ) from exc

    if not isinstance(payload, dict) or "cases" not in payload:
        raise ValueError(
            f"evaluation cases file {cases_path} is missing required top-level "
            f"key 'cases'"
        )

    cases = payload["cases"]
    if not isinstance(cases, list):
        raise ValueError(
            f"evaluation cases file {cases_path}: 'cases' must be a list, "
            f"got {type(cases).__name__}"
        )

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(
                f"evaluation cases file {cases_path}: case at index {index} "
                f"must be an object, got {type(case).__name__}"
            )
        missing = [field for field in _REQUIRED_CASE_FIELDS if field not in case]
        if missing:
            case_id = case.get("id", f"index {index}")
            raise ValueError(
                f"evaluation case {case_id!r} is missing required field(s): "
                f"{', '.join(missing)}"
            )
        if not isinstance(case["expected_facts"], list):
            raise ValueError(
                f"evaluation case {case['id']!r}: 'expected_facts' must be a "
                f"list, got {type(case['expected_facts']).__name__}"
            )

    return cases


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


def _answer_makes_claims(answer: str) -> bool:
    text = (answer or "").strip()
    if not text or text == CONTROLLED_EMPTY_ANSWER:
        return False
    return True


def _skipped_metrics(reason: str) -> dict[str, dict[str, Any]]:
    skipped = {
        "score": None,
        "passed": None,
        "is_successful": None,
        "skipped": True,
        "reason": reason,
    }
    return {
        "faithfulness": dict(skipped),
        "answer_relevancy": dict(skipped),
        "contextual_relevancy": dict(skipped),
    }


def evaluate_case(
    case: dict[str, Any],
    ask_fn: Callable[[str], dict[str, str]] = ask_rag,
    metrics_fn: Callable[..., dict[str, dict[str, Any]]] = _default_metrics_fn,
) -> dict[str, Any]:

    rag = ask_fn(case["question"])
    answer = rag.get("answer", "")
    source = rag.get("source", "")
    context = rag.get("context", "")

    source_check = check_source(source, case["expected_source"])
    facts_check = check_expected_facts(answer, case.get("expected_facts") or [])

    context_usable = bool((context or "").strip())
    if context_usable:
        metrics = metrics_fn(case["question"], answer, context)
    else:
        metrics = _skipped_metrics(
            "empty retrieval context; DeepEval metrics skipped"
        )

    allow_unsupported = case.get("allow_unsupported_claims") is not False
    grounding: dict[str, Any]
    if not allow_unsupported:
        if not context_usable:
            if _answer_makes_claims(answer):
                grounding = {
                    "status": "failed",
                    "passed": False,
                    "score": None,
                    "reason": (
                        "empty retrieval context; cannot verify grounding "
                        "of answer claims"
                    ),
                }
            else:
                grounding = {
                    "status": "skipped",
                    "passed": True,
                    "score": None,
                    "reason": (
                        "empty retrieval context; no answer claims to ground"
                    ),
                }
        else:
            faith = metrics.get("faithfulness") or {}
            grounding = {
                "status": "evaluated",
                "passed": bool(faith.get("passed")),
                "score": faith.get("score"),
                "reason": faith.get("reason") or "",
            }
    else:
        grounding = {"status": "skipped", "reason": ""}

    passed = source_check["passed"] and facts_check["passed"]
    failure_reasons: list[str] = []
    if not source_check["passed"]:
        failure_reasons.append(source_check["reason"])
    if not facts_check["passed"]:
        failure_reasons.append(facts_check["reason"])

    if not allow_unsupported and grounding.get("passed") is False:
        passed = False
        reason = grounding.get("reason") or "faithfulness/grounding failed"
        failure_reasons.append(f"grounding: {reason}")

    for metric_name in ("answer_relevancy", "contextual_relevancy"):
        metric = metrics.get(metric_name) or {}
        if metric.get("skipped"):
            continue
        if not metric.get("passed"):
            passed = False
            reason = metric.get("reason") or f"{metric_name} failed"
            failure_reasons.append(f"{metric_name}: {reason}")

    return {
        "id": case["id"],
        "passed": passed,
        "answer": answer,
        "source": source,
        "context": context,
        "source_check": source_check,
        "facts_check": facts_check,
        "grounding": grounding,
        "metrics": metrics,
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

    metrics = result.get("metrics") or {}
    for key, label in (
        ("faithfulness", "Faithfulness"),
        ("answer_relevancy", "Answer relevancy"),
        ("contextual_relevancy", "Contextual relevancy"),
    ):
        metric = metrics.get(key) or {}
        if metric.get("skipped"):
            lines.append(f"  {label}: SKIPPED ({metric.get('reason', '')})")
            continue
        status = "PASS" if metric.get("passed") else "FAIL"
        score = metric.get("score")
        score_text = f" score={score}" if score is not None else ""
        lines.append(f"  {label}: {status}{score_text}")

    grounding = result.get("grounding") or {}
    if grounding.get("status") == "evaluated":
        g_status = "PASS" if grounding.get("passed") else "FAIL"
        lines.append(f"  Grounding: {g_status}")
    elif grounding.get("status") == "failed":
        lines.append(f"  Grounding: FAIL ({grounding.get('reason', '')})")

    for reason in result.get("failure_reasons") or []:
        lines.append(f"  Failure: {reason}")
    return "\n".join(lines)


def run(
    path: str | Path | None = None,
    ask_fn: Callable[[str], dict[str, str]] = ask_rag,
    metrics_fn: Callable[..., dict[str, dict[str, Any]]] = _default_metrics_fn,
) -> int:
    cases = load_cases(path)
    results = [
        evaluate_case(case, ask_fn=ask_fn, metrics_fn=metrics_fn)
        for case in cases
    ]
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count

    for result in results:
        print(format_case_result(result))
        print()

    print(f"Summary: {passed_count} passed, {failed_count} failed")
    return 0 if failed_count == 0 else 1


def main(argv: list[str] | None = None) -> int:
    load_dotenv(BACKEND_ENV_PATH)
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv else None
    return run(path=path)


if __name__ == "__main__":
    raise SystemExit(main())
