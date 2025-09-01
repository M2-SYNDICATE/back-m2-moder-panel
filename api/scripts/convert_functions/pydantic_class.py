from pydantic import BaseModel
from typing import List, Optional

# --- Для вакансии ---
class JobPosting(BaseModel):
    comment: str
    answer: bool
    name: str | None

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