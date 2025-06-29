import os
import asyncio
import logging
from typing import Optional, Dict, Any
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request
from datetime import datetime
import random
from openai import AsyncOpenAI
from urllib.parse import parse_qs

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s | %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("main")

# --- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ---
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

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# --- ПОЛЬЗОВАТЕЛЬСКИЕ ТЕГИ И ФРАЗЫ ---
tg_map = {
    'Кристина Нестерова': '@tinatinulya',
    'Евгения Мурзина': '@xquerel',
    'Нил М. ВМ ЕВГ': '@nilfts',
    'Екатерина Белоногова': '@ek_belonogova',
    'Олег С. АРТ РВБ СПБ ГРИБ': '@olegstate'
}
personalized_phrases = {
    'Кристина Нестерова': [
        'держи, ты же у нас любишь всё контролировать 🧐.',
        'KPI сам себя не выполнит. Приступай.',
        'тут нужна твоя фирменная строгость.',
        'входящий таск для специалиста по решению нерешаемого.',
        'твой аналитический ум нужен здесь и сейчас.'
    ],
    'Евгения Мурзина': [
        'маленькая задача для большого специалиста. ✨',
        'тебе поручено нести знамя милоты и эффективности.',
        'маленький гигант большого SMM, твой час настал.',
        'получен новый таск. Уровень милоты в чате повышен.'
    ],
    'Нил М. ВМ ЕВГ': [
        'маэстро, ваш холст готов. Ждем шедевр. 🎨',
        'тут нужен твой нестандартный подход. Думай!',
        'задача требует щепотки безумия. У тебя она есть.',
        'время для мозгового штурма! Ты штурмуешь, мы ждем.'
    ],
    'Екатерина Белоногова': [
        'Figma плачет, ждет свою королеву. 👑',
        'нужно сделать красиво. Впрочем, как обычно. 💅',
        'проект ждет своего героя. И своего дизайнера. Это ты.',
        'твои макеты ждут обновления!'
    ],
    'Олег С. АРТ РВБ СПБ ГРИБ': [
        'Арт-директор, есть возможность поймать вайб. 🤙',
        'тут дельце, которое требует твоего фирменного стиля. 😎',
        'надо сделать по кайфу. Ты знаешь, как. 🌴'
    ]
}
generic_phrases = [
    'у вас тут новая задачка!',
    'для тебя обнаружена новая задача!',
    'тебе выпало новое задание.',
    'время немного поработать.'
]
random_endings = [
    '☎️ Если не сделаешь — позвоню твоей маме! 🤫',
    'P.S. Мой кот будет разочарован, если ты провалишь дедлайн. 🐈',
    'За выполненную в срок задачу — печенька. 🍪 Может быть.',
    'Да пребудет с тобой сила... и кофеин. ☕'
]

# --- UTILS ---
def extract_task_id(data: Dict[str, Any]) -> Optional[str]:
    """
    Универсальный способ вытащить task_id из разных форматов.
    """
    return data.get("id") or data.get("task_id") or data.get("document_id[2]")

def build_message(type_: str, task: Dict[str, Any]) -> str:
    fio = (task.get("responsible", {}).get("name") or '').strip()
    creator = task.get("creator", {}).get("name", "")
    creator_id = task.get("creator", {}).get("id", "")
    tg_tag = tg_map.get(fio, fio)
    deadline = task.get("deadline")
    if deadline:
        try:
            deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00')).strftime('%d.%m.%Y %H:%M')
        except Exception:
            deadline = deadline
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

async def async_get_task_data(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Асинхронно получает задачу из Bitrix24 API.
    """
    url = f"{BITRIX_WEBHOOK_URL}tasks.task.get?taskId={task_id}"
    try:
        async with httpx.AsyncClient(timeout=7) as client:
            resp = await client.get(url)
            data = resp.json()
            return data.get("result", {}).get("task")
    except Exception as e:
        logger.error(f"Ошибка при получении задачи из Bitrix24: {e}")
        return None

async def send_to_telegram(text: str, thread_id: Optional[str] = None):
    """
    Асинхронно отправляет сообщение в Telegram.
    """
    send_kwargs = dict(
        chat_id=int(CHAT_ID),
        text=text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    if THREAD_ID or thread_id:
        send_kwargs["message_thread_id"] = int(THREAD_ID or thread_id)
    try:
        await bot.send_message(**send_kwargs)
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в Telegram: {e}")

# --- FASTAPI ВЕБХУК ---
@app.post("/bitrix-webhook")
async def bitrix_webhook(request: Request):
    try:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            data = await request.json()
        else:
            raw_body = await request.body()
            form = parse_qs(raw_body.decode())
            data = {k: v[0] for k, v in form.items()}
        logger.info(f"BITRIX24 DATA: {data}")
    except Exception as e:
        logger.error(f"Ошибка парсинга тела: {e}")
        return {"ok": False, "error": f"Invalid body: {e}"}

    task_id = extract_task_id(data)
    if not task_id:
        logger.error("Не удалось найти task_id!")
        return {"ok": False, "error": "No task id found!"}

    task = await async_get_task_data(task_id)
    if not task:
        logger.error(f"Task not found: {task_id}")
        return {"ok": False, "error": "Task not found"}

    message = build_message(data.get("type", "new_task"), task)
    await send_to_telegram(message)
    return {"ok": True}

@app.get("/")
async def root():
    return {"ok": True, "status": "Бот живой"}

# --- AI ASSISTANT & ДРУГИЕ КОМАНДЫ ---
@dp.message()
async def universal_handler(message: types.Message):
    """
    Универсальный хендлер. В личке - AI ассистент.
    В группе - автоответ на /help или просто ответ.
    """
    if message.chat.type == "private":
        # GPT-бот в личку
        user_text = message.text.strip() if message.text else ""
        if not user_text:
            await message.reply("Пожалуйста, напиши свой вопрос.")
            return
        await handle_gpt_message(message, user_text)
    elif message.chat.type in ["supergroup", "group"]:
        # Реакция на команды в группе
        if message.text and message.text.startswith("/help"):
            await message.reply("Я ассистент: могу подкинуть задачи из Bitrix24 или ответить как GPT.\n"
                               "В личку - полноценный чат с AI.\n"
                               "Пиши /gpt текст - отвечу!")
        elif message.text and message.text.startswith("/gpt"):
            user_text = message.text.replace("/gpt", "", 1).strip()
            await handle_gpt_message(message, user_text)
        else:
            # Просто игнорим прочее
            pass

async def handle_gpt_message(message: types.Message, user_text: str):
    """
    Обработка сообщений для GPT.
    """
    if not user_text:
        await message.reply("Напиши свой вопрос после /gpt")
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
        logger.error(f"Ошибка при обращении к AI: {e}")
        await message.reply(f"Ошибка при обращении к AI: {e}")

# --- СТАРТ AIОGRAM ПРИ ЗАПУСКЕ FASTAPI ---
@app.on_event("startup")
async def on_startup():
    logger.info("Стартуем aiogram polling")
    asyncio.create_task(dp.start_polling(bot))

# --- ПРОЧИЕ ПОЛЕЗНЫЕ ЭНДПОИНТЫ ---
@app.get("/status")
async def status():
    """
    Быстрый статус приложения.
    """
    return {"ok": True, "time": datetime.now().isoformat()}

@app.get("/docs-link")
async def docs_link():
    """
    Документация FastAPI.
    """
    return {"url": "/docs", "info": "Swagger UI"}

# --- ХЕЛПЕРЫ ДЛЯ ДЕБАГА ---
@app.get("/debug/env")
async def debug_env():
    """
    Смотри, что реально в переменных окружения.
    """
    return {
        "BOT_TOKEN": BOT_TOKEN[:8] + "..." if BOT_TOKEN else None,
        "CHAT_ID": CHAT_ID,
        "THREAD_ID": THREAD_ID,
        "BITRIX_WEBHOOK_URL": BITRIX_WEBHOOK_URL[:25] + "...",
        "OWNER_ID": OWNER_ID
    }

# --- ДЛЯ ЗАПУСКА КАК СКРИПТ ---
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
