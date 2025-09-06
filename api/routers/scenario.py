from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import os
import smtplib
from email.message import EmailMessage

from api.db_models import Candidate, Vacancy, get_db, CallStatus
from api.models import CandidateInvite

router = APIRouter(prefix="/crud/scenario", tags=["scenario"])