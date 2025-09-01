from api.models import Module2Input
# (Заглушка для модуля 2)

def run_module2(data: Module2Input) -> dict[str, dict[str, bool]]:
    # Здесь в будущем будет AI-логика
    # Пока возвращаем примерные данные
    question_dict = {
        "question_category1": {
            "question1": False,
            "questionN": True
        },
        "question_categoryN": {
            "question1": False,
            "questionN": True
        }
    }
    return question_dict