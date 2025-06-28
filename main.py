import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request
import openai
import uvicorn
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_ID = os.getenv("CHAT_ID")
THREAD_ID = os.getenv("THREAD_ID")
BITRIX_WEBHOOK_URL = os.getenv("BITRIX_WEBHOOK_URL", "https://nebar.bitrix24.ru/rest/1856/5damz451340uegoc/")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан!")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не задан!")
if not CHAT_ID:
    raise RuntimeError("CHAT_ID не задан!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

def is_private(message: types.Message):
    return message.chat.type == "private"

@dp.message()
async def handle_message(message: types.Message):
    if is_private(message):
        user_text = message.text.strip()
        if not user_text:
            await message.reply("Пожалуйста, напиши свой вопрос.")
            return
        try:
            resp = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Ты дружелюбный ассистент ChatGPT в Telegram, отвечай понятно и по делу."},
                    {"role": "user", "content": user_text}
                ],
                max_tokens=700,
                temperature=0.7,
            )
            answer = resp.choices[0].message.content
            await message.reply(answer)
        except Exception as e:
            await message.reply(f"Ошибка при обращении к AI: {e}")

# --- Креативные фразы и маппинги (сокращенно, для примера, добавь остальные по аналогии) ---
tg_map = {
    'Кристина Нестерова': '@tinatinulya',
    'Евгения Мурзина': '@xquerel',
    'Нил М. ВМ ЕВГ': '@nilfts',
    'Екатерина Белоногова': '@ek_belonogova',
    'Олег С. АРТ РВБ СПБ ГРИБ': '@olegstate'
}
personalized_phrases = {
    'Кристина Нестерова': ['держи, ты же у нас любишь всё контролировать 🧐.', 'KPI сам себя не выполнит. Приступай.'],
    'Евгения Мурзина': ['маленькая задача для большого специалиста. ✨'],
    'Нил М. ВМ ЕВГ': ['маэстро, ваш холст готов. Ждем шедевр. 🎨'],
    'Екатерина Белоногова': ['Figma плачет, ждет свою королеву. 👑'],
    'Олег С. АРТ РВБ СПБ ГРИБ': ['Арт-директор, есть возможность поймать вайб. 🤙']
}
generic_phrases = ['у вас тут новая задачка!', 'для тебя обнаружена новая задача!']

# ... аналогично для personalizedClosedPhrases и других фраз

random_endings = [
    '☎️ Если не сделаешь — позвоню твоей маме! 🤫',
    'P.S. Мой кот будет разочарован, если ты провалишь дедлайн. 🐈'
]

def get_task_data(task_id):
    url = f"{BITRIX_WEBHOOK_URL}tasks.task.get?taskId={task_id}"
    resp = requests.get(url, timeout=10)
    data = resp.json()
    return data.get("result", {}).get("task")

def build_message(type_, task):
    fio = (task.get("responsible", {}).get("name") or '').strip()
    creator = task.get("creator", {}).get("name", "")
    creator_id = task.get("creator", {}).get("id", "")
    tg_tag = tg_map.get(fio, fio)
    deadline = task.get("deadline")
    if deadline:
        try:
            deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00')).strftime('%d.%m.%Y %H:%M')
        except Exception:
            pass
    else:
        deadline = "не указан"

    opening_line = ""
    core_message = ""
    final_ending = f"\n\n{random_endings[0]}"
    # Только тип "new_task" реализован для примера, добавляй reminder/closed по аналогии
    if type_ == 'new_task':
        phrase_list = personalized_phrases.get(fio, generic_phrases)
        random_phrase = phrase_list[0]  # random.choice можно подключить
        opening_line = f"{tg_tag}, {random_phrase}"
        core_message = (
            f"🔢 ID: {task.get('id')}\n"
            f"🧾 Задача: {task.get('title')}\n"
            f"📝 Описание: {task.get('description') or '-'}\n"
            f"👤 Исполнитель: {fio}\n"
            f"🧑‍💼 Постановщик: {creator}\n"
            f"📁 Проект: {task.get('group', {}).get('name', '-')}\n"
            f"📅 Срок: {deadline}"
        )
    message = (
        f"{opening_line}\n\n"
        f"{core_message}\n\n"
        f'<a href="https://nebar.bitrix24.ru/company/personal/user/{creator_id}/tasks/task/view/{task.get("id")}/">ССЫЛКА НА ЗАДАЧУ</a>'
        f'{final_ending}'
    )
    return message

@app.post("/bitrix-webhook")
async def bitrix_webhook(request: Request):
    data = await request.json()
    task_id = str(data.get("id") or data.get("task_id") or data.get("task", {}).get("id"))
    type_ = data.get("type") or "new_task"
    if not task_id or "{{" in task_id:
        return {"ok": False, "error": "No valid task id"}
    try:
        task = get_task_data(task_id)
        if not task:
            return {"ok": False, "error": "Task not found"}
        message = build_message(type_, task)
        send_kwargs = dict(
            chat_id=int(CHAT_ID),
            text=message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        if THREAD_ID:
            send_kwargs["message_thread_id"] = int(THREAD_ID)
        asyncio.create_task(bot.send_message(**send_kwargs))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def run_all():
    asyncio.create_task(dp.start_polling(bot))
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(run_all())
