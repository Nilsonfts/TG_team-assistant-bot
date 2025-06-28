import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import openai

# --- Загрузка переменных окружения ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
THREAD_ID = os.getenv("THREAD_ID")
THREAD_ID = int(THREAD_ID) if THREAD_ID and THREAD_ID.isdigit() else None
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

BITRIX_WEBHOOK_URL = "https://nebar.bitrix24.ru/rest/1856/5damz451340uegoc/"

# --- Инициализация клиентов ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# --- Bitrix24: Функция для получения задач ---
def get_tasks_list(limit=5):
    url = BITRIX_WEBHOOK_URL + "tasks.task.list"
    params = {
        "select": ["ID", "TITLE", "DESCRIPTION", "RESPONSIBLE_NAME", "CREATED_BY", "DEADLINE"],
        "order": {"DEADLINE": "asc"},
        "filter": {}  # Можно добавить фильтры, например, по ответственному
    }
    resp = requests.get(url, params=params)
    data = resp.json()
    if "result" in data and "tasks" in data["result"]:
        return data["result"]["tasks"][:limit]
    return []

# --- Команда /b24tasks ---
@dp.message(Command("b24tasks"))
async def show_b24tasks(message: types.Message):
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
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я ассистент. Используй /gpt [текст], чтобы поговорить с GPT. Или просто напиши мне.")

@dp.message(Command("gpt"))
async def gpt_answer(message: types.Message):
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

@dp.message()
async def fallback(message: types.Message):
    await message.reply("Если хочешь спросить у GPT, используй /gpt [текст]")

# --- Webhook для Bitrix24 ---
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
            chat_id=CHAT_ID,
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
