from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import json
import re

from api.db_models import Candidate, get_db

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


def _canonical_token(s: str) -> str:
    """Нормализуем имя секции до буквенно-цифровых, в нижнем регистре, без 'questions'."""
    s = s.lower()
    s = s.replace("questions", "").replace("question", "")
    return re.sub(r"[^a-z0-9]", "", s)


def _build_section_index(scenario: Dict[str, Any]) -> Dict[str, str]:
    """
    Строит индекс канонических имён -> фактическое имя секции из сценария.
    Добавляет полезные алиасы: general, hard/professional, soft.
    """
    idx: Dict[str, str] = {}
    for sec in scenario.keys():
        can = _canonical_token(sec)
        idx[can] = sec
        if "general" in can:
            idx.setdefault("general", sec)
        if "hard" in can or "professional" in can or "skill" in can:
            idx.setdefault("hard", sec)
            idx.setdefault("professional", sec)
        if "soft" in can:
            idx.setdefault("soft", sec)
    return idx


def merge_report_with_questions(report: Dict[str, Any],
                                scenario_payload: Dict[str, Any],
                                question_key: str = "question") -> Dict[str, Any]:
    """
    Соединяет результаты репорта с текстами вопросов из сценария.
    Ожидаем, что в scenario_payload секции содержат списки вопросов (list[dict|str]).
    Поддерживаем также вариант { "questions": [...] } внутри секции.
    """

    if not isinstance(scenario_payload, dict) or not scenario_payload:
        # Нечего мержить — вернём исходное
        return report

    # Построим карту (section_name, idx) -> question_text
    section_index = _build_section_index(scenario_payload)
    question_map: Dict[Tuple[str, int], str] = {}

    for sec_name, sec_value in scenario_payload.items():
        questions_list = None
        if isinstance(sec_value, list):
            questions_list = sec_value
        elif isinstance(sec_value, dict) and isinstance(sec_value.get("questions"), list):
            questions_list = sec_value["questions"]

        if not questions_list:
            continue

        for i, q in enumerate(questions_list):
            if isinstance(q, dict) and question_key in q:
                q_text = q[question_key]
            else:
                q_text = str(q)
            question_map[(sec_name, i)] = q_text

    # Регекс для ключей формата "section_index"
    key_re = re.compile(r"^(?P<section>[a-zA-Zа-яА-Я0-9_]+)_(?P<idx>\d+)$")

    merged: Dict[str, Any] = {}
    for k, v in report.items():
        m = key_re.match(k)
        if not m:
            merged[k] = v
            continue

        raw_section = m.group("section")
        idx = int(m.group("idx"))

        can = _canonical_token(raw_section)

        # Найдём фактическое имя секции из сценария
        real_section = (
            section_index.get(can)
            or section_index.get(raw_section.lower())
            or section_index.get(can.replace("professional", "hard"))
            or section_index.get(can.replace("hard", "professional"))
        )

        q_text = None
        if real_section is not None:
            q_text = question_map.get((real_section, idx))

        # Если вопрос не найден (например, индекс вне диапазона) — оставим ключ как есть
        if q_text is None:
            merged[k] = v
        else:
            merged[q_text] = v

    return merged


# ---------- endpoint ----------

@router.post("/interview_report")
def get_interview_report(room_name: str, report: dict, db: Session = Depends(get_db)):
    ids = _parse_ids_from_room(room_name)
    if not ids:
        raise HTTPException(status_code=400, detail="Invalid room_name format. Expected 'prefix-<candidate>-<vacancy>'.")

    candidate_id_str, vacancy_id_str = ids

    # подгружаем сценарий
    scenario_payload = _load_scenario(candidate_id_str, vacancy_id_str)
    if scenario_payload is None:
        raise HTTPException(status_code=400, detail="Invalid scenario (Not found).")
    else:
        merged_report = merge_report_with_questions(report["report"], scenario_payload)

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
