from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import os
import shutil
import smtplib
from email.message import EmailMessage
from pathlib import Path

from api.db_models import Candidate, Vacancy, get_db, CallStatus
from api.models import RoomName

router = APIRouter(tags=["report"])

# BASE_REPORT_DIR = Path(__file__).parent.parent / "data" / "reports"

@router.post("/interview_report")
def get_scenario(report: dict, db: Session = Depends(get_db)):

    print(report)
    return {"message": "success get interview report"}