import json
import os
from datetime import datetime, timezone
from .schema import CopilotResponse

# --- Module-level setup ---
# called once at import time, never again
""" why at module level and not inside log_request: because it is to be called only once at import time and not during every logging request. """


def setup_log_file() -> str:

    # step 1: read log file path from env var with a default
    """what is a sensible default path: logs/requests.jsonl"""
    log_path = os.getenv("LOG_FILE_PATH", "logs/requests.jsonl")

    # step 2: extract directory from the full file path
    """ which os function splits a path into directory and filename: os.path.split() """
    log_directory, log_file = os.path.split(log_path)

    # step 3: create directory if it does not exist
    """ which call, which parameter prevents crash if it exists: exist_ok=True """
    os.makedirs(log_directory, exist_ok=True)

    # step 4: return the resolved file path
    """ why return it instead of using a global directly: not sure but i feel like to avoid global declarations and dependencies. """
    return os.path.join(log_directory, log_file)


# called once, result stored at module level
""" why store at module level: because changing the .env file during runtime is of no use as it will not be accesible for current round of execution and it is accessed only at looger module and not across the entire project """
LOG_FILE_PATH = setup_log_file()


# --- Request Logger ---
def log_request(copilot_response: CopilotResponse) -> None:

    # step 1: build the log entry dict
    # every key with its source — include the None guard for resolution fields
    """how do you serialize a list of Pydantic objects to plain dicts: model_dump or model_model_dump_json()"""
    log_data = {}
    response = copilot_response.resolution
    log_data["requested_at"] = datetime.now(timezone.utc).isoformat()
    log_data["environment"] = os.getenv("ENV", "development")
    log_data["request_id"] = copilot_response.request_id
    log_data["user_query"] = copilot_response.query
    log_data["latency_in_ms"] = copilot_response.latency_ms
    log_data["cache_state"] = copilot_response.cache_state
    log_data["model_used"] = copilot_response.model_used
    log_data["reranker_used"] = copilot_response.reranker_used

    log_data["sources"] = response.sources if response else None
    log_data["confidence"] = response.confidence if response else None
    log_data["confidence_reason"] = response.confidence_reason if response else None
    log_data["similar_incidents"] = (
        [incident.model_dump() for incident in response.similar_incidents]
        if response
        else None
    )

    # step 2: open log file in append mode and write one JSON line
    """ why append mode: because append mode adds new data to the existing records in the file instead of overwriting it """
    """ why add "\n" at the end: to add every new request log as a new line to improve usability """
    """ which open() parameter ensures UTF-8 encoding: encoding="utf-8" """
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as logger:
        logger.write(json.dumps(log_data) + "\n")
