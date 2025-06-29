import os
import asyncio
import logging
import requests
from datetime import datetime
import random

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request
from openai import AsyncOpenAI

# --- НАСТРОЙКИ И ЛОГИ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
THREAD_ID = os.getenv("THREAD_ID")
BITRIX_WEBHOOK_URL = os.getenv("BITRIX_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "196614680"))

for name, value in [
    ("BOT_TOKEN", BOT_TOKEN),
    ("CHAT_ID", CHAT_ID),
    ("BITRIX_WEBHOOK_URL", BITRIX_WEBHOOK_URL),
    ("OPENAI_API_KEY", OPENAI_API_KEY)
]:
    if not value:
        logger.error(f"{name} не задан!")
        raise RuntimeError(f"{name} не задан!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
app = FastAPI()

# --- УНИВЕРСАЛЬНЫЙ ПАРСЕР ТЕЛА ЗАПРОСА ---
async def extract_request_data(request: Request):
    # 1. Попытка как JSON
    try:
        data = await request.json()
        logger.info(f"JSON DATA: {data}")
        return data
    except Exception:
        pass
    # 2. Попытка как form-urlencoded
    try:
        form = await request.form()
        data = dict(form)
        logger.info(f"FORM DATA: {data}")
        return data
    except Exception:
        pass
    # 3. Не удалось — возвращаем пустое
    logger.error("Не удалось распарсить тело запроса!")
    return {}

# --- ПОЛУЧЕНИЕ ДАННЫХ О ЗАДАЧЕ ---
def get_task_data(task_id):
    url = f"{BITRIX_WEBHOOK_URL}tasks.task.get?taskId={task_id}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        logger.info(f"Bitrix24 DATA for {task_id}: {data}")
        return data.get("result", {}).get("task")
    except Exception as e:
        logger.error(f"Ошибка Bitrix24: {e}")
        return None

# --- СБОРКА СООБЩЕНИЯ ---
def build_message(type_, task):
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
        'Кристина Нестерова': ['держи, ты же у нас любишь всё контролировать 🧐.', 'KPI сам себя не выполнит. Приступай.', 'тут нужна твоя фирменная строгость.', 'входящий таск для специалиста по решению нерешаемого.', 'твой аналитический ум нужен здесь и сейчас.'],
        'Евгения Мурзина': ['маленькая задача для большого специалиста. ✨', 'тебе поручено нести знамя милоты и эффективности.', 'маленький гигант большого SMM, твой час настал.', 'получен новый таск. Уровень милоты в чате повышен.'],
        'Нил М. ВМ ЕВГ': ['маэстро, ваш холст готов. Ждем шедевр. 🎨', 'тут нужен твой нестандартный подход. Думай!', 'задача требует щепотки безумия. У тебя она есть.', 'время для мозгового штурма! Ты штурмуешь, мы ждем.'],
        'Екатерина Белоногова': ['Figma плачет, ждет свою королеву. 👑', 'нужно сделать красиво. Впрочем, как обычно. 💅', 'проект ждет своего героя. И своего дизайнера. Это ты.', 'твои макеты ждут обновления!'],
        'Олег С. АРТ РВБ СПБ ГРИБ': ['Арт-директор, есть возможность поймать вайб. 🤙', 'тут дельце, которое требует твоего фирменного стиля. 😎', 'надо сделать по кайфу. Ты знаешь, как. 🌴']
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
    phrase_list = personalized_phrases.get(fio, generic_phrases)
    random_phrase = random.choice(phrase_list)
    final_ending = f"\n\n{random.choice(random_endings)}"
    opening_line = f"{tg_tag}, {random_phrase}"
    core_message = (
        f"🔢 ID: {task.get('id')}\n"
        f"🧾 Задача: {task.get('title')}\n"
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

# --- ОБРАБОТЧИК ВЕБХУКА (ОСНОВНОЙ) ---
@app.post("/bitrix-webhook")
async def bitrix_webhook(request: Request):
    data = await extract_request_data(request)
    task_id = str(data.get("id") or data.get("task_id") or data.get("task", {}).get("id"))
    type_ = data.get("type") or "new_task"
    logger.info(f"Bitrix POST: id={task_id} type={type_}")
    if not task_id or "{{" in task_id:
        logger.warning("No valid task id")
        return {"ok": False, "error": "No valid task id"}
    try:
        task = get_task_data(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
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
        logger.error(f"Ошибка при обработке webhook: {e}")
        return {"ok": False, "error": str(e)}

# --- Aiogram: ChatGPT-ответы в личку ---
@dp.message()
async def handle_message(message: types.Message):
    if message.chat.type == "private":
        user_text = message.text.strip() if message.text else ""
        if not user_text:
            await message.reply("Пожалуйста, напиши свой вопрос.")
            return
        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o",  # можно заменить на gpt-3.5-turbo для экономии
                messages=[
                    {"role": "system", "content": "Ты дружелюбный ассистент, отвечай по-русски и понятно."},
                    {"role": "user", "content": user_text}
                ],
                max_tokens=600,
                temperature=0.8,
            )
            answer = response.choices[0].message.content.strip()
            await message.reply(answer)
        except Exception as e:
            await message.reply(f"Ошибка при обращении к AI: {e}")

# --- ROOT (для проверки деплоя) ---
@app.get("/")
async def root():
    return {"ok": True, "message": "Бот жив! Для теста POST /bitrix-webhook"}

# --- Aiogram автозапуск на старте FastAPI (lifespan) ---
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(dp.start_polling(bot))

# --- END ---
