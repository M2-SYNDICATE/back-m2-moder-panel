from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Any
from enum import Enum
import json
import os
from dotenv import load_dotenv
from api.scripts.m2.module2 import module2_result_test

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("Не найден API ключ OPENROUTER_API_KEY")


class InterviewState:
    # Этот класс остаётся без изменений
    def __init__(self, questions_data: Dict):
        self.questions_data = questions_data
        self.current_category = None
        self.current_question_index = 0
        self.question_results = {}
        self.conversation_history = []
        self.total_score = 0
        self.questions_asked = 0
        self.all_questions = []
        for category, data in questions_data.items():
            for i, q in enumerate(data["questions"]):
                question_id = f"{category}_{i}"
                self.all_questions.append({
                    "id": question_id,
                    "category": category,
                    "question": q["question"],
                    "example_answer": q["example_answer"]
                    })

    def get_current_question(self):
        if self.questions_asked < len(self.all_questions):
            return self.all_questions[self.questions_asked]
        return None

    def mark_question_result(self, question_id: str, passed: bool, score: float):
        self.question_results[question_id] = {"passed": passed, "score": score}
        self.total_score += score

    def move_to_next_question(self):
        self.questions_asked += 1

    def is_interview_complete(self):
        return self.questions_asked >= len(self.all_questions)


class AIHRPipeline:
    def __init__(self, questions_data: Dict):
        self.state = InterviewState(questions_data)
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        self.unified_tool = create_unified_tool_definitions()
        self.model_name = "deepseek/deepseek-chat-v3.1:free"

    # --- ЕДИНСТВЕННОЕ ИЗМЕНЕНИЕ: Новый, более детальный и умный промпт ---
    def create_system_prompt(self, current_question: Dict) -> str:
        return f"""Ты — умный и вежливый AI HR-интервьюер. Твоя задача — вызвать инструмент `process_response`, проанализировав ответ кандидата.
Текущий вопрос: {current_question['question']}

**ШАГ 1: КЛАССИФИКАЦИЯ ОТВЕТА**
- `ANSWER`: Кандидат предоставляет информацию по теме вопроса. "не знаю" — это тоже финальный `ANSWER`. 
- `UNCERTAIN`: Кандидат растерян, к примеру "не знаю что сказать" просит уточнение или говорит не по теме ("меня слышно?").
- `REPEAT_REQUEST`: Прямая просьба повторить вопрос.

**ШАГ 2: ПРАВИЛА ФОРМИРОВАНИЯ `message` для кандидата**
- **Если это `ANSWER`**: Твоё `message` — это краткий, вежливый комментарий. **Не включай следующий вопрос.**
- **Если это `REPEAT_REQUEST`**: Твоё `message` должно начинаться с "Конечно, повторяю вопрос:" или другой фразы и затем содержать полный текст текущего вопроса.
- **Если это `UNCERTAIN`**: Это самый важный случай. Твоя задача — помочь кандидату. Сделай это очень кратко. Не более двух предложений. Сгенерируй краткую **подсказку, уточнение или ободряющую фразу** в зависимости от запроса.

**ШАГ 3: ПРАВИЛА ОЦЕНКИ**
- Только если `response_type` == 'ANSWER', ты ОБЯЗАН заполнить `score` и `passed`. В остальных случаях — не заполняй.
"""

    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        current_question = self.state.get_current_question()
        if not current_question:
            return {"message": "Собеседование завершено! Спасибо.", "interview_complete": True,
                    "final_score": self.state.total_score, "results": self.state.question_results}

        messages = [
            {"role": "system", "content": self.create_system_prompt(current_question)},
            {"role": "user", "content": user_input}
            ]

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.unified_tool,
                tool_choice={"type": "function", "function": {"name": "process_response"}},
                temperature=0.1
                )
            tool_args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        except Exception as e:
            print(f"[ERROR] Ошибка вызова API или парсинга: {e}")
            return {"message": "Произошла внутренняя ошибка. Пожалуйста, попробуйте еще раз."}

        response_type = tool_args.get("response_type")
        action = None

        final_response = {
            "message": tool_args.get("message", "Что-то пошло не так."),
            "interview_complete": False
            }

        if response_type == "ANSWER":
            action = "next_question"
            self.state.mark_question_result(
                question_id=current_question["id"],
                passed=tool_args.get("passed", False),
                score=tool_args.get("score", 0)
                )
            self.state.move_to_next_question()
            next_q = self.state.get_current_question()
            if next_q:
                final_response["next_question"] = next_q["question"]
            else:
                final_response["interview_complete"] = True
                final_response["message"] += "\n\nЭто был последний вопрос. Собеседование завершено."
                final_response["final_score"] = self.state.total_score
                final_response["results"] = self.state.question_results

        elif response_type == "REPEAT_REQUEST":
            action = "repeat_question"

        elif response_type == "UNCERTAIN":
            action = "stay_on_question"

        final_response["action"] = action
        return final_response

    def start_interview(self) -> str:
        first_question = self.state.get_current_question()
        return f"Добро пожаловать на собеседование! Давайте начнем.\n\n{first_question['question']}"


def create_unified_tool_definitions():
    # Инструмент не меняется
    return [{
        "type": "function",
        "function": {
            "name": "process_response",
            "description": "Классифицирует и (если нужно) оценивает ответ кандидата.",
            "parameters": {
                "type": "object",
                "properties": {
                    "response_type": {"type": "string", "enum": ["ANSWER", "UNCERTAIN", "REPEAT_REQUEST"]},
                    "message": {"type": "string",
                                "description": "Полный, самодостаточный ответ для кандидата (на русском)."},
                    "score": {"type": "number",
                              "description": "Оценка от 0 до 10. Только для `response_type`='ANSWER'."},
                    "passed": {"type": "boolean",
                               "description": "Справился ли кандидат. Только для `response_type`='ANSWER'."}
                    },
                "required": ["response_type", "message"]
                }
            }
        }]


if __name__ == '__main__':
    pipeline = AIHRPipeline(module2_result_test)
    print(pipeline.start_interview())
    while True:
        try:
            user_input = input("\nКандидат: ")
            if user_input.lower() in ['quit', 'exit', 'завершить']:
                print("Интервью завершено по команде пользователя.")
                break
            result = pipeline.process_user_input(user_input)

            print(f"\nИнтервьюер: {result['message']}")

            if result.get('interview_complete'):
                print(f"\nИнтервью завершено.")
                if 'final_score' in result:
                    print(f"\nИтоговый балл: {result.get('final_score', 0)}")
                    print("Результаты по вопросам:")
                    for q_id, res in result.get('results', {}).items():
                        print(f"  {q_id}: {'✓' if res['passed'] else '✗'} (Score: {res['score']}/10)")
                break

            # Логика Python-кода остается такой же простой и правильной
            if result.get('action') == 'next_question' and 'next_question' in result:
                print(f"\nСледующий вопрос: {result['next_question']}")

        except Exception as e:
            print(f"\nПроизошла ошибка: {e}")
            print("Пожалуйста, попробуйте еще раз или завершите интервью.")