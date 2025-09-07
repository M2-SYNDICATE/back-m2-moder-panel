from pydantic import BaseModel, Field
from typing import List, Optional

# --- Для вакансии ---
# class JobPosting(BaseModel):
#     comment: str
#     answer: bool
#     name: str | None
#     experience: str
class Analysis(BaseModel):
    comment: str = Field(
        description="Обоснование, почему кандидат подходит или нет, основанное на сравнении резюме и вакансии."
    )
    name: Optional[str] = Field(
        description="Имя кандидата из резюме. Null, если не найдено."
    )
    experience: list = Field(
        description="Краткая выжимка релевантного опыта работы из резюме."
    )
    contact_data: Optional[list] = Field(
        description="Контакты для связи. Null, если не найдено."
        )
    answer: bool = Field(
        description="Подходит для работы да или нет. True or False"
        )


class CvValidationResult(BaseModel):
    analysis: Analysis = Field(
        description="Блок, содержащий рассуждения и извлеченные данные."
    )
    answer: bool = Field(
        description="Итоговое решение (True/False), принятое строго на основе поля 'comment' в блоке 'analysis'."
    )
# --- Новый класс для вопроса с примером ответа ---
class QuestionWithAnswer(BaseModel):
    question: str
    example_answer: Optional[str]

# --- Блоки вопросов ---
class GeneralQuestions(BaseModel):
    questions: List[QuestionWithAnswer]

class ProfessionalQuestions(BaseModel):
    questions: List[QuestionWithAnswer]

class ExperienceQuestions(BaseModel):
    questions: List[QuestionWithAnswer]

class SituationalQuestions(BaseModel):
    questions: List[QuestionWithAnswer]

class GrowthQuestions(BaseModel):
    questions: List[QuestionWithAnswer]

# --- Общий формат интервью ---
class InterviewQuestions(BaseModel):
    general: GeneralQuestions
    professional: ProfessionalQuestions
    experience: ExperienceQuestions
    situational: SituationalQuestions
    growth: GrowthQuestions