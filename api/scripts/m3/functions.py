def create_function_definitions():
    return [
        {
            "name": "analyze_user_response",
            "description": "Analyze the user's response to determine its type and quality",
            "parameters": {
                "type": "object",
                "properties": {
                    "response_type": {
                        "type": "string",
                        "enum": ["answered", "repeat_request", "clarification_request", "irrelevant"],
                        "description": "Type of user response"
                    },
                    "answer_quality": {
                        "type": "string",
                        "enum": ["good", "poor", "incomplete"],
                        "description": "Quality of answer if response_type is 'answered'"
                    },
                    "confidence_score": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Confidence in the analysis"
                    },
                    "key_points_mentioned": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key technical points mentioned by the candidate"
                    },
                    "missing_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Important points missing from the answer"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Explanation of the analysis"
                    }
                },
                "required": ["response_type", "confidence_score", "key_points_mentioned", "missing_points", "reasoning"]
            }
        },
        {
            "name": "determine_next_action",
            "description": "Determine what action to take next in the interview",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["next_question", "repeat_question", "ask_clarification", "probe_deeper"],
                        "description": "What action to take next"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message to send to the candidate"
                    },
                    "question_id": {
                        "type": "string",
                        "description": "ID of the question to move to (if next_question)"
                    }
                },
                "required": ["action", "message"]
            }
        },
        {
            "name": "mark_question_result",
            "description": "Mark the current question as passed or failed",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_id": {
                        "type": "string",
                        "description": "ID of the question being marked"
                    },
                    "passed": {
                        "type": "boolean",
                        "description": "Whether the candidate passed this question"
                    },
                    "score": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 10.0,
                        "description": "Score for this question (0-10)"
                    },
                    "feedback": {
                        "type": "string",
                        "description": "Detailed feedback on the answer"
                    }
                },
                "required": ["question_id", "passed", "score", "feedback"]
            }
        }
    ]