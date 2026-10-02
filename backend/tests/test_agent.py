"""Unit tests for services.agent.ask_agent (mocked Bedrock + tool)."""

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from services.agent import (
    SAFE_NO_RESULTS,
    SAFE_TOOL_ERROR,
    SIMPLE_GREETING_RESPONSE,
    ask_agent,
    match_simple_greeting,
)


def test_match_simple_greeting_positives():
    for phrase in (
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "Hi",
        "  hello! ",
        "GOOD MORNING",
    ):
        assert match_simple_greeting(phrase) == SIMPLE_GREETING_RESPONSE


def test_match_simple_greeting_negatives():
    for phrase in (
        "Who won the World Cup?",
        "hi there",
        "What is Ozempic used for?",
        "",
        "   ",
    ):
        assert match_simple_greeting(phrase) is None


def test_ask_agent_greeting_short_circuits_without_model():
    model = MagicMock()

    result = ask_agent("Hi", model)

    assert result == SIMPLE_GREETING_RESPONSE
    model.invoke.assert_not_called()


def _ok_evidence(query: str = "What is Ozempic used for?") -> dict:
    return {
        "status": "ok",
        "source": "internal_documents",
        "query": query,
        "results": [
            {
                "text": "Ozempic is indicated for type 2 diabetes.",
                "score": 0.91,
                "metadata": {"product_name": "Ozempic"},
            }
        ],
        "error": None,
    }


def _ok_dailymed_evidence(
    query: str = "What is Ozempic used for?",
    product_name: str = "Ozempic",
) -> dict:
    return {
        "status": "ok",
        "source": "dailymed",
        "query": query,
        "results": [
            {
                "text": "Ozempic (semaglutide) is indicated for type 2 diabetes.",
                "score": 0.88,
                "metadata": {"product_name": product_name},
            }
        ],
        "error": None,
    }


def _mock_tool(return_value=None, side_effect=None) -> MagicMock:
    tool = MagicMock()
    if side_effect is not None:
        tool.invoke.side_effect = side_effect
    else:
        tool.invoke.return_value = return_value
    return tool


def test_ask_agent_successful_tool_call_returns_final_answer():
    question = "What is Ozempic used for?"
    tool_call = {
        "name": "search_internal_documents",
        "args": {"query": question},
        "id": "call-1",
        "type": "tool_call",
    }
    first_response = AIMessage(content="", tool_calls=[tool_call])
    final_answer = "Ozempic is used for type 2 diabetes."
    final_response = AIMessage(content=final_answer)
    mock_tool = _mock_tool(return_value=_ok_evidence(question))

    model = MagicMock()
    model.invoke.side_effect = [first_response, final_response]

    with patch(
        "services.agent.TOOL_REGISTRY",
        {"search_internal_documents": mock_tool},
    ):
        result = ask_agent(question, model)

    assert result == final_answer
    mock_tool.invoke.assert_called_once_with({"query": question})
    assert model.invoke.call_count == 2


def test_ask_agent_no_tool_call_returns_safe_no_results():
    first_response = AIMessage(content="I know about Ozempic.")
    model = MagicMock()
    model.invoke.return_value = first_response
    mock_tool = _mock_tool()

    with patch(
        "services.agent.TOOL_REGISTRY",
        {"search_internal_documents": mock_tool},
    ):
        result = ask_agent("What is Ozempic used for?", model)

    assert result == SAFE_NO_RESULTS
    mock_tool.invoke.assert_not_called()
    assert model.invoke.call_count == 1


def test_ask_agent_no_results_skips_second_llm_call():
    question = "What is UnknownDrug used for?"
    tool_call = {
        "name": "search_internal_documents",
        "args": {"query": question},
        "id": "call-2",
        "type": "tool_call",
    }
    first_response = AIMessage(content="", tool_calls=[tool_call])
    model = MagicMock()
    model.invoke.return_value = first_response

    evidence = {
        "status": "no_results",
        "source": "internal_documents",
        "query": question,
        "results": [],
        "error": None,
    }
    mock_tool = _mock_tool(return_value=evidence)

    with patch(
        "services.agent.TOOL_REGISTRY",
        {"search_internal_documents": mock_tool},
    ):
        result = ask_agent(question, model)

    assert result == SAFE_NO_RESULTS
    assert model.invoke.call_count == 1


def test_ask_agent_tool_error_skips_second_llm_call():
    question = "What is Ozempic used for?"
    tool_call = {
        "name": "search_internal_documents",
        "args": {"query": question},
        "id": "call-3",
        "type": "tool_call",
    }
    first_response = AIMessage(content="", tool_calls=[tool_call])
    model = MagicMock()
    model.invoke.return_value = first_response

    evidence = {
        "status": "error",
        "source": "internal_documents",
        "query": question,
        "results": [],
        "error": "Internal document search failed.",
    }
    mock_tool = _mock_tool(return_value=evidence)

    with patch(
        "services.agent.TOOL_REGISTRY",
        {"search_internal_documents": mock_tool},
    ):
        result = ask_agent(question, model)

    assert result == SAFE_TOOL_ERROR
    assert model.invoke.call_count == 1


def test_ask_agent_second_call_receives_grounded_message_history():
    question = "What is Ozempic used for?"
    tool_call = {
        "name": "search_internal_documents",
        "args": {"query": question},
        "id": "call-4",
        "type": "tool_call",
    }
    first_response = AIMessage(content="", tool_calls=[tool_call])
    final_answer = "Ozempic is indicated for type 2 diabetes."
    final_response = AIMessage(content=final_answer)
    evidence = _ok_evidence(question)
    mock_tool = _mock_tool(return_value=evidence)

    model = MagicMock()
    model.invoke.side_effect = [first_response, final_response]

    with patch(
        "services.agent.TOOL_REGISTRY",
        {"search_internal_documents": mock_tool},
    ):
        result = ask_agent(question, model)

    assert result == final_answer
    assert model.invoke.call_count == 2

    second_messages = model.invoke.call_args_list[1].args[0]
    assert isinstance(second_messages[0], SystemMessage)
    assert isinstance(second_messages[1], HumanMessage)
    assert second_messages[1].content == question
    assert second_messages[2] is first_response

    tool_message = second_messages[3]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.tool_call_id == "call-4"
    assert tool_message.name == "search_internal_documents"
    assert json.loads(tool_message.content) == evidence


def test_ask_agent_dailymed_tool_call_returns_final_answer():
    question = "What is Ozempic used for?"
    tool_call = {
        "name": "search_dailymed_evidence",
        "args": {"query": question, "product_name": "Ozempic"},
        "id": "call-5",
        "type": "tool_call",
    }
    first_response = AIMessage(content="", tool_calls=[tool_call])
    final_answer = "Ozempic is indicated for type 2 diabetes."
    final_response = AIMessage(content=final_answer)
    evidence = _ok_dailymed_evidence(question)
    mock_tool = _mock_tool(return_value=evidence)

    model = MagicMock()
    model.invoke.side_effect = [first_response, final_response]

    with patch(
        "services.agent.TOOL_REGISTRY",
        {"search_dailymed_evidence": mock_tool},
    ):
        result = ask_agent(question, model)

    assert result == final_answer
    mock_tool.invoke.assert_called_once_with(
        {"query": question, "product_name": "Ozempic"},
    )
    assert model.invoke.call_count == 2

    second_messages = model.invoke.call_args_list[1].args[0]
    tool_message = second_messages[3]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.name == "search_dailymed_evidence"
    assert json.loads(tool_message.content) == evidence


def test_ask_agent_unknown_tool_returns_safe_tool_error():
    tool_call = {
        "name": "search_web",
        "args": {"query": "Ozempic"},
        "id": "call-6",
        "type": "tool_call",
    }
    first_response = AIMessage(content="", tool_calls=[tool_call])
    model = MagicMock()
    model.invoke.return_value = first_response

    result = ask_agent("What is Ozempic used for?", model)

    assert result == SAFE_TOOL_ERROR
    assert model.invoke.call_count == 1


def test_ask_agent_tool_invoke_exception_returns_safe_tool_error():
    question = "What is Ozempic used for?"
    tool_call = {
        "name": "search_internal_documents",
        "args": {"query": question},
        "id": "call-7",
        "type": "tool_call",
    }
    first_response = AIMessage(content="", tool_calls=[tool_call])
    model = MagicMock()
    model.invoke.return_value = first_response
    mock_tool = _mock_tool(side_effect=RuntimeError("tool boom"))

    with patch(
        "services.agent.TOOL_REGISTRY",
        {"search_internal_documents": mock_tool},
    ):
        result = ask_agent(question, model)

    assert result == SAFE_TOOL_ERROR
    assert model.invoke.call_count == 1
