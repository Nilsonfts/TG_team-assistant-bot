import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

# Настройки (подставь свои значения)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ТВОЙ_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "ID_ТВОЕГО_ЧАТА")  # чат куда слать задачи
MY_TELEGRAM_ID = os.getenv("MY_TELEGRAM_ID", "ТВОЙ_ЛИЧНЫЙ_ID")      # тебе лично для ошибок и логов

# Функция отправки сообщений в Telegram
def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data)
        return resp.ok
    except Exception as e:
        print(f"Ошибка при отправке в Telegram: {e}")
        return False

# Универсальный обработчик вебхука
@app.api_route("/bitrix-webhook", methods=["GET", "POST"])
async def bitrix_webhook(request: Request):
    # Получаем данные из разных источников
    data = {}
    # JSON
    try:
        data = await request.json()
    except Exception:
        pass
    # form-data
    if not data:
        try:
            form = await request.form()
            data = dict(form)
        except Exception:
            pass
    # query
    if not data:
        data = dict(request.query_params)

    # Логируем всё себе
    print("Bitrix webhook:", data)
    send_telegram_message(MY_TELEGRAM_ID, f"📩 Webhook получен:\n<code>{data}</code>")

    # Пытаемся собрать сообщение для чата задач (можешь доработать по нужным полям)
    # Пример для задачи: id, type, title и др.
    task_id = data.get("id") or data.get("ID") or "-"
    task_type = data.get("type") or data.get("TYPE") or "-"
    task_title = data.get("title") or data.get("TITLE") or "Без названия"

    # Формируем текст
    msg = f"🆕 Новая задача из Bitrix24!\n"
    msg += f"ID: <b>{task_id}</b>\n"
    msg += f"Тип: <b>{task_type}</b>\n"
    msg += f"Название: <b>{task_title}</b>\n"
    msg += f"Данные: <code>{data}</code>"

    # Шлём в чат задач
    ok = send_telegram_message(TELEGRAM_CHAT_ID, msg)
    if not ok:
        send_telegram_message(MY_TELEGRAM_ID, "❗️Ошибка при отправке задачи в рабочий чат!")

    return JSONResponse({"status": "ok"})

# Главная страница для тестов
@app.get("/")
async def root():
    return {"message": "Бот работает. Вебхук для Bitrix24: /bitrix-webhook"}
