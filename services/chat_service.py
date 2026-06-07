"""Evaluation Agent.

The user sends a message. The model decides whether to call the
`evaluate_topic` tool: if the message names a topic id, it runs the existing
evaluation flow and explains the result in plain language; if not, it replies
asking for what is missing.

- milestone 1: `chat` (single message, no history).
- milestone 2: `chat_threaded` (a conversation thread whose history is loaded
  from and persisted to the database around each turn).

Follows Stavros's guidance: OpenAI chat-completions with function calling, a
plain branch on whether a tool was called, and two model calls in the tool
branch (one to get the call, one to turn the tool result into a reply).
"""

import json

from db import get_connection
from repositories import chat_repo
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


def _run_turn(messages):
    """Run one agent turn over a full message list (system + prior turns).

    Returns (reply_text, tool_used, evaluation). The tool-plumbing messages
    (the assistant turn carrying tool_calls and the tool result) are transient
    to this call and are not part of what callers persist.
    """
    client = get_client()
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
        return choice.content, False, None

    call = tool_calls[0]
    args = json.loads(call.function.arguments or "{}")
    result, tool_payload = _run_tool(args.get("topic_id"))

    convo = messages + [
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
        },
        {"role": "tool", "tool_call_id": call.id, "content": json.dumps(tool_payload)},
    ]
    second = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=convo,
        temperature=TEMPERATURE,
    )
    return (
        second.choices[0].message.content,
        True,
        result["evaluation"] if result else None,
    )


def chat(message):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]
    reply, tool_used, evaluation = _run_turn(messages)
    return {"reply": reply, "tool_used": tool_used, "evaluation": evaluation}


def chat_threaded(thread_id, message):
    """Milestone 2: persist the turn and carry the thread's history.

    Saves the incoming user message, loads the full thread from the database,
    runs the turn with that history in the prompt, then persists the reply
    before returning. Only clean user/assistant turns are stored; the tool
    plumbing stays transient.
    """
    conn = get_connection()
    try:
        chat_repo.save_message(conn, thread_id, "user", message)
        conn.commit()

        history = chat_repo.get_messages_by_thread(conn, thread_id)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
            {"role": row["role"], "content": row["content"]} for row in history
        ]

        reply, tool_used, evaluation = _run_turn(messages)

        chat_repo.save_message(conn, thread_id, "assistant", reply or "")
        conn.commit()
    finally:
        conn.close()

    return {
        "thread_id": thread_id,
        "reply": reply,
        "tool_used": tool_used,
        "evaluation": evaluation,
        "message_count": len(history) + 1,
    }
