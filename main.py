import os
import sys
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import requests
import openai

# --- Load environment variables ---
load_dotenv()

def get_env_str(name, required=True, default=None):
    val = os.getenv(name)
    if val is None or val == "":
        if required:
            print(f"Environment variable {name} is not set! Please set it in your Railway/Heroku/.env")
            sys.exit(1)
        return default
    return val

BOT_TOKEN = get_env_str("BOT_TOKEN")
OPENAI_API_KEY = get_env_str("OPENAI_API_KEY")
CHAT_ID = get_env_str("CHAT_ID", required=False, default=None)
THREAD_ID = get_env_str("THREAD_ID", required=False, default=None)
OWNER_ID = int(get_env_str("OWNER_ID", required=False, default="196614680"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

BITRIX_WEBHOOK_URL = "https://nebar.bitrix24.ru/rest/1856/5damz451340uegoc/"

def get_tasks_list(limit=5):
    url = BITRIX_WEBHOOK_URL + "tasks.task.list"
    params = {
        "select": ["ID", "TITLE", "DESCRIPTION", "RESPONSIBLE_NAME", "CREATED_BY", "DEADLINE"],
        "order": {"DEADLINE": "asc"},
        "filter": {}
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if "result" in data and "tasks" in data["result"]:
            return data["result"]["tasks"][:limit]
    except Exception as e:
        print("Ошибка при получении задач Bitrix24:", e)
    return []

def is_private(message: types.Message):
    return message.chat.type == "private"

def is_group_thread(message: types.Message):
    try:
        return (
            message.chat.type in ("supergroup", "group")
            and CHAT_ID is not None
            and str(message.chat.id) == str(CHAT_ID)
            and (not THREAD_ID or str(message.message_thread_id) == str(THREAD_ID))
        )
    except Exception:
        return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n"
        f"Твой user ID: <code>{message.from_user.id}</code>\n"
        f"Текущий chat ID: <code>{message.chat.id}</code>", parse_mode=ParseMode.HTML
    )

@dp.message(Command("b24tasks"))
async def show_b24tasks(message: types.Message):
    if not (is_private(message) or is_group_thread(message)):
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

@dp.message(Command("gpt"))
async def gpt_answer(message: types.Message):
    if not (is_private(message) or is_group_thread(message)):
        return
    user_text = message.text.replace("/gpt", "", 1).strip()
    if not user_text:
        await message.reply("Пожалуйста, напиши свой вопрос после команды /gpt")
        return
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты — дружелюбный Telegram-ассистент, отвечай кратко и по делу."},
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
    if is_private(message) or is_group_thread(message):
        await message.reply("Используй /gpt [текст], чтобы спросить у GPT\nили /b24tasks — чтобы получить задачи из Bitrix24.")

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
        if CHAT_ID:
            send_kwargs = dict(
                chat_id=int(CHAT_ID),
                text=message_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            if THREAD_ID:
                send_kwargs["message_thread_id"] = int(THREAD_ID)
            asyncio.create_task(bot.send_message(**send_kwargs))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import uvicorn
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    uvicorn.run(app, host="0.0.0.0", port=8000)
