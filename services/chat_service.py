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
from repositories import chat_repo, topic_repo
from services import evaluation_service
from services.openai_client import get_client
from services.topic_service import ValidationError

CHAT_MODEL = "gpt-4o-mini"
TEMPERATURE = 0.0
MAX_TOOL_ITERS = 5

SYSTEM_PROMPT = (
    "You are the assistant for a Review Intelligence Tool. You evaluate the "
    "customer reviews stored under a topic.\n"
    "- If the user gives a topic id, call evaluate_topic with that id.\n"
    "- If the user names a topic (a company or product) instead of an id, call "
    "find_topics_by_name to look it up. The name may be partial or misspelled.\n"
    "  - No matches: say so and ask the user to rephrase or add a topic.\n"
    "  - Several matches: list them and ask which one.\n"
    "  - One match: always confirm it with the user and wait for their reply "
    "before evaluating, even when the user's message sounded like a request to "
    "analyze (e.g. reply 'I found \"X\". Evaluate it?' and stop there for this turn).\n"
    "- Once the user has confirmed a topic (e.g. said yes) or gave an id directly, "
    "evaluate it now and do NOT ask again. A topic id is valid from the user's "
    "direct input, a find_topics_by_name result in the current turn, or a verified "
    "topic given in a conversation-state note in this prompt. If a conversation-state "
    "note names a verified topic id, reuse that id directly. Otherwise, if the "
    "confirmed topic was found only in an earlier turn with no such note, silently "
    "call find_topics_by_name again to re-resolve its id, then call evaluate_topic. "
    "Never invent an id.\n"
    "- After an evaluation, give a short, plain-language summary of what the reviews say."
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

FIND_TOPICS_TOOL = {
    "type": "function",
    "function": {
        "name": "find_topics_by_name",
        "description": (
            "Look up topics whose name matches the given text (partial or "
            "approximate allowed). Returns candidate topics with their ids so the "
            "right one can be confirmed before evaluating."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The topic name or fragment to search for.",
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
}

TOOLS = [EVALUATE_TOOL, FIND_TOPICS_TOOL]


def _run_evaluate(topic_id):
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


def _find_topics(name):
    """Fuzzy-look up topics by name for the agent to confirm."""
    if not isinstance(name, str) or not name.strip():
        return {"candidates": []}
    conn = get_connection()
    try:
        rows = topic_repo.search_topics_by_name(conn, name.strip())
    finally:
        conn.close()
    return {
        "candidates": [
            {"id": r["id"], "name": r["name"], "category": r["category"]}
            for r in rows
        ]
    }


def _dispatch_tool(name, args):
    """Run one tool call and return the JSON-string result, any evaluation, and
    the topic resolved this turn (id + name): the evaluated topic, or a single
    name match. Persisting a single match lets a follow-up "yes" evaluate that
    exact id instead of re-resolving by name and risking the wrong topic."""
    if name == "evaluate_topic":
        topic_id = args.get("topic_id")
        result, payload = _run_evaluate(topic_id)
        evaluation = result["evaluation"] if result else None
        resolved = {"id": topic_id, "name": result["topic_name"]} if result else None
        return json.dumps(payload), evaluation, resolved
    if name == "find_topics_by_name":
        res = _find_topics(args.get("name"))
        cands = res.get("candidates", [])
        resolved = {"id": cands[0]["id"], "name": cands[0]["name"]} if len(cands) == 1 else None
        return json.dumps(res), None, resolved
    return json.dumps({"error": f"unknown tool: {name}"}), None, None


def _run_turn(messages):
    """Run one agent turn over a full message list (system + prior turns).

    Loops: the model may call tools (look up a topic, then evaluate it), and we
    feed each tool result back until it returns a plain-text reply. Returns
    (reply_text, tool_used, evaluation, verified_topic). verified_topic is the
    {id, name} of the last topic evaluated this turn, or None. The tool-plumbing
    messages are transient to this call and are not part of what callers persist.
    """
    client = get_client()
    convo = list(messages)
    tool_used = False
    evaluation = None
    verified_topic = None

    for _ in range(MAX_TOOL_ITERS):
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=convo,
            tools=TOOLS,
            tool_choice="auto",
            temperature=TEMPERATURE,
        )
        choice = response.choices[0].message
        tool_calls = choice.tool_calls or []

        if not tool_calls:
            return choice.content, tool_used, evaluation, verified_topic

        tool_used = True
        convo.append(
            {
                "role": "assistant",
                "content": choice.content,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {
                            "name": c.function.name,
                            "arguments": c.function.arguments,
                        },
                    }
                    for c in tool_calls
                ],
            }
        )
        for c in tool_calls:
            args = json.loads(c.function.arguments or "{}")
            content, this_eval, evaluated = _dispatch_tool(c.function.name, args)
            if this_eval is not None:
                evaluation = this_eval
            if evaluated is not None:
                verified_topic = evaluated
            convo.append({"role": "tool", "tool_call_id": c.id, "content": content})

    # Safety net: tool loop did not converge; force a plain reply without tools.
    final = client.chat.completions.create(
        model=CHAT_MODEL, messages=convo, temperature=TEMPERATURE
    )
    return final.choices[0].message.content, tool_used, evaluation, verified_topic


def chat(message):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]
    reply, tool_used, evaluation, _ = _run_turn(messages)
    return {"reply": reply, "tool_used": tool_used, "evaluation": evaluation}


def _verified_topic_note(thread):
    """Build a conversation-state system message for the topic under discussion
    on this thread, or None if there is none yet."""
    if not thread or thread["verified_topic_id"] is None:
        return None
    topic_id = thread["verified_topic_id"]
    name = thread["verified_topic_name"]
    return {
        "role": "system",
        "content": (
            f'Conversation state: the topic currently under discussion in this thread '
            f'is id {topic_id} ("{name}"). If the user confirms evaluating it or refers '
            f'to it again (e.g. "yes", "that one", "it", "again"), call evaluate_topic '
            f"with id {topic_id} directly. Do NOT call find_topics_by_name to re-resolve "
            "it. Only look up a topic by name if the user clearly names a different one."
        ),
    }


def chat_threaded(thread_id, message):
    """Milestone 2 + verified-topic persistence: carry the thread's history and
    its verified topic across turns.

    Saves the incoming user message, loads the full thread and its verified-topic
    state from the database, runs the turn with both in the prompt, then persists
    the reply (and any newly verified topic) before returning. Only clean
    user/assistant turns are stored; the tool plumbing stays transient.
    """
    conn = get_connection()
    try:
        chat_repo.save_message(conn, thread_id, "user", message)
        conn.commit()

        thread = chat_repo.get_thread(conn, thread_id)
        history = chat_repo.get_messages_by_thread(conn, thread_id)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        note = _verified_topic_note(thread)
        if note is not None:
            messages.append(note)
        messages += [
            {"role": row["role"], "content": row["content"]} for row in history
        ]

        reply, tool_used, evaluation, verified_topic = _run_turn(messages)

        chat_repo.save_message(conn, thread_id, "assistant", reply or "")
        if verified_topic is not None:
            chat_repo.set_verified_topic(
                conn, thread_id, verified_topic["id"], verified_topic["name"]
            )
        conn.commit()
    finally:
        conn.close()

    current = verified_topic["id"] if verified_topic else (
        thread["verified_topic_id"] if thread else None
    )
    return {
        "thread_id": thread_id,
        "reply": reply,
        "tool_used": tool_used,
        "evaluation": evaluation,
        "message_count": len(history) + 1,
        "verified_topic_id": current,
    }
