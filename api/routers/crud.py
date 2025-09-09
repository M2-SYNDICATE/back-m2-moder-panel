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
from api.scripts.m1.module1 import cv_validation
from api.scripts.m1.convert_functions import convert_to_dict  # Интеграция с Module1
from api.scripts.m2.module2 import generate_and_save_scenario
from typing import List, Dict, Any
import json
import tempfile
import string
import secrets
import re
import asyncio

router = APIRouter(prefix="/crud", tags=["crud"])

# Настройки для паролей и JWT
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "sdfghjkl"  # Замените на реальный секрет
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 999

# ---------- helpers (prefix / room / phone) ----------

def _delete_file_silent(p: Path) -> None:
    try:
        if p.exists() and p.is_file():
            p.unlink()
    except Exception as e:
        print(f"⚠️ Не удалось удалить файл '{p}': {e}")

def _delete_scenarios_for_vacancy(vacancy_id: int) -> int:
    """Удаляет все сценарии для вакансии: *_<vacancy_id>.json"""
    count = 0
    for p in SCENARIO_DIR.glob(f"*_{vacancy_id}.json"):
        _delete_file_silent(p)
        count += 1
    return count

def _delete_scenarios_for_candidate(candidate_id: int, vacancy_id: int) -> int:
    """Удаляет сценарий кандидата: <candidate_id>_<vacancy_id>.json"""
    p = SCENARIO_DIR / f"{candidate_id}_{vacancy_id}.json"
    existed = p.exists()
    _delete_file_silent(p)
    return int(existed)

def _random_prefix(length: int = 6) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def _slug_ascii(s: str) -> str:
    """
    Пытаемся сделать ASCII-слуг: приводим к нижнему регистру,
    убираем всё не буквы/цифры, заменяем пробелы на '-'.
    Для кириллицы .encode('ascii','ignore') даст пусто — это ожидаемо,
    тогда fallback на рандом.
    """
    s_ascii = s.encode("ascii", "ignore").decode("ascii").lower()
    s_ascii = re.sub(r"\s+", "-", s_ascii)
    s_ascii = re.sub(r"[^a-z0-9\-]", "", s_ascii)
    s_ascii = s_ascii.strip("-")
    return s_ascii

def _make_room_prefix(vacancy: Vacancy) -> str:
    """
    Источник префикса:
    1) Пробуем короткое имя/код вакансии если есть такие поля у модели.
       >>> Если хотите управлять префиксом вручную — заведите, например, поле Vacancy.short_code
       >>> и используйте его здесь.
    2) Пробуем title/name (могут быть на кириллице) — слугифицируем в ASCII.
    3) Fallback: рандомный префикс.
    """
    for attr in ("short_code", "short_name", "code", "prefix"):  # <<< МЕСТО ДЛЯ ЯВНОГО ПРЕФИКСА
        val = getattr(vacancy, attr, None)
        if isinstance(val, str) and val.strip():
            pref = _slug_ascii(val.strip())
            if pref:
                return pref

    for attr in ("title", "name"):  # частые поля с названием вакансии
        val = getattr(vacancy, attr, None)
        if isinstance(val, str) and val.strip():
            pref = _slug_ascii(val.strip())
            if pref:
                return pref

    return _random_prefix()

def _fake_phone_ru() -> str:
    """Генерация номера в формате +7XXXXXXXXXX (10 цифр после +7)."""
    digits = "".join(secrets.choice(string.digits) for _ in range(10))
    return f"+7{digits}"

def _build_room_name(candidate_id: int, vacancy_id: int, prefix: str) -> str:
    return f"{prefix}-{candidate_id}-{vacancy_id}"

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

SCENARIO_DIR = Path(__file__).parent.parent / "data" / "scenario"  # api/data/scenario

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
        resumeAnalysis=c.resume_analysis, callStatus=c.call_status, callDate=c.call_date, callLink=c.call_link
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
        createdAt=candidate.created_at, ai_report=candidate.ai_report, phone=candidate.email
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

@router.post("/candidate")
async def add_candidate(
    vacancy_id: str = Form(...),
    resumes: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    added_candidates: List[int] = []
    generated_scenarios: List[str] = []

    # 0) Вакансия
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    # 1) Директории
    cvs_dir = BASE_DATA_DIR / str(vacancy.id) / "cvs"
    scenario_dir = SCENARIO_DIR
    os.makedirs(cvs_dir, exist_ok=True)
    os.makedirs(scenario_dir, exist_ok=True)

    # 2) Сохраняем резюме (IO — можно оставить синхронно)
    for resume in resumes:
        with open(cvs_dir / resume.filename, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)

    # 3) Запускаем Модуль 1 в пуле потоков
    try:
        result_dict = await asyncio.to_thread(
            cv_validation,
            folder_cv_path=str(cvs_dir),
            info_cv_path=str(vacancy.filename),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analyse error: {e}")

    room_prefix = _make_room_prefix(vacancy)

    # Будем копить задачи генерации сценариев (без ORM внутри)
    scenario_tasks = []

    # 4) Создаём кандидатов в БД, для suitable — сразу сохраняем ссылку/дату/телефон,
    #    а генерацию сценария отправляем в фоновый поток.
    for link_to_cv, analysis_result in result_dict.items():
        data: Dict[str, Any] = analysis_result if isinstance(analysis_result, dict) else {}
        is_suitable = bool(data.get("answer", False))
        ai_comments = data.get("comment")

        raw_name = data.get("name")
        full_name = raw_name if raw_name not in [None, "None", 0, "0"] else Path(link_to_cv).name

        # Создание кандидата (в основном потоке)
        try:
            new_candidate = Candidate(
                full_name=full_name,
                vacancy_id=vacancy.id,
                call_status="planed",
                resume_filename=str(link_to_cv),
                resume_size=Path(link_to_cv).stat().st_size if Path(link_to_cv).exists() else 0,
                resume_analysis=ResumeAnalysisStatus.suitable if is_suitable else ResumeAnalysisStatus.not_suitable,
                ai_comments=ai_comments,
            )
            db.add(new_candidate)
            db.commit()
            db.refresh(new_candidate)
            added_candidates.append(new_candidate.id)
        except Exception as e:
            db.rollback()
            print(f"DB error for CV '{link_to_cv}': {e}")
            continue

        if is_suitable:
            # 4a) сразу записываем call_link / email / call_date (ORM тут!)
            try:
                room_name = _build_room_name(new_candidate.id, vacancy.id, room_prefix)
                new_candidate.call_link = f"https://m2-live.ru/room/{room_name}"
                new_candidate.email = _fake_phone_ru()   # телефон по ТЗ кладём в email
                new_candidate.call_date = datetime.now()  # DateTime в БД

                db.add(new_candidate)
                db.commit()
                db.refresh(new_candidate)
            except Exception as e:
                db.rollback()
                print(f"Error saving call link/phone/date for candidate {new_candidate.id}: {e}")

            # 4b) подготовим payload для сценария и запланируем to_thread
            scenario_filename = f"{new_candidate.id}_{vacancy.id}.json"

            # каждый поток сам сделает свой temp json, чтобы не делить ресурсы
            async def _scenario_job(
                info_cv_path: str,
                data_obj: Dict[str, Any],
                link: str,
                out_dir: str,
                scen_filename: str,
            ):
                # всё внутри — в отдельном потоке, никаких обращений к ORM!
                def _work():
                    # временный JSON на одного кандидата
                    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tmp:
                        json.dump({link: data_obj}, tmp, ensure_ascii=False, indent=2)
                        tmp_json_path = tmp.name
                    try:
                        generate_and_save_scenario(
                            info_cv_path=info_cv_path,
                            json_path=tmp_json_path,
                            out_dir=out_dir,
                            scenario_filename=scen_filename,
                        )
                        return scen_filename, None
                    except Exception as ex:
                        return None, ex
                    finally:
                        try:
                            os.remove(tmp_json_path)
                        except Exception:
                            pass

                return await asyncio.to_thread(_work)

            scenario_tasks.append(
                _scenario_job(
                    info_cv_path=str(vacancy.filename),
                    data_obj=data,
                    link=link_to_cv,
                    out_dir=str(scenario_dir),
                    scen_filename=scenario_filename,
                )
            )

    # 5) Дожидаемся генерации всех сценариев (параллельно в потоках)
    if scenario_tasks:
        results = await asyncio.gather(*scenario_tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                print(f"Scenario task raised: {res}")
                continue
            scen_filename, err = res
            if err:
                print(f"Scenario generation error: {err}")
            elif scen_filename:
                generated_scenarios.append(scen_filename)

    return {
        "message": "Candidates added",
        "candidates_id": added_candidates,
        "scenarios_saved": generated_scenarios,
        "scenario_dir": str(SCENARIO_DIR),
    }

@router.delete("/vacancy/{vacancy_id}")  # _УДАЛИТЬ ВАКАНСИЮ_ DEL (каскад)
def delete_vacancy(vacancy_id: int, db: Session = Depends(get_db)):
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    # 1) Удаляем запись из БД (каскад на кандидатов — согласно вашей модели/ФК)
    db.delete(vacancy)
    db.commit()

    # 2) Удаляем папку с файлами вакансии (uploads/<vacancy_id>)
    vacancy_dir = BASE_DATA_DIR / str(vacancy_id)
    if vacancy_dir.exists() and vacancy_dir.is_dir():
        shutil.rmtree(vacancy_dir, ignore_errors=True)

    # 3) Удаляем все сценарии, связанные с вакансией
    _delete_scenarios_for_vacancy(vacancy_id)

    return {"message": "Vacancy, files and scenarios deleted"}


@router.delete("/candidate/{candidate_id}")  # _УДАЛИТЬ КАНДИДАТА_ DEL
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Сохраняем vacancy_id до удаления записи — нужно для имени сценария
    vacancy_id = int(candidate.vacancy_id) if candidate.vacancy_id is not None else None

    # 1) Удаляем файл резюме кандидата
    if candidate.resume_filename and os.path.exists(candidate.resume_filename):
        try:
            os.remove(candidate.resume_filename)
        except Exception as e:
            print(f"⚠️ Не удалось удалить файл резюме {candidate.resume_filename}: {e}")

    # 2) Удаляем сценарий кандидата (если знаем vacancy_id)
    scenarios_deleted = 0
    if vacancy_id is not None:
        _delete_scenarios_for_candidate(candidate_id, vacancy_id)

    # 3) Удаляем запись из БД
    db.delete(candidate)
    db.commit()

    return {"message": "Candidate, resume and scenario deleted"}