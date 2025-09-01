from api.models import Module4Input
# (Заглушка для модуля 4)

def run_module4(data: Module4Input) -> dict[str, float]:
    # Здесь в будущем будет AI-логика для расчета скора
    # Пока возвращаем средние значения
    question_dict_result = {}
    for category, questions in data.question_dict_updated.items():
        true_count = sum(questions.values())
        total = len(questions)
        score = true_count / total if total > 0 else 0.0
        question_dict_result[category] = score
    return question_dict_result