import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from fastapi import FastAPI
import openai
import uvicorn

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "196614680"))  # Только твой user id, если хочешь ограничить

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан!")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не задан!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

def is_private(message: types.Message):
    return message.chat.type == "private"

# Если нужно отвечать только тебе - раскомментируй следующую строку и используй в хендлере
# def is_owner(message: types.Message):
#     return message.from_user.id == OWNER_ID

@dp.message()
async def handle_message(message: types.Message):
    if is_private(message):
        # Если нужно отвечать только тебе, раскомментируй строку ниже
        # if not is_owner(message): return
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

async def run_all():
    asyncio.create_task(dp.start_polling(bot))
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(run_all())
