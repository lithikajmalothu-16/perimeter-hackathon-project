"""Pydantic models for the API (PRD section 10)."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

Campus = Literal["clarkston", "perimeter_all", "online", "gsu_wide", "atlanta_only"]
RType = Literal["office", "center", "program", "org", "opportunity", "event", "service"]


class Profile(BaseModel):
    name: str = "Jordan"
    campus: str = "clarkston"
    campus_name: Optional[str] = None
    email: Optional[str] = None
    email_verified: bool = False
    major: Optional[str] = None
    pathway_id: Optional[str] = "business_admin"
    credits: int = 30
    work_hours: int = 30
    holds: list[str] = Field(default_factory=list)
    interests: str = ""
    topics: list[str] = Field(default_factory=list)


class Resource(BaseModel):
    id: str
    source_id: str
    name: str
    type: Optional[str] = None
    campus: Optional[str] = None
    audience: Optional[str] = None
    topics: list[str] = Field(default_factory=list)
    summary: Optional[str] = None
    eligibility: Optional[str] = None
    how_to_start: Optional[str] = None
    contact_office: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    location_building: Optional[str] = None
    location_room: Optional[str] = None
    hours: Optional[str] = None
    deadline: Optional[str] = None
    event_start: Optional[str] = None
    event_end: Optional[str] = None
    evidence: str
    source_url: Optional[str] = None
    fetched_at: Optional[str] = None
    origin: Optional[str] = "agent"
    status: Optional[str] = None


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list)


class Match(BaseModel):
    resource: Resource
    why: str
    first_step: str


class TraceStep(BaseModel):
    step: str
    detail: str
    ms: int


class Verification(BaseModel):
    checker: str
    removed_sentences: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    unverified: list[dict] = Field(default_factory=list)
    answer: str
    matches: list[Match]
    trace: list[TraceStep]
    verification: Verification


class DraftEmailRequest(BaseModel):
    resource_id: str


class DraftEmail(BaseModel):
    to: Optional[str]
    subject: str
    body: str
    contact_url: Optional[str]


class IngestionRun(BaseModel):
    id: int
    source_id: str
    started_at: str
    finished_at: Optional[str] = None
    rows_new: int = 0
    rows_changed: int = 0
    rows_dropped: int = 0
    error: Optional[str] = None


class SendCode(BaseModel):
    email: str


class VerifyCode(BaseModel):
    email: str
    code: str


class Onboard(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str
    token: str
    campus_name: str
    major: str
    topics: list[str] = Field(default_factory=list)
