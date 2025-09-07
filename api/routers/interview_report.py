from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import os
import shutil
import smtplib
from email.message import EmailMessage
import re
from pathlib import Path
from typing import Dict, Any

from api.db_models import Candidate, Vacancy, get_db, CallStatus
from api.models import RoomName
from api.routers.scenario import scenario_json
router = APIRouter(tags=["report"])

# BASE_REPORT_DIR = Path(__file__).parent.parent / "data" / "reports"


test_report = {'general_0': {'passed': True, 'score': 7}, 'general_1': {'passed': False, 'score': 0}, 'professional_0': {'passed': False, 'score': 4}}


@router.post("/interview_report")
def get_interview_report(room_name: str, report: dict, db: Session = Depends(get_db)):
    candidate_id = room_name.split("-")[1]
    room_id = room_name.split("-")[2]
    merged_report = merge_report_with_questions(test_report, scenario_json, room_id)
    print(merged_report)
    # тут сохранение в SQLite
    return {"message": "success get interview report"}


def merge_report_with_questions(report: Dict[str, Any],
                                scenarios: Dict[str, Any],
                                room_id: str,
                                question_key: str = "question") -> Dict[str, Any]:
    
    if room_id not in scenarios:
        raise KeyError(f"room_id='{room_id}' не найден в scenarios")
    
    scenario = scenarios[room_id]
    question_map: Dict[tuple, str] = {}
    
    for section_name, section_payload in scenario.items():
        if not isinstance(section_payload, dict):
            continue
        questions = section_payload.get("questions")
        if not isinstance(questions, list):
            continue
        for idx, q in enumerate(questions):
            if isinstance(q, dict) and question_key in q:
                question_text = q[question_key]
            else:
                # Если вопрос хранится не словарём, а строкой
                question_text = str(q)
            question_map[(section_name, idx)] = question_text
    
    # Регекс для ключей вида "section_index"
    key_re = re.compile(r"^(?P<section>[a-zA-Zа-яА-Я0-9_]+)_(?P<idx>\d+)$")
    
    merged: Dict[str, Any] = {}
    for k, v in report.items():
        m = key_re.match(k)
        if not m:
            # Ключ необычного формата — оставим как есть
            merged[k] = v
            continue
        
        section = m.group("section")
        idx = int(m.group("idx"))
        
        # Попытка прямого совпадения (как есть)
        q_text = question_map.get((section, idx))
        
        if q_text is None:
            # На всякий случай попробуем варианты с нормализацией:
            # 1) нижний регистр
            section_lower = section.lower()
            # 2) часто секции в сценарии в нижнем регистре — проверим
            q_text = question_map.get((section_lower, idx))
            if q_text is None:
                # 3) уберём неалфанум-символы (кроме подчеркивания) и попробуем снова
                norm = re.sub(r"[^a-zA-Zа-яА-Я0-9_]", "", section_lower)
                q_text = question_map.get((norm, idx))
        
        if q_text is None:
            # Вопрос не найден — сохраняем исходный ключ, чтобы ничего не потерять
            merged[k] = v
        else:
            merged[q_text] = v
    
    return merged