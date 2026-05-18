from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AiProvider = Literal["groq", "local_gemma"]
CleanedFilter = Literal["any", "only_cleaned", "only_uncleaned"]


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = Field(min_length=1, max_length=80)


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionResponse(BaseModel):
    token: str
    user: dict


class DeviceRegisterRequest(BaseModel):
    device_name: str = Field(min_length=1, max_length=120)
    connector_version: str = "1.0.0"


class DeviceRegisterResponse(BaseModel):
    device_id: str
    device_token: str


class ClipMetadata(BaseModel):
    relative_path: str
    title_text: str
    category: str = ""
    character: str = ""
    filename: str
    extension: str = ".mp4"
    size_bytes: int = 0
    size_mb: float = 0.0
    modified_at: str
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    frames: int | None = None
    duration_sec: float | None = None
    aspect_ratio: str | None = None
    looks_cleaned: bool = False
    search_text: str
    source_hash: str


class RootSyncRequest(BaseModel):
    device_token: str
    label: str
    folder_path: str
    clips: list[ClipMetadata]
    reset: bool = True
    finalize: bool = True


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=20, ge=1, le=100)
    provider: AiProvider = "local_gemma"
    local_model: str | None = None


class AssistantRequest(BaseModel):
    message: str
    provider: AiProvider = "local_gemma"
    local_model: str | None = None
    state: dict = Field(default_factory=dict)


class ViralStitchRequest(BaseModel):
    brief: str = Field(min_length=8, max_length=1200)
    transcript: str = Field(default="", max_length=4000)
    provider: AiProvider = "local_gemma"
    local_model: str | None = None
    clip_count: int = Field(default=6, ge=2, le=12)


class FrameIntelligenceRequest(BaseModel):
    max_clips: int = Field(default=6, ge=1, le=20)
    frames_per_clip: int = Field(default=3, ge=1, le=8)
    target_score: int = Field(default=100, ge=70, le=100)


class BillingCheckoutRequest(BaseModel):
    plan_id: str
    success_url: str
    cancel_url: str


class VoiceTranscriptionRequest(BaseModel):
    audio_base64: str
    mime_type: str = "audio/webm"
    language: str = "en"
