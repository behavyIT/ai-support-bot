# Поддержка, которая не бесит — Python-версия

Flask-бэкенд + один HTML-фронтенд + Groq API. Логика диалога:
приём обращения → разбор проблемы → уточняющие вопросы → шаги решения →
проверка результата → эскалация специалисту с полным контекстом.
Тикеты хранятся в SQLite (`tickets.db`, создаётся автоматически).

## Запуск локально

```bash
cd support_assistant
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

export GROQ_API_KEY=gsk-...     # Windows: set GROQ_API_KEY=...
python app.py
```

Откройте http://localhost:5000

## Структура

```text
support_assistant/
  app.py            # Flask-сервер: /api/chat, /api/tickets
  static/index.html # фронтенд (чат + панель специалиста)
  tickets.db        # создаётся автоматически при первом запуске
  requirements.txt
```

## Как захостить

Любой вариант, где можно запустить Flask-приложение с переменной окружения
`GROQ_API_KEY`:

* **Render / Railway / Fly.io** — просто подключите репозиторий, задайте
  `GROQ_API_KEY` в переменных окружения, команда запуска:
  `gunicorn app:app` (добавьте `gunicorn` в requirements.txt для прода).
* **VPS** — `pip install -r requirements.txt`, затем запустить через
  `gunicorn -w 2 -b 0.0.0.0:5000 app:app` за nginx.
* **Docker** — при желании можно добавить Dockerfile отдельно.

Для прод-режима не используйте `debug=True` и встроенный dev-сервер Flask —
за ним лучше поставить `gunicorn`/`uwsgi`.

## Важно

* `tickets.db` — SQLite-файл, для демо достаточно. Для
  нескольких параллельных пользователей на проде лучше Postgres.
* Модель настроена в `app.py`:
  `MODEL = "openai/gpt-oss-120b"`.
* AI работает через **Groq API**, поэтому для запуска необходима переменная
  окружения `GROQ_API_KEY`.
