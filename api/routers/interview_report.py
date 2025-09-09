from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import json
import re
from api.scripts.report_analize import analyze_interview_data
from rich import print

from api.db_models import Candidate, Vacancy, get_db

router = APIRouter(tags=["report"])

SCENARIO_DIR = Path(__file__).parent.parent / "data" / "scenario"


# ---------- helpers ----------

def _parse_ids_from_room(room_name: str) -> Optional[Tuple[str, str]]:
    """
    Ожидаемый формат: 'prefix-<candidate_id>-<vacancy_id>'.
    Префикс может содержать дефисы — берём две последние части.
    """
    if not room_name:
        return None
    parts = room_name.split("-")
    if len(parts) < 3:
        return None
    return parts[-2], parts[-1]


def _load_scenario(candidate_id: str, vacancy_id: str) -> Optional[Dict[str, Any]]:
    """
    Загружает payload сценария из файла <candidate_id>_<vacancy_id>.json.
    Игнорирует верхний ключ и возвращает первое значение-объект.
    """
    file_path = SCENARIO_DIR / f"{candidate_id}_{vacancy_id}.json"
    if not file_path.exists() or not file_path.is_file():
        return None

    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    if isinstance(data, dict) and data:
        first_value = next(iter(data.values()))
        if isinstance(first_value, dict):
            return first_value
        # если вдруг структура другая — вернём как есть
        return data
    return None


# ---------- endpoint ----------

@router.post("/interview_report")
def get_interview_report(room_name: str, report: dict, db: Session = Depends(get_db)):
    ids = _parse_ids_from_room(room_name)
    if not ids:
        raise HTTPException(status_code=400, detail="Invalid room_name format. Expected 'prefix-<candidate>-<vacancy>'.")

    candidate_id_str, vacancy_id_str = ids
    vacancy_title = db.query(Vacancy).filter(Vacancy.id == int(vacancy_id_str)).first()
    # подгружаем сценарий
    scenario_payload = _load_scenario(candidate_id_str, vacancy_id_str)
    if scenario_payload is None:
        raise HTTPException(status_code=400, detail="Invalid scenario (Not found).")
    else:
        merged_report = analyze_interview_data(report, scenario_payload, vacancy_title.title)
        print(merged_report)
    # пишем в БД
    try:
        candidate_id = int(candidate_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate id in room_name")

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.ai_report = json.dumps(merged_report, ensure_ascii=False)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return {"message": "success get interview report"}
