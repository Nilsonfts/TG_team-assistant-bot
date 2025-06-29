import os
import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from datetime import datetime
import random
from openai import AsyncOpenAI

# --- Загрузка переменных окружения ---
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "196614680"))
CHAT_ID = os.getenv("CHAT_ID")
THREAD_ID = os.getenv("THREAD_ID")
BITRIX_WEBHOOK_URL = os.getenv("BITRIX_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

for var_name, value in [
    ("BOT_TOKEN", BOT_TOKEN),
    ("OPENAI_API_KEY", OPENAI_API_KEY),
    ("CHAT_ID", CHAT_ID),
    ("BITRIX_WEBHOOK_URL", BITRIX_WEBHOOK_URL)
]:
    if not value:
        logger.error(f"{var_name} не задан!")
        raise RuntimeError(f"{var_name} не задан!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# --- Получение данных задачи из Битрикс24 ---
def get_task_data(task_id):
    url = f"{BITRIX_WEBHOOK_URL}tasks.task.get?taskId={task_id}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        return data.get("result", {}).get("task")
    except Exception as e:
        logger.error(f"Ошибка при получении задачи из Bitrix24: {e}")
        return None

# --- Формирование сообщения для Telegram ---
def build_message(type_, task, extra_title=None):
    fio = (task.get("responsible", {}).get("name") or '').strip()
    creator = task.get("creator", {}).get("name", "")
    creator_id = task.get("creator", {}).get("id", "")
    tg_map = {
        'Кристина Нестерова': '@tinatinulya',
        'Евгения Мурзина': '@xquerel',
        'Нил М. ВМ ЕВГ': '@nilfts',
        'Екатерина Белоногова': '@ek_belonogova',
        'Олег С. АРТ РВБ СПБ ГРИБ': '@olegstate'
    }
    personalized_phrases = {
        'Кристина Нестерова': [
            'держи, ты же у нас любишь всё контролировать 🧐.', 'KPI сам себя не выполнит. Приступай.'
        ],
        'Евгения Мурзина': [
            'маленькая задача для большого специалиста. ✨', 'тебе поручено нести знамя милоты и эффективности.'
        ],
        'Нил М. ВМ ЕВГ': [
            'маэстро, ваш холст готов. Ждем шедевр. 🎨', 'тут нужен твой нестандартный подход. Думай!'
        ],
        'Екатерина Белоногова': [
            'Figma плачет, ждет свою королеву. 👑', 'нужно сделать красиво. Впрочем, как обычно. 💅'
        ],
        'Олег С. АРТ РВБ СПБ ГРИБ': [
            'Арт-директор, есть возможность поймать вайб. 🤙', 'тут дельце, которое требует твоего фирменного стиля. 😎'
        ]
    }
    generic_phrases = [
        'у вас тут новая задачка!', 'для тебя обнаружена новая задача!', 'тебе выпало новое задание.', 'время немного поработать.'
    ]
    random_endings = [
        '☎️ Если не сделаешь — позвоню твоей маме! 🤫',
        'P.S. Мой кот будет разочарован, если ты провалишь дедлайн. 🐈',
        'За выполненную в срок задачу — печенька. 🍪 Может быть.',
        'Да пребудет с тобой сила... и кофеин. ☕'
    ]
    tg_tag = tg_map.get(fio, fio)
    deadline = task.get("deadline")
    if deadline:
        try:
            deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00')).strftime('%d.%m.%Y %H:%M')
        except Exception:
            pass
    else:
        deadline = "не указан"
    desc = task.get("description") or '-'
    title = extra_title or task.get('title', '')

    phrase_list = personalized_phrases.get(fio, generic_phrases)
    random_phrase = random.choice(phrase_list)
    final_ending = f"\n\n{random.choice(random_endings)}"

    opening_line = f"{tg_tag}, {random_phrase}"
    core_message = (
        f"🔢 ID: {task.get('id')}\n"
        f"🧾 Задача: {title}\n"
        f"📝 Описание: {desc}\n"
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

# --- Обработчик сообщений Telegram: ChatGPT в личку ---
@dp.message()
async def handle_message(message: types.Message):
    if message.chat.type == "private":
        user_text = message.text.strip() if message.text else ""
        if not user_text:
            await message.reply("Пожалуйста, напиши свой вопрос.")
            return
        try:
            response = await openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты дружелюбный ассистент, отвечай по-русски и понятно."},
                    {"role": "user", "content": user_text}
                ],
                max_tokens=600,
                temperature=0.9,
            )
            answer = response.choices[0].message.content.strip()
            await message.reply(answer)
        except Exception as e:
            await message.reply(f"Ошибка при обращении к AI: {e}")

# --- FastAPI APP ---
app = FastAPI()

@app.post("/bitrix-webhook")
async def bitrix_webhook(request: Request):
    # Универсальный парсер: пробуем JSON → form → query
    try:
        try:
            data = await request.json()
            logger.info(f"Webhook пришел как JSON: {data}")
        except Exception:
            form = await request.form()
            if form:
                data = dict(form)
                logger.info(f"Webhook пришел как form-data: {data}")
            else:
                data = dict(request.query_params)
                logger.info(f"Webhook пришел как query: {data}")
    except Exception as e:
        logger.error(f"Ошибка разбора данных: {e}")
        return {"ok": False, "error": "Failed to parse data"}

    task_id = str(data.get("id") or data.get("task_id") or data.get("task", {}).get("id"))
    type_ = data.get("type") or "new_task"
    extra_title = data.get("title")

    if not task_id or "{{" in task_id:
        logger.warning("No valid task id")
        return {"ok": False, "error": "No valid task id"}
    try:
        task = get_task_data(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
            return {"ok": False, "error": "Task not found"}
        message = build_message(type_, task, extra_title=extra_title)
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
        logger.error(f"Ошибка при обработке webhook: {e}")
        return {"ok": False, "error": str(e)}

@app.get("/")
async def root():
    return {"ok": True}

# --- Запуск aiogram вместе с FastAPI (через lifespan) ---
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(dp.start_polling(bot))
