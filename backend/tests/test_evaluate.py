from pathlib import Path

from eval.evaluate import (
    check_expected_facts,
    check_source,
    evaluate_case,
    load_cases,
    main,
)


CASES_PATH = Path(__file__).resolve().parent.parent / "eval" / "cases.json"


def _passing_metrics(*_args, **_kwargs):
    return {
        "faithfulness": {
            "score": 1.0,
            "passed": True,
            "is_successful": True,
            "reason": "grounded",
        },
        "answer_relevancy": {
            "score": 1.0,
            "passed": True,
            "is_successful": True,
            "reason": "relevant",
        },
        "contextual_relevancy": {
            "score": 1.0,
            "passed": True,
            "is_successful": True,
            "reason": "context relevant",
        },
    }


def _failing_faithfulness_metrics(*_args, **_kwargs):
    return {
        "faithfulness": {
            "score": 0.1,
            "passed": False,
            "is_successful": False,
            "reason": "unsupported claim",
        },
        "answer_relevancy": {
            "score": 1.0,
            "passed": True,
            "is_successful": True,
            "reason": "relevant",
        },
        "contextual_relevancy": {
            "score": 1.0,
            "passed": True,
            "is_successful": True,
            "reason": "context relevant",
        },
    }


def _failing_answer_relevancy_metrics(*_args, **_kwargs):
    return {
        "faithfulness": {
            "score": 1.0,
            "passed": True,
            "is_successful": True,
            "reason": "grounded",
        },
        "answer_relevancy": {
            "score": 0.1,
            "passed": False,
            "is_successful": False,
            "reason": "off-topic answer",
        },
        "contextual_relevancy": {
            "score": 1.0,
            "passed": True,
            "is_successful": True,
            "reason": "context relevant",
        },
    }


def _failing_contextual_relevancy_metrics(*_args, **_kwargs):
    return {
        "faithfulness": {
            "score": 1.0,
            "passed": True,
            "is_successful": True,
            "reason": "grounded",
        },
        "answer_relevancy": {
            "score": 1.0,
            "passed": True,
            "is_successful": True,
            "reason": "relevant",
        },
        "contextual_relevancy": {
            "score": 0.1,
            "passed": False,
            "is_successful": False,
            "reason": "irrelevant context",
        },
    }


def test_load_cases_reads_real_cases_json():
    cases = load_cases(CASES_PATH)

    assert isinstance(cases, list)
    assert len(cases) >= 1
    first = cases[0]
    assert "id" in first
    assert "question" in first
    assert "expected_source" in first
    assert "expected_facts" in first
    assert "allow_unsupported_claims" in first


def test_check_source_match():
    result = check_source("ozempic.pdf", "ozempic.pdf")

    assert result["passed"] is True
    assert result["reason"] == ""


def test_check_source_mismatch():
    result = check_source("humira.pdf", "ozempic.pdf")

    assert result["passed"] is False
    assert "ozempic.pdf" in result["reason"]
    assert "humira.pdf" in result["reason"]


def test_check_expected_facts_case_insensitive():
    result = check_expected_facts(
        "The active ingredient is Semaglutide.",
        ["semaglutide"],
    )

    assert result["passed"] is True
    assert result["missing_facts"] == []


def test_check_expected_facts_reports_missing():
    result = check_expected_facts(
        "Ozempic is a medicine.",
        ["semaglutide", "Ozempic"],
    )

    assert result["passed"] is False
    assert result["missing_facts"] == ["semaglutide"]


def test_evaluate_case_with_mocked_ask_fn():
    case = {
        "id": "ozempic-active-ingredient",
        "product": "ozempic",
        "question": "What is the active ingredient in Ozempic?",
        "expected_source": "ozempic-epar-product-information_en.pdf",
        "expected_facts": ["semaglutide"],
        "allow_unsupported_claims": False,
    }

    def mock_ask(question):
        assert question == case["question"]
        return {
            "answer": "The active ingredient is semaglutide.",
            "source": "ozempic-epar-product-information_en.pdf",
            "context": "Ozempic contains semaglutide.",
        }

    result = evaluate_case(
        case, ask_fn=mock_ask, metrics_fn=_passing_metrics
    )

    assert result["id"] == "ozempic-active-ingredient"
    assert result["passed"] is True
    assert result["source_check"]["passed"] is True
    assert result["facts_check"]["passed"] is True
    assert result["grounding"]["status"] == "evaluated"
    assert result["grounding"]["passed"] is True
    assert result["metrics"]["faithfulness"]["passed"] is True
    assert result["answer"] == "The active ingredient is semaglutide."
    assert result["context"] == "Ozempic contains semaglutide."
    assert result["source"] == "ozempic-epar-product-information_en.pdf"


def test_evaluate_case_allow_unsupported_false_fails_on_faithfulness():
    case = {
        "id": "grounding-fail",
        "product": "ozempic",
        "question": "What is Ozempic?",
        "expected_source": "ozempic.pdf",
        "expected_facts": ["Ozempic"],
        "allow_unsupported_claims": False,
    }

    def mock_ask(_question):
        return {
            "answer": "Ozempic is a medicine.",
            "source": "ozempic.pdf",
            "context": "Some context.",
        }

    result = evaluate_case(
        case, ask_fn=mock_ask, metrics_fn=_failing_faithfulness_metrics
    )

    assert result["passed"] is False
    assert result["grounding"]["status"] == "evaluated"
    assert result["grounding"]["passed"] is False
    assert any(
        "grounding" in reason or "faithfulness" in reason
        for reason in result["failure_reasons"]
    )


def test_evaluate_case_faithfulness_fail_even_if_source_and_facts_pass():
    case = {
        "id": "faithfulness-only-fail",
        "product": "ozempic",
        "question": "What is Ozempic?",
        "expected_source": "ozempic.pdf",
        "expected_facts": ["Ozempic"],
        "allow_unsupported_claims": False,
    }

    def mock_ask(_question):
        return {
            "answer": "Ozempic cures everything instantly.",
            "source": "ozempic.pdf",
            "context": "Ozempic is indicated for type 2 diabetes.",
        }

    result = evaluate_case(
        case, ask_fn=mock_ask, metrics_fn=_failing_faithfulness_metrics
    )

    assert result["source_check"]["passed"] is True
    assert result["facts_check"]["passed"] is True
    assert result["passed"] is False
    assert result["grounding"]["passed"] is False


def test_evaluate_case_all_three_metrics_pass_overall_pass():
    case = {
        "id": "all-metrics-pass",
        "product": "ozempic",
        "question": "What is the active ingredient in Ozempic?",
        "expected_source": "ozempic.pdf",
        "expected_facts": ["semaglutide"],
        "allow_unsupported_claims": False,
    }

    def mock_ask(_question):
        return {
            "answer": "The active ingredient is semaglutide.",
            "source": "ozempic.pdf",
            "context": "Ozempic contains semaglutide.",
        }

    result = evaluate_case(
        case, ask_fn=mock_ask, metrics_fn=_passing_metrics
    )

    assert result["passed"] is True
    assert result["metrics"]["faithfulness"]["passed"] is True
    assert result["metrics"]["answer_relevancy"]["passed"] is True
    assert result["metrics"]["contextual_relevancy"]["passed"] is True
    assert result["grounding"]["passed"] is True
    assert result["failure_reasons"] == []


def test_evaluate_case_answer_relevancy_alone_fails_case():
    case = {
        "id": "answer-relevancy-only-fail",
        "product": "ozempic",
        "question": "What is the active ingredient in Ozempic?",
        "expected_source": "ozempic.pdf",
        "expected_facts": ["semaglutide"],
        "allow_unsupported_claims": False,
    }

    def mock_ask(_question):
        return {
            "answer": "The active ingredient is semaglutide.",
            "source": "ozempic.pdf",
            "context": "Ozempic contains semaglutide.",
        }

    result = evaluate_case(
        case, ask_fn=mock_ask, metrics_fn=_failing_answer_relevancy_metrics
    )

    assert result["source_check"]["passed"] is True
    assert result["facts_check"]["passed"] is True
    assert result["grounding"]["passed"] is True
    assert result["metrics"]["faithfulness"]["passed"] is True
    assert result["metrics"]["contextual_relevancy"]["passed"] is True
    assert result["metrics"]["answer_relevancy"]["passed"] is False
    assert result["passed"] is False
    assert any(
        "answer_relevancy" in reason for reason in result["failure_reasons"]
    )


def test_evaluate_case_contextual_relevancy_alone_fails_case():
    case = {
        "id": "contextual-relevancy-only-fail",
        "product": "ozempic",
        "question": "What is the active ingredient in Ozempic?",
        "expected_source": "ozempic.pdf",
        "expected_facts": ["semaglutide"],
        "allow_unsupported_claims": False,
    }

    def mock_ask(_question):
        return {
            "answer": "The active ingredient is semaglutide.",
            "source": "ozempic.pdf",
            "context": "Ozempic contains semaglutide.",
        }

    result = evaluate_case(
        case,
        ask_fn=mock_ask,
        metrics_fn=_failing_contextual_relevancy_metrics,
    )

    assert result["source_check"]["passed"] is True
    assert result["facts_check"]["passed"] is True
    assert result["grounding"]["passed"] is True
    assert result["metrics"]["faithfulness"]["passed"] is True
    assert result["metrics"]["answer_relevancy"]["passed"] is True
    assert result["metrics"]["contextual_relevancy"]["passed"] is False
    assert result["passed"] is False
    assert any(
        "contextual_relevancy" in reason
        for reason in result["failure_reasons"]
    )



def test_evaluate_case_empty_context_skips_metrics_and_fails_grounding():
    case = {
        "id": "empty-context",
        "product": "ozempic",
        "question": "What is Ozempic?",
        "expected_source": "ozempic.pdf",
        "expected_facts": ["Ozempic"],
        "allow_unsupported_claims": False,
    }
    ask_calls = []

    def mock_ask(question):
        ask_calls.append(question)
        return {
            "answer": "Ozempic is a medicine.",
            "source": "ozempic.pdf",
            "context": "",
        }

    metrics_calls = []

    def mock_metrics(*args, **kwargs):
        metrics_calls.append((args, kwargs))
        return _passing_metrics()

    result = evaluate_case(
        case, ask_fn=mock_ask, metrics_fn=mock_metrics
    )

    assert len(ask_calls) == 1
    assert metrics_calls == []
    assert result["metrics"]["faithfulness"].get("skipped") is True
    assert result["metrics"]["answer_relevancy"].get("skipped") is True
    assert result["metrics"]["contextual_relevancy"].get("skipped") is True
    assert result["grounding"]["status"] == "failed"
    assert result["grounding"]["passed"] is False
    assert result["passed"] is False
    assert any("grounding" in reason for reason in result["failure_reasons"])


def test_evaluate_case_fails_on_source_mismatch():
    case = {
        "id": "wrong-source",
        "product": "ozempic",
        "question": "What is Ozempic?",
        "expected_source": "ozempic.pdf",
        "expected_facts": ["Ozempic"],
        "allow_unsupported_claims": False,
    }

    def mock_ask(_question):
        return {
            "answer": "Ozempic is a medicine.",
            "source": "humira.pdf",
            "context": "context",
        }

    result = evaluate_case(
        case, ask_fn=mock_ask, metrics_fn=_passing_metrics
    )

    assert result["passed"] is False
    assert result["source_check"]["passed"] is False


def test_main_loads_backend_dotenv_before_run(monkeypatch):
    loaded = {}

    def fake_load_dotenv(path=None, **_kwargs):
        loaded["path"] = Path(path) if path is not None else None
        return True

    monkeypatch.setattr("eval.evaluate.load_dotenv", fake_load_dotenv)
    monkeypatch.setattr("eval.evaluate.run", lambda path=None: 0)

    assert main([]) == 0
    assert loaded["path"] == Path(__file__).resolve().parent.parent / ".env"
