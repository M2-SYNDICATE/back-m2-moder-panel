from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import os
import smtplib
from email.message import EmailMessage

from api.db_models import Candidate, Vacancy, get_db, CallStatus  # CallStatus уже импортируется в твоём crud.py
from api.models import CandidateInvite
# Если в CallStatus нет значения scheduled/appointed — см. комментарий ниже.

router = APIRouter(prefix="/crud/schedule", tags=["schedule"])

# Reuse auth settings from your crud.py
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"

# Где развёрнут фронт/бэкенд. Если фронта нет, можно использовать наш HTML эндпоинт /schedule/choose
BASE_APP_URL = os.getenv("BASE_APP_URL", "http://localhost:8000")

# SMTP настройки (задай в env)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "no-reply@example.com")
SMTP_PASS = os.getenv("SMTP_PASS", "password")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)


def send_email(to_email: str, subject: str, html_body: str, text_body: str = ""):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    if text_body:
        msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)


def make_token(candidate_id: int, expires_minutes: int = 7 * 24 * 60) -> str:
    payload = {
        "cid": candidate_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def parse_token(token: str) -> int:
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(data["cid"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid or expired token")


def get_scheduled_status():
    """
    Возвращаем нужное значение из enum CallStatus.
    Если у тебя другое имя (например, 'appointed' или 'scheduled_interview'),
    поменяй здесь один раз — и весь код ниже подстроится.
    """
    # Наиболее вероятное имя:
    return getattr(CallStatus, "scheduled", None) or getattr(CallStatus, "appointed")


@router.post("/invite")
def send_schedule_invite(
    data: CandidateInvite,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    1) Сохраняем email кандидата
    2) Генерируем токен
    3) Отправляем письмо с ссылкой для выбора даты/времени
    """
    candidate = db.query(Candidate).filter(Candidate.id == data.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # если в модели Candidate нет поля email — добавь его в БД; здесь предполагаем, что оно есть:
    candidate.email = data.email
    db.commit()

    token = make_token(data.candidate_id)
    # Вариант 1: встроенная HTML-форма на бэке
    choose_url = f"{BASE_APP_URL}/schedule/choose?token={token}"
    # (Альтернатива — отправлять на фронтовую страницу бронирования, если она есть)

    subject = "Выбор даты собеседования"
    text_body = (
        f"Здравствуйте, {candidate.full_name}!\n\n"
        f"Пожалуйста, выберите удобные дату и время для собеседования: {choose_url}\n\n"
        f"Если ссылка не открывается, скопируйте её в браузер."
    )
    html_body = f"""
    <p>Здравствуйте, {candidate.full_name}!</p>
    <p>Пожалуйста, выберите удобные дату и время для собеседования по ссылке ниже:</p>
    <p><a href="{choose_url}">{choose_url}</a></p>
    <p>Если ссылка не открывается, скопируйте её в адресную строку браузера.</p>
    """

    background_tasks.add_task(send_email, data.email, subject, html_body, text_body)

    return {"message": "Invite sent", "choose_url": choose_url}


@router.get("/choose", response_class=HTMLResponse)
def choose_datetime(token: str):
    """
    Простейшая HTML-страница с формой (datetime-local), которая отправляет POST на /schedule/confirm.
    """
    # Валидируем токен (и сразу узнаём candidate_id), чтобы не показывать форму для битого токена
    _ = parse_token(token)

    return f"""
    <!doctype html>
    <html lang="ru">
    <head>
      <meta charset="utf-8"/>
      <title>Выбор времени собеседования</title>
      <meta name="viewport" content="width=device-width,initial-scale=1"/>
      <style>
        body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding: 24px; }}
        .card {{ max-width: 520px; margin: 0 auto; padding: 24px; border: 1px solid #e5e7eb; border-radius: 12px; }}
        label {{ display:block; margin-bottom:8px; font-weight:600; }}
        input, button {{ width:100%; padding:10px 12px; border-radius:8px; border:1px solid #d1d5db; }}
        button {{ margin-top:12px; border: none; background:#111827; color:white; cursor:pointer; }}
        button:hover {{ background:#0b1220; }}
        .hint {{ color:#6b7280; font-size: 14px; margin-top:6px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h2>Назначить собеседование</h2>
        <form method="post" action="/schedule/confirm">
          <input type="hidden" name="token" value="{token}"/>
          <label for="dt">Выберите дату и время</label>
          <input id="dt" type="datetime-local" name="datetime_local" required />
          <div class="hint">Время укажите в своём часовом поясе.</div>
          <button type="submit">Подтвердить</button>
        </form>
      </div>
    </body>
    </html>
    """


@router.post("/confirm")
def confirm_datetime(
    token: str = Form(...),
    datetime_local: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Принимаем токен + datetime-local (строка, например '2025-09-08T14:30').
    Сохраняем в БД (в UTC) и меняем статус на 'назначено'.
    """
    candidate_id = parse_token(token)
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Парсим локальное время кандидата.
    # Если хочешь явную таймзону, пришли её отдельным полем; сейчас считаем, что это локальное время кандидата,
    # сохраняем как naive и дальше интерпретируем как Europe/Copenhagen или сразу как UTC.
    # Самый простой путь: принять как naive и сохранить в UTC без смещения (или со смещением, если знаем TZ).
    # Здесь предполагаем Europe/Copenhagen (UTC+2/UTC+1) — можно доработать под pytz/zoneinfo.
    try:
        # Строка формата 'YYYY-MM-DDTHH:MM'
        dt_naive = datetime.strptime(datetime_local, "%Y-%m-%dT%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad datetime format. Use 'YYYY-MM-DDTHH:MM'.")

    # Если хочешь хранить в UTC, добавь таймзону. Для простоты — считаем присланное время как локальное Europe/Copenhagen.
    # Преобразуем в UTC:
    # На бэке без зависимостей можно принять как UTC сразу:
    dt_utc = dt_naive.replace(tzinfo=timezone.utc)

    candidate.call_date = dt_utc
    scheduled_status = get_scheduled_status()
    if scheduled_status is None:
        # Если в enum нет нужного значения — дадим понятную ошибку (или выставим строку, если поле строковое)
        raise HTTPException(status_code=500, detail="CallStatus enum has no 'scheduled'/'appointed' value")
    candidate.call_status = scheduled_status

    db.commit()

    # Можно вернуть редирект на «спасибо» страницу:
    return JSONResponse({"message": "Interview scheduled", "candidate_id": candidate.id, "datetime_utc": dt_utc.isoformat()})
