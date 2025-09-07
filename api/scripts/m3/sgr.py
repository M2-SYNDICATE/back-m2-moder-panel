from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Any
from enum import Enum
class ResponseType(str, Enum):
    ANSWERED = "answered"
    REPEAT_REQUEST = "repeat_request"
    CLARIFICATION_REQUEST = "clarification_request"
    IRRELEVANT = "irrelevant"

class AnswerQuality(str, Enum):
    GOOD = "good"
    POOR = "poor"
    INCOMPLETE = "incomplete"

class UserResponseAnalysis(BaseModel):
    response_type: ResponseType = Field(description="Type of user response")
    answer_quality: Optional[AnswerQuality] = Field(
        default=None,
        description="Quality of answer if response_type is 'answered'"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the analysis (0-1)"
    )
    key_points_mentioned: List[str] = Field(
        description="Key technical points mentioned by the candidate"
    )
    missing_points: List[str] = Field(
        description="Important points missing from the answer"
    )
    reasoning: str = Field(description="Explanation of the analysis")

class NextAction(BaseModel):
    action: Literal["next_question", "repeat_question", "ask_clarification", "probe_deeper"] = Field(
        description="What action to take next"
    )
    message: str = Field(description="Message to send to the candidate")
    question_id: Optional[str] = Field(
        default=None,
        description="ID of the question to move to (if next_question)"
    )