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
from api.scripts.module1 import cv_validation  # Интеграция с Module1
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
    return {"access_token": access_token, "token_type": "bearer"}

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
    title = f"{candidate.full_name} / {vacancy.title}" if vacancy else candidate.full_name
    if candidate.resume_analysis != ResumeAnalysisStatus.suitable:
        candidate.call_date = None
        candidate.call_link = None
        candidate.ai_comments = None
        candidate.ai_report = None
    return CandidateDetailResponse(
        id=candidate.id, title=title, vacancy=vacancy.title if vacancy else None,
        callDate=candidate.call_date, callLink=candidate.call_link,
        comments=candidate.ai_comments, resume=resume_dict,
        resumeAnalysis=candidate.resume_analysis, callStatus=candidate.call_status,
        createdAt=candidate.created_at, ai_report=candidate.ai_report
    )

@router.post("/vacancy")  # _СОЗДАТЬ ВАКАНСИЮ_ POST
async def create_vacancy(title: str = Form(...), info_cv: UploadFile = File(...), db: Session = Depends(get_db)):
    extension = info_cv.filename.split('.')[-1].lower()
    if extension not in ['pdf', 'docx', 'doc']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    vacancy_dir = BASE_DATA_DIR / str(datetime.now().timestamp())
    os.makedirs(vacancy_dir, exist_ok=True)
    filename = vacancy_dir / info_cv.filename
    with open(filename, "wb") as buffer:
        shutil.copyfileobj(info_cv.file, buffer)
    new_vacancy = Vacancy(title=title, filename=str(filename))
    db.add(new_vacancy)
    db.commit()
    db.refresh(new_vacancy)
    return {"message": "Vacancy created", "vacancy_id": new_vacancy.id}

@router.post("/candidate")  # _ДОБАВИТЬ КАНДИДАТА_ POST
async def add_candidate(
    vacancy_title: str = Form(...),
    full_name: str = Form(...),  # Добавил ФИО, так как в объекте фронта есть fullName
    resume: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    vacancy = db.query(Vacancy).filter(Vacancy.title == vacancy_title).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    extension = resume.filename.split('.')[-1].lower()
    if extension not in ['pdf', 'docx', 'doc']:
        raise HTTPException(status_code=400, detail="Invalid resume format")
    cv_dir = BASE_DATA_DIR / str(vacancy.id) / "cv"
    os.makedirs(cv_dir, exist_ok=True)
    resume_path = cv_dir / resume.filename
    with open(resume_path, "wb") as buffer:
        shutil.copyfileobj(resume.file, buffer)
    # Вызов Module1 для анализа
    try:
        result_dict = cv_validation(folder_cv_path=str(cv_dir), info_cv_path=vacancy.filename)
        # Предполагаем, что result_dict[resume_path] имеет 'answer': bool, 'comment': str, 'name': str
        analysis_result = result_dict.get(str(resume_path), {})
        resume_analysis = ResumeAnalysisStatus.suitable if analysis_result.get('answer', False) else ResumeAnalysisStatus.not_suitable
        ai_comments = analysis_result.get('comment')
    except Exception as e:
        resume_analysis = ResumeAnalysisStatus.not_suitable
        ai_comments = str(e)
    new_candidate = Candidate(
        full_name=full_name or analysis_result.get('name', 'Unknown'),
        vacancy_id=vacancy.id,
        resume_filename=str(resume_path),
        resume_size=resume_path.stat().st_size,
        resume_analysis=resume_analysis,
        ai_comments=ai_comments
        # ai_report заполняется позже, в других модулях
    )
    db.add(new_candidate)
    db.commit()
    db.refresh(new_candidate)
    return {"message": "Candidate added", "candidate_id": new_candidate.id}

@router.delete("/vacancy/{vacancy_id}")  # _УДАЛИТЬ ВАКАНСИЮ_ DEL (каскад)
def delete_vacancy(vacancy_id: int, db: Session = Depends(get_db)):
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    db.delete(vacancy)
    db.commit()
    # Каскад удалит кандидатов автоматически
    return {"message": "Vacancy deleted"}

@router.delete("/candidate/{candidate_id}")  # _УДАЛИТЬ КАНДИДАТА_ DEL
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(candidate)
    db.commit()
    return {"message": "Candidate deleted"}