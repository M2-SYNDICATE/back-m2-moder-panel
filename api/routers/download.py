# back/api/routers/download.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import os
import urllib
import mimetypes

from api.db_models import Vacancy, Candidate, get_db

router = APIRouter(prefix="/crud/download", tags=["download"])

# 📂 Базовая директория для файлов
BASE_DATA_DIR = Path(__file__).parent.parent / "data" / "uploads"


@router.get("/vacancy/{vacancy_id}")
def download_vacancy_file(vacancy_id: int, db: Session = Depends(get_db)):
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    if not vacancy.filename or not os.path.exists(vacancy.filename):
        raise HTTPException(status_code=404, detail="Vacancy file not found")

    filename = os.path.basename(vacancy.filename)
    encoded_filename = urllib.parse.quote(filename)

    # Определяем MIME-тип
    mime_type, _ = mimetypes.guess_type(vacancy.filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    return FileResponse(
        path=vacancy.filename,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


@router.get("/candidate/{candidate_id}")
def download_candidate_resume(candidate_id: int, db: Session = Depends(get_db)):
    """
    Скачать резюме кандидата по ID
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if not candidate.resume_filename or not os.path.exists(candidate.resume_filename):
        raise HTTPException(status_code=404, detail="Resume file not found")

    filename=os.path.basename(candidate.resume_filename)
    encoded_filename = urllib.parse.quote(filename)

    # Определяем MIME-тип
    mime_type, _ = mimetypes.guess_type(candidate.resume_filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    return FileResponse(
        path=candidate.resume_filename,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )
