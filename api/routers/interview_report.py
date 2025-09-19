from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import json
import re
from api.scripts.report_analize import analyze_interview_data
from rich import print
import concurrent.futures
from api.db_models import Candidate, Vacancy, get_db
import math

router = APIRouter(tags=["report"])

SCENARIO_DIR = Path(__file__).parent.parent / "data" / "scenario"
TIMEOUT_SECONDS = 180  # 3 минуты
MAX_RETRIES = 3

# ---------- helpers ----------
def _report_score_processing(report: dict):
    detailed_report = report.get("detailed_report", [])
    scores_by_category_raw = {}

    # Собираем баллы по категориям
    for item in detailed_report:
        category = item["category"]
        score = item["evaluation"]["score"]
        if category not in scores_by_category_raw:
            scores_by_category_raw[category] = []
        scores_by_category_raw[category].append(score)

    # Считаем суммы по категориям
    category_totals = {cat: sum(scores) for cat, scores in scores_by_category_raw.items()}

    # Получаем список уникальных категорий в порядке их появления
    ordered_categories = list(dict.fromkeys(item["category"] for item in detailed_report))

    # Считаем максимальные баллы по каждой категории (по 10 за каждый вопрос)
    max_scores_by_category = {}
    for item in detailed_report:
        category = item["category"]
        if category not in max_scores_by_category:
            max_scores_by_category[category] = 0
        max_scores_by_category[category] += 10  # каждый вопрос оценивается до 10

    # Переводим баллы в 10-балльную шкалу по каждой категории и округляем вниз
    scores_by_category_10 = []
    for cat in ordered_categories:
        total = category_totals.get(cat, 0)
        max_total = max_scores_by_category.get(cat, 1)  # избегаем деления на 0
        score_10 = (total / max_total) * 10 if max_total > 0 else 0
        scores_by_category_10.append(math.floor(score_10))

    # Общий скор: сумма всех баллов / максимальный возможный * 10
    total_gained = sum(category_totals.values())
    total_possible = sum(max_scores_by_category.values())
    total_score_10 = (total_gained / total_possible) * 10 if total_possible > 0 else 0
    total_score_10 = math.floor(total_score_10)

    return total_score_10, scores_by_category_10

def _call_with_timeout(func, *args, timeout: int = TIMEOUT_SECONDS):
    """Вызывает sync-функцию с таймаутом через отдельный поток."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as e:
            # Попробуем отменить, чтобы не держать поток (если ещё возможно)
            future.cancel()
            raise e

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
    vacancy = db.query(Vacancy).filter(Vacancy.id == int(vacancy_id_str)).first()


    # подгружаем сценарий
    scenario_payload = _load_scenario(candidate_id_str, vacancy_id_str)
    if scenario_payload is None:
        raise HTTPException(status_code=400, detail="Invalid scenario (Not found).")

    # анализ с таймаутом и автоперезапуском при зависании
    attempts = 0
    last_error = None
    while attempts <= MAX_RETRIES:
        try:
            merged_report = _call_with_timeout(
                analyze_interview_data,
                report,
                scenario_payload,
                vacancy.title if vacancy else None,
                timeout=TIMEOUT_SECONDS,
            )
            break  # успех
        except concurrent.futures.TimeoutError:
            attempts += 1
            print("[yellow bold]analyze_interview_data timed out (attempt %d/%d)", attempts, MAX_RETRIES + 1)
            last_error = "Timeout"
            if attempts > MAX_RETRIES:
                raise HTTPException(
                    status_code=504,
                    detail=f"analyze_interview_data timed out after {TIMEOUT_SECONDS//60} minutes (retried {MAX_RETRIES} time(s)).",
                )
        except Exception as e:
            # Любая другая ошибка — сразу 500
            print("[red bold on white]analyze_interview_data failed: %s", e)
            raise HTTPException(status_code=500, detail="Failed to analyze interview data")

    # пишем в БД
    try:
        candidate_id = int(candidate_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate id in room_name")

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    print(merged_report)
    total_score, group_score_list = _report_score_processing(report)
    candidate.ai_report = json.dumps(merged_report, ensure_ascii=False)
    candidate.call_status = "completed"
    candidate.total_score = str(total_score)
    candidate.question_group_score = json.dumps(group_score_list)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return {"message": "success get interview report"}
