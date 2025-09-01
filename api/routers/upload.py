# back/api/routers/upload.py
# (Обновленный файл: изменяем эндпоинт для принятия данных, соответствующих Module1Input после загрузки)

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import shutil
import os
from pathlib import Path
import time
from api.models import Module1Input  # Импорт модели

router = APIRouter(prefix="/upload", tags=["upload"])

# Папка для сохранения файлов (back/api/data/uploads/)
BASE_DATA_DIR = Path(__file__).parent.parent / "data" / "uploads"
os.makedirs(BASE_DATA_DIR, exist_ok=True)  # Создаем базовую папку, если не существует

@router.post("/vacancy-and-cvs", response_model=Module1Input)
async def upload_vacancy_and_cvs(
    info_cv: UploadFile = File(...),  # Файл с описанием вакансии (PDF/DOCX/DOC)
    cvs: list[UploadFile] = File(...)  # Список файлов CV (PDF/DOCX/DOC)
):
    """
    Эндпоинт для загрузки файла с описанием вакансии и списка CV.
    Сохраняет файлы в уникальной подпапке в data/uploads/{timestamp}/,
    где vacancy в корне, CV в поддиректории cv/.
    Возвращает Module1Input с путями для дальнейшей обработки в Module1.
    """
    # Проверяем наличие файлов
    if not info_cv:
        raise HTTPException(status_code=400, detail="Файл с описанием вакансии обязателен.")
    if not cvs:
        raise HTTPException(status_code=400, detail="Необходимо загрузить хотя бы одно CV.")

    # Создаем уникальную папку по timestamp
    timestamp = int(time.time())
    upload_dir = BASE_DATA_DIR / str(timestamp)
    cv_dir = upload_dir / "cv"
    os.makedirs(cv_dir, exist_ok=True)

    try:
        # Сохраняем файл вакансии
        info_extension = info_cv.filename.split('.')[-1].lower()
        if info_extension not in ['pdf', 'docx', 'doc']:
            raise HTTPException(status_code=400, detail="Неподдерживаемый формат для файла вакансии: PDF, DOCX, DOC.")
        
        info_cv_path = upload_dir / f"info_cv.{info_extension}"
        with open(info_cv_path, "wb") as buffer:
            shutil.copyfileobj(info_cv.file, buffer)

        # Сохраняем CV файлы в поддиректории cv/
        for cv_file in cvs:
            cv_extension = cv_file.filename.split('.')[-1].lower()
            if cv_extension not in ['pdf', 'docx', 'doc']:
                raise HTTPException(status_code=400, detail=f"Неподдерживаемый формат для CV '{cv_file.filename}': PDF, DOCX, DOC.")
            
            cv_path = cv_dir / cv_file.filename
            with open(cv_path, "wb") as buffer:
                shutil.copyfileobj(cv_file.file, buffer)

        # Возвращаем модель с путями
        return Module1Input(
            folder_cv_path=str(cv_dir),
            infocv_path=str(info_cv_path)
        )
    
    except Exception as e:
        # Очистка в случае ошибки (опционально)
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении файлов: {str(e)}")