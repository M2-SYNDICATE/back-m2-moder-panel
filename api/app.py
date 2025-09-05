# back/api/app.py
# (Обновленный файл: добавляем импорт роутера)

from fastapi import FastAPI, Request
import json
from fastapi.middleware.cors import CORSMiddleware
from api.routers import upload, crud, download, schedule

app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить все источники
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все методы (GET, POST, OPTIONS и др.)
    allow_headers=["*"],  # Разрешить все заголовки
)

# Подключаем роутер
# app.include_router(upload.router)
app.include_router(crud.router)
app.include_router(download.router)
app.include_router(schedule.router)