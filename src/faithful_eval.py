from .schema import Chunk, IncidentResolution, SimilarIncident, FaithfulnessResult
from typing import Optional


# --- Helper: build valid sets from chunks ---
# Q: why is this a separate function and not inlined into check_faithfulness?
# Q: what does it return — a tuple of two sets, or something else?
def build_valid_sets(chunks: list[Chunk]):

    valid_sources = set(chunk.source for chunk in chunks)
    valid_inc_ids = set(chunk.incident_id for chunk in chunks if chunk.incident_id)

    return valid_sources, valid_inc_ids


# --- Check 1: sources field ---
# Takes the claimed sources list and the valid sources set
# Returns a list of strings — each string is one fabricated source filename
# Q: what does an empty list mean for this check?
# Q: what does a non-empty list mean?
def _check_sources(claimed_sources: list[str], valid_sources: set[str]) -> list[str]:

    fabricated_sources = [
        source for source in claimed_sources if source not in valid_sources
    ]

    return fabricated_sources


# --- Check 2: similar_incidents field ---
# Takes the similar_incidents list from IncidentResolution and valid_incident_ids set
# Returns a list of strings — each string is one fabricated incident ID
# Q: what field on SimilarIncident do you check?
# Q: what field would you also want to check but can't mechanically?
def _check_incident_ids(
    similar_incidents: list[SimilarIncident], valid_incidents: set[str]
) -> list[str]:

    fabricated_incidents = [
        incident.incident_id
        for incident in similar_incidents
        if incident.incident_id not in valid_incidents
    ]

    return fabricated_incidents


# --- Main public function ---
# This is what eval.py and CI will call
# Q: what does it do with the results of the two checks above?
# Q: should it print anything, or only return?
# Q: what happens if chunks is empty — is that a pass or a special case?
def evaluate_faithfulness(
    query: str, resolution: IncidentResolution, chunks: list[Chunk]
) -> Optional[FaithfulnessResult]:

    if not chunks:
        result = FaithfulnessResult(
            query=query,
            fabricated_incidents=[],
            fabricated_sources=[],
            was_evaluated=False,
        )
        return result

    valid_sources, valid_inc_ids = build_valid_sets(chunks)

    fabricated_sources = _check_sources(
        claimed_sources=resolution.sources, valid_sources=valid_sources
    )

    fabricated_incidents = _check_incident_ids(
        similar_incidents=resolution.similar_incidents, valid_incidents=valid_inc_ids
    )

    result = FaithfulnessResult(
        query=query,
        fabricated_incidents=fabricated_incidents,
        fabricated_sources=fabricated_sources,
        was_evaluated=True,
    )

    return result
