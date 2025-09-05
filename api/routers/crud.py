# back/api/routers/crud.py
# (Новый файл: Роутер для CRUD эндпоинтов)

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from api.db_models import User, Vacancy, Candidate, get_db, ResumeAnalysisStatus, CallStatus
from api.models import UserRegister, UserLogin, Token, VacancyResponse, CandidateListResponse, CandidateDetailResponse, AddCandidateRequest
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
import os
import shutil
from pathlib import Path
from api.scripts.module1 import cv_validation
from api.scripts.convert_functions import convert_to_dict  # Интеграция с Module1
from typing import List

router = APIRouter(prefix="/crud", tags=["crud"])

# Настройки для паролей и JWT
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "your_secret_key"  # Замените на реальный секрет
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Папка для файлов
BASE_DATA_DIR = Path(__file__).parent.parent / "data" / "uploads"
os.makedirs(BASE_DATA_DIR, exist_ok=True)

@router.post("/register")  # _ЛОГИН_ POST как регистрация
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user.password)
    new_user = User(fio=user.fullName, email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully"}

@router.post("/login", response_model=Token)  # Отдельный логин для аутентификации
def login_user(form_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.email).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer", "userEmail": user.email, "fullName": user.fio}

@router.get("/vacancies", response_model=List[VacancyResponse])  # _ВАКАНСИИ_ GET
def get_vacancies(db: Session = Depends(get_db)):
    vacancies = db.query(Vacancy).all()
    return [VacancyResponse(id=v.id, title=v.title, fileName=v.filename) for v in vacancies]

@router.get("/candidates", response_model=List[CandidateListResponse])  # _КАНДИДАТЫ_ GET
def get_candidates(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()
    return [CandidateListResponse(
        id=c.id, fullName=c.full_name, vacancyId=c.vacancy_id,
        resumeAnalysis=c.resume_analysis, callStatus=c.call_status, callDate=c.call_date
    ) for c in candidates]

@router.get("/candidate/{candidate_id}", response_model=CandidateDetailResponse)  # _КАНДИДАТ_ GET
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    vacancy = db.query(Vacancy).filter(Vacancy.id == candidate.vacancy_id).first()
    resume_upload_date = candidate.created_at.date().isoformat() if candidate.created_at else None
    resume_dict = {
        "name": os.path.basename(candidate.resume_filename),
        "size": candidate.resume_size,
        "uploadDate": resume_upload_date
    }
    
    if candidate.resume_analysis != ResumeAnalysisStatus.suitable:
        candidate.call_date = None
        candidate.call_link = None
        candidate.ai_report = None
    return CandidateDetailResponse(
        id=candidate.id, title=candidate.full_name, vacancy=vacancy.title if vacancy else None,
        callDate=candidate.call_date, callLink=candidate.call_link,
        comments=candidate.ai_comments, resume=resume_dict,
        resumeAnalysis=candidate.resume_analysis, callStatus=candidate.call_status,
        createdAt=candidate.created_at, ai_report=candidate.ai_report
    )

@router.post("/vacancy")  # _СОЗДАТЬ ВАКАНСИЮ_ POST
async def create_vacancy(info_cv: UploadFile = File(...), db: Session = Depends(get_db)):
    new_vacancy = Vacancy(title="load", filename="load")
    db.add(new_vacancy)
    db.commit()
    db.refresh(new_vacancy)
    vacancy_dir = BASE_DATA_DIR / str(new_vacancy.id)
    os.makedirs(vacancy_dir, exist_ok=True)
    filename = vacancy_dir / info_cv.filename
    with open(filename, "wb") as buffer:
        shutil.copyfileobj(info_cv.file, buffer)

    _, title = convert_to_dict(str(filename))
    new_vacancy.title = str(title)
    new_vacancy.filename = str(filename)
    db.commit()
    db.refresh(new_vacancy)

    return {"message": "Vacancy created", "vacancy_id": new_vacancy.id}

@router.post("/candidate")  # _ДОБАВИТЬ КАНДИДАТА_ POST
async def add_candidate(
    vacancy_id: str = Form(...),
    resumes: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    added_candidates = []
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    cvs_dir = BASE_DATA_DIR / str(vacancy.id) / "cvs"
    os.makedirs(cvs_dir, exist_ok=True)
    
    for resume in resumes:
        resume_path = cvs_dir / resume.filename
        print(resume_path)
        with open(resume_path, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)
        # Вызов Module1 для анализа
    try:
        result_dict = cv_validation(folder_cv_path=str(cvs_dir), info_cv_path=vacancy.filename)
    except Exception as e:
        HTTPException(status_code=500, detail="AI analise error")
    for link_to_cv, analysis_result in result_dict.items():
        resume_analysis = ResumeAnalysisStatus.suitable if analysis_result.get('answer', False) else ResumeAnalysisStatus.not_suitable
        ai_comments = analysis_result.get('comment')
        new_candidate = Candidate(
            full_name=analysis_result.get('name') if analysis_result.get('name') not in [None,'None',0,'0'] else Path(link_to_cv).name,
            vacancy_id=vacancy.id,
            resume_filename=str(link_to_cv),
            resume_size=Path(link_to_cv).stat().st_size,
            resume_analysis=resume_analysis,
            ai_comments=ai_comments
            # ai_report заполняется позже, в других модулях
        )
        db.add(new_candidate)
        db.commit()
        db.refresh(new_candidate)
        added_candidates.append(new_candidate.id)
    return {"message": "Candidates added", "candidates_id": added_candidates}

@router.delete("/vacancy/{vacancy_id}")  # _УДАЛИТЬ ВАКАНСИЮ_ DEL (каскад)
def delete_vacancy(vacancy_id: int, db: Session = Depends(get_db)):
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    # Удаляем запись из БД
    db.delete(vacancy)
    db.commit()

    # Удаляем папку с файлами вакансии (если существует)
    vacancy_dir = BASE_DATA_DIR / str(vacancy_id)
    if vacancy_dir.exists() and vacancy_dir.is_dir():
        shutil.rmtree(vacancy_dir, ignore_errors=True)

    return {"message": "Vacancy and files deleted"}

@router.delete("/candidate/{candidate_id}")  # _УДАЛИТЬ КАНДИДАТА_ DEL
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Удаляем файл резюме кандидата
    if candidate.resume_filename and os.path.exists(candidate.resume_filename):
        try:
            os.remove(candidate.resume_filename)
        except Exception as e:
            print(f"⚠️ Не удалось удалить файл резюме {candidate.resume_filename}: {e}")

    # Удаляем запись из БД
    db.delete(candidate)
    db.commit()

    return {"message": "Candidate and resume deleted"}