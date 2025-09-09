from typing import Optional, Dict, List
from openai import OpenAI
from dotenv import load_dotenv
import os
import json

load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("Не найден API ключ OPENROUTER_API_KEY")

def _create_evaluation_tool_definitions():
    """Возвращает инструмент для детальной ОЦЕНКИ ответа."""
    return [{"type": "function", "function": {"name": "evaluate_answer", "description": "Оценивает ответ кандидата.", "parameters": {"type": "object", "properties": {"score": {"type": "number"}, "passed": {"type": "boolean"}, "feedback": {"type": "string"}}, "required": ["score", "passed", "feedback"]}}}]

def _create_evaluation_prompt(question: str, answer: str, expected_response: Optional[str], vacancy_name: str) -> str:
    """Создает системный промпт для оценки ответа."""
    expected_text = f"Критерии для идеального ответа: {expected_response}" if expected_response else "Четких критериев нет. Оцени ответ на основе логичности и полноты."
    return f"Ты — технический эксперт, оценивающий кандидата на позицию '{vacancy_name}'. Твоя задача — объективно оценить ответ кандидата.\n{expected_text}\n\nПроанализируй связку вопрос-ответ и вызови инструмент `evaluate_answer`.\nВопрос: \"{question}\"\nОтвет кандидата: \"{answer}\""

def analyze_interview_data(collected_data: Dict, questions_data: Dict, vacancy_name: str) -> List[Dict]:
    """
    Анализирует собранные результаты, последовательно выставляя оценки каждому ответу.
    """
    print("\n--- НАЧАЛО ПОСЛЕДОВАТЕЛЬНОГО АНАЛИЗА РЕЗУЛЬТАТОВ ---")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    evaluation_tool = _create_evaluation_tool_definitions()
    analysis_report = []

    all_questions = []
    for category, questions_list in questions_data.items():
        for q in questions_list:
            all_questions.append({
                "category": category,
                "question": q.get("question"),
                "expected_response": q.get("expected_response")
            })

    for question_data in all_questions:
        category, question_text, expected_response = question_data["category"], question_data["question"], question_data["expected_response"]
        candidate_answer = next((ans["answer"] for ans in collected_data.get(category, []) if ans["question"] == question_text), None)
        
        evaluation = {}
        if candidate_answer is None:
            print(f"Вопрос '{question_text[:40]}...' пропущен.")
            evaluation = {"score": 0, "passed": False, "feedback": "Ответ не был дан."}
        else:
            print(f"Анализирую ответ на вопрос: '{question_text[:40]}...'")
            system_prompt = _create_evaluation_prompt(question_text, candidate_answer, expected_response, vacancy_name)
            try:
                response = client.chat.completions.create(model="deepseek/deepseek-chat-v3.1:free", messages=[{"role": "system", "content": system_prompt}], tools=evaluation_tool, tool_choice={"type": "function", "function": {"name": "evaluate_answer"}})
                tool_args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
                evaluation = {"score": tool_args.get("score"), "passed": tool_args.get("passed"), "feedback": tool_args.get("feedback")}
            except Exception as e:
                print(f"  - ОШИБКА при оценке: {e}")
                evaluation = {"error": str(e)}
        
        analysis_report.append({
            "category": category,
            "question": question_text,
            "expected_response": expected_response,
            "answer": candidate_answer or "Ответ не дан.",
            "evaluation": evaluation
        })
    
    print("\n--- АНАЛИЗ ЗАВЕРШЕН ---")
    return analysis_report
