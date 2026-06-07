"""Evaluation Agent, milestone 1: a single-message chat endpoint.

The user sends one message. The model decides whether to call the
`evaluate_topic` tool: if the message names a topic id, it runs the existing
evaluation flow and explains the result in plain language; if not, it replies
asking for what is missing. No conversation history yet (that is milestone 2).

Follows Stavros's guidance: OpenAI chat-completions with function calling, a
plain branch on whether a tool was called, and two model calls in the tool
branch (one to get the call, one to turn the tool result into a reply).
"""

import json

from services import evaluation_service
from services.openai_client import get_client
from services.topic_service import ValidationError

CHAT_MODEL = "gpt-4o-mini"
TEMPERATURE = 0.0

SYSTEM_PROMPT = (
    "You are the assistant for a Review Intelligence Tool. You can evaluate the "
    "customer reviews stored under a topic. When the user gives a topic id, call "
    "the evaluate_topic tool with that id. If no topic id is provided, do not "
    "guess one: ask the user to provide the topic id. After an evaluation, give a "
    "short, plain-language summary of what the reviews say."
)

EVALUATE_TOOL = {
    "type": "function",
    "function": {
        "name": "evaluate_topic",
        "description": (
            "Run the AI evaluation over the reviews stored under a topic, "
            "identified by its integer id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic_id": {
                    "type": "integer",
                    "description": "The integer id of the topic to evaluate.",
                }
            },
            "required": ["topic_id"],
            "additionalProperties": False,
        },
    },
}


def _run_tool(topic_id):
    """Invoke the evaluation flow and shape a result the model can summarise."""
    try:
        result = evaluation_service.evaluate_topic(topic_id)
    except ValidationError as e:
        return None, {"ok": False, "error": str(e)}
    payload = {
        "ok": True,
        "topic_name": result["topic_name"],
        "review_count": result["review_count"],
        "evaluation": result["evaluation"],
    }
    return result, payload


def chat(message):
    client = get_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    first = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        tools=[EVALUATE_TOOL],
        tool_choice="auto",
        temperature=TEMPERATURE,
    )
    choice = first.choices[0].message
    tool_calls = choice.tool_calls or []

    if not tool_calls:
        return {"reply": choice.content, "tool_used": False, "evaluation": None}

    call = tool_calls[0]
    args = json.loads(call.function.arguments or "{}")
    result, tool_payload = _run_tool(args.get("topic_id"))

    messages.append(
        {
            "role": "assistant",
            "content": choice.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
            ],
        }
    )
    messages.append(
        {
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(tool_payload),
        }
    )

    second = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=TEMPERATURE,
    )
    return {
        "reply": second.choices[0].message.content,
        "tool_used": True,
        "evaluation": result["evaluation"] if result else None,
    }
