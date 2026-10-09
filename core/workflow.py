import time
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

class StepStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class TimelineEvent(BaseModel):
    step_name: str
    status: StepStatus
    agent_name: str
    message: str
    timestamp: float = Field(default_factory=time.time)
    duration_ms: Optional[float] = None

class WorkflowState(BaseModel):
    session_id: str
    image_path: Optional[str] = None
    image_metadata: Dict[str, Any] = {}
    raw_vision_output: Optional[Dict[str, Any]] = None
    database_schema: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
    refinement_iterations: int = 0
    generated_artifacts: Dict[str, Any] = {}
    timeline: List[TimelineEvent] = []
    error_message: Optional[str] = None

    def add_event(self, step_name: str, agent_name: str, message: str, status: StepStatus = StepStatus.COMPLETED, duration_ms: Optional[float] = None):
        event = TimelineEvent(
            step_name=step_name,
            agent_name=agent_name,
            message=message,
            status=status,
            duration_ms=duration_ms
        )
        self.timeline.append(event)
