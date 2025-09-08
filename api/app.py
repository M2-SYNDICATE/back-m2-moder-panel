# back/api/app.py
# (Обновленный файл: добавляем импорт роутера)

from fastapi import FastAPI, Request
import json
from fastapi.middleware.cors import CORSMiddleware
from api.routers import crud, download, schedule, scenario, interview_report
# ================= JWT middleware =================
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

app = FastAPI()
# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить все источники
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все методы (GET, POST, OPTIONS и др.)
    allow_headers=["*"],  # Разрешить все заголовки
)
# Публичные эндпоинты (без токена)
PUBLIC_PATHS = {
    "/crud/login",
    "/scenario/get_scenario",
    "/interview_report",
    "/docs",
    "/openapi.json",
}

load_dotenv()
# Сервисный токен и список эндпоинтов, куда он дает доступ
MY_CUSTOM_SERVICE_TOKEN = os.getenv("MY_CUSTOM_SERVICE_TOKEN")
SERVICE_TOKEN_PATHS = {
    
    
}

def _strip_bearer(auth_header: str | None):
    if not auth_header:
        return None
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):]
    return None

@app.middleware("http")
async def jwt_auth_middleware(request: Request, call_next):
    # Разрешаем preflight и публичные маршруты
    if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    raw = request.headers.get("Authorization")
    token = _strip_bearer(raw)
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Authorization header is missing or invalid"})

    # Сервисный токен: точное совпадение и доступ только к разрешенным путям
    if token == MY_CUSTOM_SERVICE_TOKEN:
        if request.url.path in SERVICE_TOKEN_PATHS:
            return await call_next(request)
        return JSONResponse(status_code=403, content={"detail": "Service token not allowed for this endpoint"})

    # Обычный JWT: проверяем подпись и срок
    try:
        payload = jwt.decode(token, crud.SECRET_KEY, algorithms=[crud.ALGORITHM])
        exp = payload.get("exp")
        if exp is not None:
            if datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(tz=timezone.utc):
                return JSONResponse(status_code=401, content={"detail": "Token expired"})
        # при необходимости можно дополнить проверкой payload["sub"] и поиском пользователя в БД
    except JWTError:
        return JSONResponse(status_code=401, content={"detail": "Token is invalid or expired"})

    return await call_next(request)


# Подключаем роутер
# app.include_router(upload.router)
app.include_router(crud.router)
app.include_router(download.router)
app.include_router(schedule.router)
app.include_router(scenario.router)
app.include_router(interview_report.router)