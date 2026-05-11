from pydantic import BaseModel
from typing import Optional, List, Literal


class Chunk(BaseModel):
    model_config = {"frozen": False}
    text: str
    source: str
    incident_id: Optional[str] = None
    chunk_type: Literal["runbook", "incident"]
    score: Optional[float] = None
    rerank_score: Optional[float] = None


class RecommendedAction(BaseModel):
    step: int
    action: str
    command: Optional[str] = None


class SimilarIncident(BaseModel):
    incident_id: str
    title: str
    similarity_reason: str


class IncidentResolution(BaseModel):
    issue_summary: str
    likely_causes: List[str]
    recommended_actions: List[RecommendedAction]
    similar_incidents: List[SimilarIncident]
    confidence: str
    confidence_reason: str
    sources: List[str]
