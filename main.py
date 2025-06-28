import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
import openai

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env")

openai.api_key = OPENAI_API_KEY

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Привет! Я ассистент-бот. Задай мне любой вопрос, и я помогу!")

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer("Просто напиши мне свой вопрос или запрос — и я попробую помочь!")

@dp.message()
async def gpt_answer(message: types.Message):
    user_text = message.text
    await message.answer("Секунду, думаю...")

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Или другой, если у тебя другой API/ключ
            messages=[
                {"role": "system", "content": "Ты дружелюбный Telegram-ассистент."},
                {"role": "user", "content": user_text}
            ],
            max_tokens=400,
            temperature=0.7,
        )
        answer = response['choices'][0]['message']['content']
        await message.answer(answer)
    except Exception as e:
        await message.answer(f"Ошибка при обращении к AI: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
