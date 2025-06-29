import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

app = FastAPI()

# Ваши переменные окружения
CHAT_ID = os.getenv("CHAT_ID")
# остальные переменные

# Настройка логгирования (можно смотреть логи в Railway)
logging.basicConfig(level=logging.INFO)

@app.post("/bitrix-webhook")
async def bitrix_webhook(request: Request):
    # Логируем сырое тело запроса для отладки
    raw_body = await request.body()
    logging.info(f"RAW BODY: {raw_body}")

    try:
        data = await request.json()
    except Exception as e:
        logging.error(f"Ошибка при парсинге JSON: {e}")
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid JSON: {e}. RAW BODY: {raw_body.decode('utf-8', errors='replace')}"
        )

    # Проверяем, что пришёл ID задачи
    task_id = data.get("id")
    if not task_id:
        return JSONResponse({"ok": False, "error": "No 'id' in request"}, status_code=400)
    
    # Здесь ваша логика работы с task_id и отправки сообщения в Telegram
    # send_to_telegram(chat_id=CHAT_ID, text=...)

    # Пример успешного ответа
    return {"ok": True, "message": f"Task {task_id} processed"}

# Можно добавить обработчик для GET (например, тестовый "жив ли сервер")
@app.get("/bitrix-webhook")
async def webhook_status():
    return {"ok": True, "message": "Webhook is alive"}
