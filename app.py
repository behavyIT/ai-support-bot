
import os
import json
import sqlite3
import time
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from groq import Groq

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "tickets.db")

app = Flask(__name__, static_folder="static", static_url_path="")
client = Groq(api_key=os.environ["GROQ_API_KEY"])

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """Ты — ассистент первой линии техподдержки внутри компании. Пользователь пишет о технической проблеме свободным текстом (может быть неполно, эмоционально, с несколькими симптомами).
Твоя задача на каждом шаге диалога — вернуть СТРОГО JSON (без markdown, без пояснений) со следующими полями:
{
 "problem_summary": "краткая суть проблемы одним предложением",
 "service": "какой сервис/система затронута",
 "urgency": "high|medium|low",
 "known_facts": ["известные факты из обращения, кратко"],
 "action": "ask_question|propose_step|escalate|resolved",
 "message": "текст, который увидит пользователь: вопрос, шаг решения, сообщение об эскалации или подтверждение решения",
 "escalation_reason": "если action=escalate — почему нельзя решить самостоятельно, иначе null"
}
Правила:
- Задавай ТОЛЬКО те уточняющие вопросы, которые реально нужны для решения именно этой проблемы. Не спрашивай лишнего.
- Если после 1-2 уточнений и/или предложенных шагов проблема не решается, или она явно требует доступа специалиста (сброс паролей на сервере, аппаратная поломка, баг в системе) — используй action=escalate.
- Если пользователь сообщает, что шаг помог и всё работает — action=resolved.
- Если urgency=high (например, дедлайн через несколько минут) — старайся минимизировать число уточняющих вопросов и предлагай самый быстрый вариант или сразу escalate.
- message пиши по-русски, дружелюбно, кратко, без канцелярита.
- Отвечай ТОЛЬКО валидным JSON, один объект, ничего больше."""


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            problem_summary TEXT,
            service TEXT,
            urgency TEXT,
            known_facts TEXT,
            reason TEXT,
            full_log TEXT
        )
    """)
    con.commit()
    con.close()


init_db()


def extract_json(text):
    """Model sometimes wraps JSON in fences or adds stray text; extract the object."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in model output")
    return json.loads(text[start:end + 1])


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Body: {"history": [{"role": "user"|"assistant", "text": "..."}]}
    "assistant" entries hold the raw JSON string from a previous turn.
    Returns the parsed JSON dict describing the next turn.
    """
    body = request.get_json(force=True)
    history = body.get("history", [])

    convo_dump = json.dumps(
        [{"role": h["role"], "content": h["text"]} for h in history],
        ensure_ascii=False,
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            max_tokens=800,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"История диалога (JSON):\n{convo_dump}",
                },
            ],
        )
        raw_text = resp.choices[0].message.content
        parsed = extract_json(raw_text)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(parsed)


@app.route("/api/tickets", methods=["GET"])
def list_tickets():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM tickets ORDER BY created_at DESC").fetchall()
    con.close()
    tickets = []
    for r in rows:
        tickets.append({
            "id": r["id"],
            "createdAt": r["created_at"],
            "problem_summary": r["problem_summary"],
            "service": r["service"],
            "urgency": r["urgency"],
            "known_facts": json.loads(r["known_facts"] or "[]"),
            "reason": r["reason"],
            "full_log": json.loads(r["full_log"] or "[]"),
        })
    return jsonify(tickets)


@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    data = request.get_json(force=True)
    ticket_id = "t_" + uuid.uuid4().hex[:10]
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO tickets (id, created_at, problem_summary, service, urgency, known_facts, reason, full_log) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ticket_id,
            datetime.utcnow().isoformat(),
            data.get("problem_summary"),
            data.get("service"),
            data.get("urgency", "medium"),
            json.dumps(data.get("known_facts", []), ensure_ascii=False),
            data.get("reason"),
            json.dumps(data.get("full_log", []), ensure_ascii=False),
        ),
    )
    con.commit()
    con.close()
    return jsonify({"id": ticket_id})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
