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
    # --- ИЗМЕНЕНИЕ 1: Уточняем, что фидбек должен быть коротким ---
    return [{"type": "function", "function": {"name": "evaluate_answer", "description": "Оценивает ответ кандидата.", "parameters": {"type": "object", "properties": {"score": {"type": "number"}, "passed": {"type": "boolean"}, "feedback": {"type": "string", "description": "Краткий (1-2 предложения) отзыв на русском."}}, "required": ["score", "passed", "feedback"]}}}]

def _create_evaluation_prompt(question: str, answer: str, expected_response: Optional[str], vacancy_name: str) -> str:
    expected_text = f"Критерии для идеального ответа: {expected_response}" if expected_response else "Четких критериев нет. Оцени ответ на основе логичности и полноты."
    # --- ИЗМЕНЕНИЕ 2: Добавляем требование к краткости фидбека ---
    return f"Ты — технический эксперт, оценивающий кандидата на позицию '{vacancy_name}'.\n{expected_text}\n\nПроанализируй связку вопрос-ответ и вызови `evaluate_answer`. **Твой отзыв (`feedback`) должен быть коротким и по существу (1-2 предложения).**\nВопрос: \"{question}\"\nОтвет: \"{answer}\""

# --- ИЗМЕНЕНИЕ 3: Новая функция для генерации итогового резюме ---
def _generate_final_summary(feedbacks: List[str], vacancy_name: str, client: OpenAI) -> str:
    if not feedbacks:
        return "Итоговое резюме не может быть составлено, так как не было получено ни одного отзыва."

    # Соединяем все фидбеки в один текст
    all_feedbacks_text = "\n- ".join(feedbacks)

    system_prompt = f"""Ты — опытный HR-менеджер. Проанализируй следующие краткие комментарии по ответам кандидата на позицию '{vacancy_name}'. 
На основе этих комментариев напиши короткую выжимку. Максимально короткую, не более 3-4 предложений в сумме.
Вот комментарии:
- {all_feedbacks_text}
"""
    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-r1-0528:free",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.2
            )
        summary = response.choices[0].message.content
        return summary.strip()
    except Exception as e:
        print(f"[ERROR] Не удалось сгенерировать итоговое резюме: {e}")
        return "Ошибка при генерации итогового резюме."



def analyze_interview_data(collected_data: Dict, questions_data: Dict, vacancy_name: str) -> Dict:
    print("\n--- НАЧАЛО ПОСЛЕДОВАТЕЛЬНОГО АНАЛИЗА РЕЗУЛЬТАТОВ ---")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    evaluation_tool = _create_evaluation_tool_definitions()
    
    analysis_report = []
    total_score = 0
    category_scores = {}
    all_feedbacks = [] # Собираем все фидбеки для итогового резюме

    all_questions = []
    for category, questions_list in questions_data.items():
        category_scores.setdefault(category, 0)
        for q in questions_list:
            all_questions.append({"category": category, "question": q.get("question"), "expected_response": q.get("expected_response")})


    for question_data in all_questions:
        category, question_text, expected_response = question_data["category"], question_data["question"], question_data["expected_response"]
        candidate_answer = next((ans["answer"] for ans in collected_data.get(category, []) if ans["question"] == question_text), None)
        
        evaluation = {}
        if candidate_answer is None:
            evaluation = {"score": 0, "passed": False, "feedback": "Ответ не был дан."}
        else:
            print(f"Анализирую ответ на вопрос: '{question_text[:40]}...'")
            system_prompt = _create_evaluation_prompt(question_text, candidate_answer, expected_response, vacancy_name)
            try:
                response = client.chat.completions.create(model="deepseek/deepseek-chat-v3.1:free", messages=[{"role": "system", "content": system_prompt}], tools=evaluation_tool, tool_choice={"type": "function", "function": {"name": "evaluate_answer"}})
                tool_args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
                evaluation = {"score": tool_args.get("score"), "passed": tool_args.get("passed"), "feedback": tool_args.get("feedback")}
                # --- ИЗМЕНЕНИЕ 4: Сохраняем фидбек в список ---
                if evaluation.get("feedback"):
                    all_feedbacks.append(evaluation["feedback"])
            except Exception as e:
                print(f"  - ОШИБКА при оценке: {e}")
                evaluation = {"error": str(e)}
        
        score = evaluation.get("score", 0)
        total_score += score
        category_scores[category] += score
        analysis_report.append({"category": category, "question": question_text, "expected_response": expected_response, "answer": candidate_answer or "Ответ не дан.", "evaluation": evaluation})
    
    # --- ИЗМЕНЕНИЕ 5: После цикла вызываем генерацию итогового резюме ---
    print("\nГенерирую итоговое резюме...")
    final_summary_text = _generate_final_summary(all_feedbacks, vacancy_name, client)

    print("\n--- АНАЛИЗ ЗАВЕРШЕН ---")
    
    score_summary = {"total_score": total_score, "scores_by_category": category_scores}
    
    return {
        "detailed_report": analysis_report,
        "score_summary": score_summary,
        "final_summary": final_summary_text # Добавляем резюме в итоговый отчет
    }


