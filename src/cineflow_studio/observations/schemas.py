"""Pydantic schemas for FrameObservation and plan conformance (Issue #93)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ViewerSide = Literal["left", "center", "right", "unknown"]
FaceVisibility = Literal["visible", "partial", "hidden", "unknown"]
MouthVisibility = Literal["open", "closed", "obscured", "unknown"]

# Mouth visibility never implies dialogue authority (ScriptLine / TTS binding does).
FORBIDDEN_SPEAKING_KEYS = frozenset(
    {
        "speaking",
        "is_speaking",
        "speaking_role",
        "active_speaker",
        "speaker",
        "is_speaker",
        "talking",
        "is_talking",
    }
)


class CharacterCandidate(BaseModel):
    """Grounded identity guess. Keep character_id null when ambiguous."""

    character_id: str | None = None
    label: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: Any) -> float | None:
        if value is None or value == "" or value == "unknown":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number < 0.0 or number > 1.0:
            return None
        return number


class SubjectObservation(BaseModel):
    subject_index: int = 0
    visual_description: str = ""
    character_candidates: list[CharacterCandidate] = Field(default_factory=list)
    viewer_relative_position: ViewerSide = "unknown"
    pose: str | None = None
    contact: str | None = None
    face_visibility: FaceVisibility = "unknown"
    mouth_visibility: MouthVisibility = "unknown"

    @field_validator("viewer_relative_position", mode="before")
    @classmethod
    def _side(cls, value: Any) -> str:
        token = str(value or "unknown").strip().lower()
        if token in {"left", "center", "right", "unknown"}:
            return token
        if token in {"l", "camera-left", "frame-left"}:
            return "left"
        if token in {"r", "camera-right", "frame-right"}:
            return "right"
        if token in {"c", "middle"}:
            return "center"
        return "unknown"

    @field_validator("face_visibility", mode="before")
    @classmethod
    def _face(cls, value: Any) -> str:
        token = str(value or "unknown").strip().lower()
        if token in {"visible", "partial", "hidden", "unknown"}:
            return token
        return "unknown"

    @field_validator("mouth_visibility", mode="before")
    @classmethod
    def _mouth(cls, value: Any) -> str:
        token = str(value or "unknown").strip().lower()
        if token in {"open", "closed", "obscured", "unknown"}:
            return token
        return "unknown"

    @field_validator("pose", "contact", mode="before")
    @classmethod
    def _optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() in {"unknown", "none", "n/a"}:
            return None
        return text


class SceneGeometry(BaseModel):
    location_notes: str | None = None
    lighting_notes: str | None = None
    framing_notes: str | None = None
    geometry_notes: str | None = None

    @field_validator(
        "location_notes",
        "lighting_notes",
        "framing_notes",
        "geometry_notes",
        mode="before",
    )
    @classmethod
    def _notes(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() in {"unknown", "none", "n/a"}:
            return None
        return text


class FrameObservationPayload(BaseModel):
    """Pixel facts only. Never carries speaking-role authority."""

    subjects: list[SubjectObservation] = Field(default_factory=list)
    scene: SceneGeometry = Field(default_factory=SceneGeometry)
    ambiguity: list[str] = Field(default_factory=list)

    def model_dump_public(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PlanAssessmentWarning(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class PlanAssessmentPayload(BaseModel):
    observation_id: str
    plan_snapshot_hash: str
    warnings: list[PlanAssessmentWarning] = Field(default_factory=list)
    conforms: bool | None = None
    # Explicit: assessment does not rewrite observation or canon.
    mutates_observation: Literal[False] = False
    mutates_canon: Literal[False] = False


class ObserveFrameRequest(BaseModel):
    image_artifact_id: str | None = None
    use_selected_frame: Literal["first_frame", "last_frame"] | None = "first_frame"
    provider: str = "mock"
    model: str = "mock-vision"
    force: bool = False
    # Optional injected structured vision payload for offline / tests.
    vision_payload: dict[str, Any] | None = None


class AssessPlanRequest(BaseModel):
    plan_snapshot_hash: str | None = None
    plan_revision: str | None = None
    plan_facts: dict[str, Any] | None = None
    publish_artifact: bool = True


class FrameObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    shot_id: str | None
    image_content_hash: str
    image_artifact_id: str | None
    provider: str
    model: str
    subjects: list[dict[str, Any]]
    scene: dict[str, Any]
    ambiguity: list[Any]
    raw_response: str | None
    provenance: dict[str, Any]
    artifact_version_id: str | None
    cache_hit: bool = False
    created_at: datetime


class PlanAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    shot_id: str
    observation_id: str
    plan_snapshot_hash: str
    plan_revision: str | None
    warnings: list[dict[str, Any]]
    result: dict[str, Any]
    provenance: dict[str, Any]
    artifact_version_id: str | None
    cache_hit: bool = False
    created_at: datetime
