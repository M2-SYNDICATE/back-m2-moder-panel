# back/api/db_models.py
# (Новый файл: SQLAlchemy модели для БД)

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text, Enum
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

# Настройка БД (SQLite для примера)
DATABASE_URL = "sqlite:///./db.sqlite"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enums для статусов
class ResumeAnalysisStatus(str, enum.Enum):
    suitable = "suitable"
    not_suitable = "not_suitable"
    analyzing = "analyzing"

class CallStatus(str, enum.Enum):
    not_planned = "not_planned"
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    fio = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

class Vacancy(Base):
    __tablename__ = "vacancies"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)  # Путь к файлу info_cv
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    candidates = relationship("Candidate", back_populates="vacancy", cascade="all, delete-orphan")

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    vacancy_id = Column(Integer, ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    resume_filename = Column(String, nullable=False)  # Путь к файлу резюме
    resume_size = Column(Integer, nullable=True)  # В байтах
    resume_analysis = Column(Enum(ResumeAnalysisStatus), default=ResumeAnalysisStatus.analyzing)
    call_status = Column(Enum(CallStatus), default=CallStatus.not_planned)
    call_date = Column(DateTime, nullable=True)
    call_link = Column(String, nullable=True)
    ai_comments = Column(Text, nullable=True)  # Комментарий от ИИ
    ai_report = Column(Text, nullable=True)  # Отчет от ИИ
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    vacancy = relationship("Vacancy", back_populates="candidates")
    email = Column(String, nullable=True)
    total_score = Column(String, nullable=True)
    question_group_score = Column(String, nullable=True)

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Dependency для сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()