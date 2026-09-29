from pathlib import Path

from eval.evaluate import (
    check_expected_facts,
    check_source,
    evaluate_case,
    load_cases,
)


CASES_PATH = Path(__file__).resolve().parent.parent / "eval" / "cases.json"


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

    result = evaluate_case(case, ask_fn=mock_ask)

    assert result["id"] == "ozempic-active-ingredient"
    assert result["passed"] is True
    assert result["source_check"]["passed"] is True
    assert result["facts_check"]["passed"] is True
    assert result["grounding"]["status"] == "deferred"
    assert result["answer"] == "The active ingredient is semaglutide."
    assert result["context"] == "Ozempic contains semaglutide."
    assert result["source"] == "ozempic-epar-product-information_en.pdf"


def test_evaluate_case_allow_unsupported_false_does_not_fail_on_grounding():
    case = {
        "id": "grounding-deferred",
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

    result = evaluate_case(case, ask_fn=mock_ask)

    assert result["passed"] is True
    assert result["grounding"]["status"] == "deferred"
    assert result["grounding"].get("passed") is not False


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

    result = evaluate_case(case, ask_fn=mock_ask)

    assert result["passed"] is False
    assert result["source_check"]["passed"] is False
