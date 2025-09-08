# api/scripts/m2/scenario_generator.py
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
from api.scripts.m1.convert_functions import convert_to_dict, convert_to_text
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import translitua
import re
from pathlib import Path

import tempfile

load_dotenv()

def generate_for_single_candidate(
    info_cv_path: str,
    json_path: str,
    cv_path_key: str,
    out_dir: str,
    scenario_filename: str,
) -> Path:
    """
    Берёт общий JSON Модуля 1, фильтрует записи до одного кандидата (по ключу cv_path),
    вызывает основной генератор и сохраняет сценарий как <candidate_id>_<vacancy_id>.json.
    """
    # Подготовим временный JSON только с одним кандидатом
    with open(json_path, "r", encoding="utf-8") as f:
        full_payload = json.load(f)

    single_payload = {cv_path_key: full_payload[cv_path_key]}

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tmp:
        json.dump(single_payload, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name

    # используем уже существующую функцию сохранения сценария
    return generate_and_save_scenario(
        info_cv_path=info_cv_path,
        json_path=tmp_path,
        out_dir=out_dir,
        scenario_filename=scenario_filename,
    )

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("Не найден API ключ OPENROUTER_API_KEY")


class Question(BaseModel):
    question: str = Field(description="Текст вопроса для собеседования.")
    expected_response: Optional[str] = Field(
        description="Возможный ожидаемый ответ кандидата на основе CV."
    )


class InterviewQuestions(BaseModel):
    general_questions: List[Question] = Field(
        description="Общие вопросы: опыт работы, зарплатные ожидания и т.д."
    )
    hard_skills_questions: List[Question] = Field(
        description="Вопросы на проверку hard skills"
    )
    soft_skills_questions: List[Question] = Field(
        description="Вопросы на проверку soft skills"
    )


# --- Транслитерация для TTS ---
custom_translit_map = {
    "Excel": "Эксель",
    "Word": "Ворд",
    "Visio": "Визио",
    "BIOS": "БИОС",
    "BMC": "Би-Эм-Си",
    "RAID": "Рейд",
    "CMDB": "Си-Эм-Ди-Би",
    "DCIM": "Ди-Си-Ай-Эм",
    "IPMI": "Ай-Пи-Эм-Ай",
    "LAN": "Лан",
    "SAN": "Сан",
}

def transliterate_word(word):
    for k, v in custom_translit_map.items():
        if k.lower() == word.lower():
            return v
    return translitua.translit(word)

def process_question_for_tts(question_text: str) -> str:
    latin_words = re.findall(r'[a-zA-Z-]{2,}', question_text)
    processed_text = question_text
    for word in set(latin_words):
        transliterated = transliterate_word(word)
        processed_text = re.sub(r'\b' + re.escape(word) + r'\b', transliterated, processed_text)
    return processed_text
# --- конец блока TTS ---


def _prompt_question_block(info: dict, cv_text: str):
    prompt_content = f"""
    Описание вакансии: {info}
    Текст резюме кандидата: {cv_text}

    Сгенерируй около 15 вопросов для первичного HR-собеседования в общей сложности.
    Раздели вопросы на три категории:
    - general_questions: 3-5 общих вопросов.
    - hard_skills_questions: вопросы по hard skills на основе вакансии и CV.
    - soft_skills_questions: вопросы по soft skills.

    Регулируй баланс в зависимости от типа вакансии.
    expected_response заполняй только для hard_skills и general_questions. В soft_skills — null.

    ВАЖНО: используй ТОЛЬКО РУССКИЙ ЯЗЫК, никакой латиницы/английских терминов.
    """
    return [
        {"role": "system", "content": "Ты — HR-ассистент, генерирующий вопросы для собеседования на основе вакансии и CV."},
        {"role": "user", "content": prompt_content},
    ]


def question_block(info_cv_path: str, json_path: str) -> Dict[str, Any]:
    """
    Обрабатывает JSON с анализами CV, генерирует блоки вопросов для тех, у кого answer=true.
    info_cv_path: путь к описанию вакансии/требований (поддерживает convert_to_dict)
    json_path: JSON из модуля 1 (invo_cv_text), где ключи — пути к CV, а value.answer — флаг
    """
    info, _ = convert_to_dict(info_cv_path)

    with open(json_path, 'r', encoding='utf-8') as f:
        invo_cv = json.load(f)

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    result: Dict[str, Any] = {}
    for cv_path, data in invo_cv.items():
        if data.get("answer", False):
            cv_text = convert_to_text(cv_path, file_num=0)

            response = client.chat.completions.parse(
                model="deepseek/deepseek-r1-0528:free",
                messages=_prompt_question_block(info=info, cv_text=cv_text),
                response_format=InterviewQuestions,
                temperature=0.1,
                top_p=0.95,
            )

            questions: InterviewQuestions = response.choices[0].message.parsed

            # пост-обработка для TTS, чтобы не проскочила латиница
            for q_list in [questions.general_questions, questions.hard_skills_questions, questions.soft_skills_questions]:
                for item in q_list:
                    item.question = process_question_for_tts(item.question)

            result[cv_path] = questions.model_dump()
        else:
            result[cv_path] = None
    print("RESULT: ", result)
    return result


def generate_and_save_scenario(
    info_cv_path: str,
    json_path: str,
    out_dir: str | Path,
    scenario_filename: str,
) -> Path:
    """
    Генерирует сценарий и сохраняет его в out_dir/scenario_filename (JSON).
    Возвращает путь к файлу.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scenario = question_block(info_cv_path=info_cv_path, json_path=json_path)
    out_path = out_dir / scenario_filename
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(scenario, f, ensure_ascii=False, indent=2)
    return out_path
