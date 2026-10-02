"""Unit tests for services.agent.ask_agent (mocked Bedrock + tool)."""

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from services.agent import (
    SAFE_NO_RESULTS,
    SAFE_TOOL_ERROR,
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

    model = MagicMock()
    model.invoke.side_effect = [first_response, final_response]

    with patch("services.agent.search_internal_documents_tool") as mock_tool:
        mock_tool.invoke.return_value = _ok_evidence(question)
        result = ask_agent(question, model)

    assert result == final_answer
    mock_tool.invoke.assert_called_once_with({"query": question})
    assert model.invoke.call_count == 2


def test_ask_agent_no_tool_call_returns_safe_no_results():
    first_response = AIMessage(content="I know about Ozempic.")
    model = MagicMock()
    model.invoke.return_value = first_response

    with patch("services.agent.search_internal_documents_tool") as mock_tool:
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

    with patch("services.agent.search_internal_documents_tool") as mock_tool:
        mock_tool.invoke.return_value = evidence
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

    with patch("services.agent.search_internal_documents_tool") as mock_tool:
        mock_tool.invoke.return_value = evidence
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

    model = MagicMock()
    model.invoke.side_effect = [first_response, final_response]

    with patch("services.agent.search_internal_documents_tool") as mock_tool:
        mock_tool.invoke.return_value = evidence
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
