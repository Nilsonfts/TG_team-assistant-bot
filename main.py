import os
import sys
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import openai

# === Конфиг ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BITRIX_WEBHOOK_URL = "https://nebar.bitrix24.ru/rest/1856/5damz451340uegoc/"
GROUP_ID = int(os.getenv("CHAT_ID"))      # ID чата/группы для задач из Bitrix24
THREAD_ID = int(os.getenv("THREAD_ID"))   # ID ветки (топика)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OWNER_ID = 196614680                      # твой Telegram user_id

# --- Инициализация клиентов ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# --- Bitrix24: Получить задачи ---
def get_tasks_list(limit=5):
    url = BITRIX_WEBHOOK_URL + "tasks.task.list"
    params = {
        "select": ["ID", "TITLE", "DESCRIPTION", "RESPONSIBLE_NAME", "CREATED_BY", "DEADLINE"],
        "order": {"DEADLINE": "asc"},
        "filter": {}
    }
    resp = requests.get(url, params=params)
    data = resp.json()
    if "result" in data and "tasks" in data["result"]:
        return data["result"]["tasks"][:limit]
    return []

# --- Проверки ---
def is_private_owner(message: types.Message):
    return message.chat.type == "private" and message.from_user.id == OWNER_ID

def is_work_thread(message: types.Message):
    return (
        message.chat.type in ("supergroup", "group")
        and message.chat.id == GROUP_ID
        and (message.message_thread_id == THREAD_ID if message.message_thread_id else False)
    )

# --- Команда /b24tasks ---
@dp.message(Command("b24tasks"))
async def show_b24tasks(message: types.Message):
    if not (is_private_owner(message) or is_work_thread(message)):
        return
    tasks = get_tasks_list(limit=5)
    if not tasks:
        await message.reply("Нет задач в Битрикс24.")
        return
    msg = "<b>Топ задач из Битрикс24:</b>\n"
    for task in tasks:
        t = task["task"]
        title = t.get("title", "Без названия")
        tid = t.get("id", "-")
        responsible = t.get("responsible_name", "-")
        deadline = t.get("deadline", "не указан")
        msg += f"\n<b>{title}</b>\nID: <code>{tid}</code>\nОтветственный: {responsible}\nДедлайн: {deadline}\n"
        msg += f'<a href="https://nebar.bitrix24.ru/company/personal/user/{t.get("created_by", "")}/tasks/task/view/{tid}/">Открыть задачу</a>\n'
    await message.reply(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# --- GPT ассистент ---
@dp.message(Command("gpt"))
async def gpt_answer(message: types.Message):
    if not (is_private_owner(message) or is_work_thread(message)):
        return
    user_text = message.text.replace("/gpt", "", 1).strip()
    if not user_text:
        await message.reply("Пожалуйста, напиши свой вопрос после команды /gpt")
        return
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты дружелюбный Telegram-ассистент, отвечай кратко и по делу."},
                {"role": "user", "content": user_text}
            ],
            max_tokens=500,
            temperature=0.7,
        )
        answer = response.choices[0].message.content
        await message.answer(answer)
    except Exception as e:
        await message.reply(f"Ошибка при обращении к AI: {e}")

# --- Общий фоллбек ---
@dp.message()
async def fallback(message: types.Message):
    if is_private_owner(message) or is_work_thread(message):
        await message.reply("Если хочешь спросить у GPT, используй /gpt [текст]")

# --- Webhook для Bitrix24 (пушит задачи в группу/топик) ---
@app.post("/bitrix-webhook")
async def bitrix_webhook(request: Request):
    try:
        data = await request.json()
        task = (
            data.get("task") or
            data.get("data", {}).get("TASK") or
            data
        )
        if not task:
            return {"ok": False, "error": "No task data"}
        title = task.get("title", "Без названия")
        desc = task.get("description", "-")
        task_id = task.get("id", "—")
        deadline = task.get("deadline", "не указан")
        responsible = (
            task.get("responsible", {}).get("name")
            if isinstance(task.get("responsible"), dict)
            else task.get("responsible", "-")
        )
        creator = (
            task.get("creator", {}).get("name")
            if isinstance(task.get("creator"), dict)
            else task.get("creator", "-")
        )
        creator_id = (
            task.get("creator", {}).get("id")
            if isinstance(task.get("creator"), dict)
            else ""
        )
        link = f"https://nebar.bitrix24.ru/company/personal/user/{creator_id}/tasks/task/view/{task_id}/"
        message_text = (
            f"🆕 <b>Новая задача из Bitrix24</b>\n"
            f"<b>Название:</b> {title}\n"
            f"<b>Описание:</b> {desc}\n"
            f"<b>Исполнитель:</b> {responsible}\n"
            f"<b>Постановщик:</b> {creator}\n"
            f"<b>Дедлайн:</b> {deadline}\n"
            f'<a href="{link}">Открыть задачу в Битрикс24</a>'
        )
        send_kwargs = dict(
            chat_id=GROUP_ID,
            text=message_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        if THREAD_ID:
            send_kwargs["message_thread_id"] = THREAD_ID
        asyncio.create_task(bot.send_message(**send_kwargs))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# --- Запуск aiogram и FastAPI ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import uvicorn
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    uvicorn.run(app, host="0.0.0.0", port=8000)
