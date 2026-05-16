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


# --- Response Wrapper Model ---
class CopilotResponse(BaseModel):
    # field: query
    """why: it stores the user input query and is important to display the user input"""
    query: str

    # field: latency_ms
    """ why float and not int: perf_counter returns float value and converting to integer format looses sub ms accuracy """
    latency_ms: float
    retrieval_ms: Optional[float] = None
    rerank_ms: Optional[float] = None
    llm_ms: Optional[float] = None

    # field: request_id
    """ why: A unique id for each request raised towards this system and acts as an identifier """
    request_id: str

    # field: cache_state
    """ why Literal and not str: Because we want to provide only 2 options i.e either a hit or a miss """
    cache_state: Literal["HIT", "MISS"]

    # field: model_used
    """ why Optional: In case of cache Hit we never call a model so i refer to it as optional field for now """
    model_used: Optional[str]

    # field: resolution
    """ why Optional: It is optional because in case we get a cache miss and the internal validations of run_pipeline fail and we dont get any response it is to avoid any kind of dumps """
    resolution: Optional[IncidentResolution]

    # field: reranker_used
    """ why: The model has the flexibility to either run the reranker or use FAISS similarity for outputs """
    reranker_used: bool


# --- Result model ---
# Define a Pydantic model for the result of one faithfulness check
# Q: what fields does it need?
# Q: which fields are lists (multiple violations possible) vs single values?
# Q: should it have a boolean "passed" field, or can you derive that from the violations list?
class FaithfulnessResult(BaseModel):

    query: str
    fabricated_sources: list[str]
    fabricated_incidents: list[str]
    was_evaluated: bool
