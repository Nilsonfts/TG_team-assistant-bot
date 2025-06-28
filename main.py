import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from fastapi import FastAPI
import uvicorn

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не задана!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.reply(f"Привет! Твой user ID: <code>{message.from_user.id}</code>\nchat ID: <code>{message.chat.id}</code>", parse_mode=ParseMode.HTML)

@dp.message()
async def echo(message: types.Message):
    print(f"Получено сообщение: {message.text} от {message.from_user.id}")
    await message.reply("Я получил твое сообщение!")

async def main():
    asyncio.create_task(dp.start_polling(bot))
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
