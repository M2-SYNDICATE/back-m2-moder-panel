from fastapi import APIRouter
from api.models import RoomName
from pathlib import Path
import json
from typing import Optional, Any




router = APIRouter(prefix="/scenario", tags=["scenario"])

SCENARIO_DIR = Path(__file__).parent.parent / "data" / "scenario"

def _parse_ids_from_room(room_name: str) -> Optional[tuple[str, str]]:
    """
    Ожидается формат: 'prefix-<candidate_id>-<vacancy_id>'.
    Префикс может содержать дефисы. Берём две последние части.
    """
    if not room_name:
        return None
    parts = room_name.split("-")
    if len(parts) < 3:
        return None
    candidate_id, vacancy_id = parts[-2], parts[-1]
    if not candidate_id or not vacancy_id:
        return None
    return candidate_id, vacancy_id


def _load_scenario(candidate_id: str, vacancy_id: str) -> Optional[Any]:
    """
    Читает файл <candidate_id>_<vacancy_id>.json из SCENARIO_DIR.
    Игнорирует верхний ключ и возвращает его значение.
    """
    file_path = SCENARIO_DIR / f"{candidate_id}_{vacancy_id}.json"
    if not file_path.exists() or not file_path.is_file():
        return None

    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    # В ваших файлах верхний уровень — dict { "<какой-то ключ>": <нужный объект> }
    if isinstance(data, dict) and data:
        # Берём ПЕРВОЕ значение и игнорируем ключ, как и требуется
        return next(iter(data.values()))
    # На всякий случай, если структура иная — вернём как есть
    return data


@router.post("/get_scenario")
def get_scenario(room: RoomName):
    ids = _parse_ids_from_room(room.room)
    if not ids:
        return {"scenario": None}

    candidate_id, vacancy_id = ids
    scenario = _load_scenario(candidate_id, vacancy_id)
    return {"scenario": scenario if scenario is not None else None}