# back/api/models.py

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class Module1Input(BaseModel):
    """
    Input for Module1: validating all cv hr loaded to folder_cv_path via info about vacancy.

    `folder_cv_path`:  folder with all CV loaded for selected info_cv

    `info_cv_path`:  path for vacancy describe

    `result`: dict `{link_to_cv:{answer:bool, comment:str}}`, additionally info_dict for module 2
    """
    folder_cv_path: str =""
    infocv_path: str = ""

class Module1Output(BaseModel):
    """
    Output для Module1: Обработка входящих резюме.
    """
    return_description: Dict[str, str]
    return_dict: Dict[str, bool]

class Module2Input(BaseModel):
    """
    Input для Module2: Генерация question_dict на основе return_description.
    """
    return_description: Dict[str, str]

class Module2Output(BaseModel):
    """
    Output для Module2: Генерация question_dict на основе return_description.
    """
    question_dict: Dict[str, Dict[str, bool]]

class Module3Input(BaseModel):
    """
    Input для Module3: Обработка для конкретного PDF с промптом и question_dict.
    """
    link_pdf_resume: str
    prompt: str
    question_dict: Dict[str, Dict[str, bool]]

class Module3Output(BaseModel):
    """
    Output для Module3: Обработка для конкретного PDF с промптом и question_dict.
    """
    link_pdf_resume: str
    question_dict_updated: Dict[str, Dict[str, bool]]  # Предполагаем структуру как в module2

class Module4Input(BaseModel):
    """
    Input для Module4: Финальный расчет на основе обновленного question_dict.
    """
    link_pdf_resume: str
    question_dict_updated: Dict[str, Dict[str, bool]]

class Module4Output(BaseModel):
    """
    Output для Module4: Финальный расчет на основе обновленного question_dict.
    """
    question_dict_result: Dict[str, float]


# Enums для статусов
class ResumeAnalysisStatus(str, Enum):
    suitable = "suitable"
    not_suitable = "not_suitable"
    analyzing = "analyzing"

class CallStatus(str, Enum):
    not_planned = "not_planned"
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"

# Для _ЛОГИН_ POST (регистрация)
class UserRegister(BaseModel):
    fullName: str
    email: str
    password: str

# Для логина (аутентификация)
class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    userEmail: str
    fullName: str

# Для _ВАКАНСИИ_ GET (элемент)
class VacancyResponse(BaseModel):
    id: int
    title: str
    fileName: str  # filename

# Для _КАНДИДАТЫ_ GET (элемент)
class CandidateListResponse(BaseModel):
    id: int
    fullName: str
    vacancyId: int
    resumeAnalysis: ResumeAnalysisStatus
    callStatus: CallStatus
    callDate: Optional[datetime]

# Для _КАНДИДАТ_ GET
class CandidateDetailResponse(BaseModel):
    id: int
    title: str  # e.g. 'Иванов Иван / Java Developer'
    vacancy: str  # Название вакансии
    callDate: Optional[datetime]
    callLink: Optional[str]
    comments: Optional[str]  # ai_comments
    resume: dict  # {name: str, size: int, uploadDate: datetime}
    resumeAnalysis: ResumeAnalysisStatus
    callStatus: CallStatus
    createdAt: datetime
    ai_report: Optional[str]  # Отчет от ИИ

# Для _СОЗДАТЬ ВАКАНСИЮ_ POST
# (Файл загружается отдельно через UploadFile)

# Для _ДОБАВИТЬ КАНДИДАТА_ POST
class AddCandidateRequest(BaseModel):
    vacancy_title: str  # Название вакансии (для поиска vacancy_id)
    # Файлы резюме через UploadFile в эндпоинте

class CandidateInvite(BaseModel):
    candidate_id: int
    email: str




