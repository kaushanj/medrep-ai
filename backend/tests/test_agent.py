"""Unit tests for services.agent.ask_agent (mocked Bedrock + tool)."""

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from services.agent import (
    AGENT_SYSTEM_PROMPT,
    SAFE_NO_RESULTS,
    SAFE_TOOL_ERROR,
    TOOL_REGISTRY,
    ask_agent,
)


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


def test_agent_exposes_only_internal_documents_tool():
    assert list(TOOL_REGISTRY.keys()) == ["search_internal_documents"]
    assert "dailymed" not in AGENT_SYSTEM_PROMPT.lower()
    assert "search_dailymed_evidence" not in AGENT_SYSTEM_PROMPT


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

    assert result["answer"] == final_answer
    mock_tool.invoke.assert_called_once_with({"query": question})
    assert model.invoke.call_count == 2


def test_ask_agent_multi_step_compare_invokes_tool_twice():
    question = "Compare Ozempic and Mounjaro indications"
    first_tool_call = {
        "name": "search_internal_documents",
        "args": {"query": "Ozempic indications"},
        "id": "call-a",
        "type": "tool_call",
    }
    second_tool_call = {
        "name": "search_internal_documents",
        "args": {"query": "Mounjaro indications"},
        "id": "call-b",
        "type": "tool_call",
    }
    first_response = AIMessage(content="", tool_calls=[first_tool_call])
    second_response = AIMessage(content="", tool_calls=[second_tool_call])
    final_answer = "Both are indicated for type 2 diabetes."
    final_response = AIMessage(content=final_answer)

    ozempic_evidence = _ok_evidence("Ozempic indications")
    mounjaro_evidence = {
        "status": "ok",
        "source": "internal_documents",
        "query": "Mounjaro indications",
        "results": [
            {
                "text": "Mounjaro is indicated for type 2 diabetes.",
                "score": 0.9,
                "metadata": {"product_name": "Mounjaro"},
            }
        ],
        "error": None,
    }
    mock_tool = _mock_tool(side_effect=[ozempic_evidence, mounjaro_evidence])

    model = MagicMock()
    model.invoke.side_effect = [first_response, second_response, final_response]

    with patch(
        "services.agent.TOOL_REGISTRY",
        {"search_internal_documents": mock_tool},
    ):
        result = ask_agent(question, model)

    assert result["answer"] == final_answer
    assert mock_tool.invoke.call_count == 2
    mock_tool.invoke.assert_any_call({"query": "Ozempic indications"})
    mock_tool.invoke.assert_any_call({"query": "Mounjaro indications"})
    assert model.invoke.call_count == 3


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

    assert result["answer"] == SAFE_NO_RESULTS
    mock_tool.invoke.assert_not_called()
    assert model.invoke.call_count == 1


def test_ask_agent_no_results_continues_then_safe_no_results():
    question = "What is UnknownDrug used for?"
    tool_call = {
        "name": "search_internal_documents",
        "args": {"query": question},
        "id": "call-2",
        "type": "tool_call",
    }
    first_response = AIMessage(content="", tool_calls=[tool_call])
    second_response = AIMessage(content="UnknownDrug is a medicine.")
    model = MagicMock()
    model.invoke.side_effect = [first_response, second_response]

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

    assert result["answer"] == SAFE_NO_RESULTS
    assert model.invoke.call_count == 2


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

    assert result["answer"] == SAFE_TOOL_ERROR
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

    assert result["answer"] == final_answer
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

    assert result["answer"] == SAFE_TOOL_ERROR
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

    assert result["answer"] == SAFE_TOOL_ERROR
    assert model.invoke.call_count == 1
