import redis, hashlib, time, uuid, os, json
from typing import Optional, Literal
from .schema import IncidentResolution
from .pipeline import run_pipeline
from pydantic import BaseModel, ValidationError


# --- Response Wrapper Model ---
class CopilotResponse(BaseModel):
    # field: query
    """why: it stores the user input query and is important to display the user input"""
    query: str

    # field: latency_ms
    """ why float and not int: perf_counter returns float value and converting to integer format looses sub ms accuracy """
    latency_ms: float

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


# --- Cache Key ---
def make_cache_key(query: str, use_reranker: bool) -> str:

    # step 1: combine query and use_reranker into a single string
    """why combine both: Combined both step 1 and step 2 instead of having them separate"""

    # step 2: hash the combined string using sha256
    """ why sha256 and not md5: because sha256 has very low collision probability compared to MD5 and the modern standard """

    # step 3: return hex digest with a namespace prefix e.g. "copilot:<hash>"
    """ why namespace prefix: All of step 1, 2 and 3 are combined together the namespace prefix is to organise the keys by the purpose or operation """
    cache_key = f"copilot:reranker:{use_reranker}:{hashlib.sha256(query.encode('utf-8')).hexdigest()}"

    return cache_key


# --- Cache Read ---
def get_cached_response(
    redis_client, query: str, use_reranker: bool
) -> tuple[Optional[IncidentResolution], Optional[str]]:

    #  step 1: generate cache key using make_cache_key
    """why reuse make_cache_key and not inline the hash: because it is a helper function to create a hashed key for redis and inmplement resuability"""
    cache_key = make_cache_key(query, use_reranker)

    # step 2: attempt redis GET
    # step 3: if None, return None
    """ what does redis return if key does not exist: It returns None indicating that this query has never been encountered before and should be sent to the model for inference and later to be cached.
        Step 2 and Step 3 combined """
    cached = redis_client.get(cache_key)
    if cached:
        try:
            result = json.loads(cached)
        except json.JSONDecodeError as de:
            print(f"Error: Cache returned invalid JSON syntax. {de}")
            raise
    else:
        return None, None

    # step 4: deserialize the json string into a dict
    """ what two keys do you expect in this dict: Incident resolution details and model name """
    # step 5: validate the resolution dict into IncidentResolution
    """ which pydantic v2 method: model_vaidate_json method. Both Step 4 and 5 have been combined """
    try:
        response = result["model_response"]
        parsed = IncidentResolution.model_validate_json(response)
    except ValidationError as e:
        print(
            f"Cache data parsed but does not match Incident Resolution Schema. {e.json()}"
        )
        raise

    # step 6: return (IncidentResolution, model_name)
    """ why return model_name separately: because it is a separate key in the dictionary """
    model_name = result["model_name"]
    return parsed, model_name


# --- Cache Write ---
def cache_response(
    redis_client,
    query: str,
    use_reranker: bool,
    resolution: IncidentResolution,
    model_name: str,
    ttl_seconds: int,
) -> None:

    #  step 1: generate cache key using make_cache_key
    """why same key generation as get_cached_response: because we need to make sure that the keys match to ensure the redis usage makes sense else
    we will have to call the model every single time and cache duplicates wasting the space and increasing the cost
    """
    cache_key = make_cache_key(query, use_reranker)

    # step 2: build the envelope dict with two keys
    """ what are the two keys and why store model_name here: model_response is one key storing the llm response and model_name is the 2nd key.
        We store model name to improve observability and it acts as metadata for the request for debugging and make it traceable"""
    to_be_cached = {}
    to_be_cached["model_name"] = model_name

    # step 3: serialize envelope to json string
    """ which method for the IncidentResolution part: model_dump_json """
    to_be_cached["model_response"] = resolution.model_dump_json()

    # step 4: store in redis with TTL
    """ what redis command takes both value and expiry: redis.setex() method takes both value and expiry key """
    redis_client.setex(cache_key, ttl_seconds, json.dumps(to_be_cached, indent=2))


# --- Main Entry Point ---
def run_with_cache(query: str, use_reranker: bool, redis_client) -> CopilotResponse:

    # step 1: generate request_id here
    """why here and not at the api layer: Because this is service orchestration layer and it is unaware of any HTTP or other services calling this layer and
    hence if we call it though CLI or any other methods then there will be no request id leading to traceability issues
    """
    request_id = str(uuid.uuid4())

    # step 2: start the timer
    """ which python function and why perf_counter over time.time: perf_counter because it is meant for latency measurement where as time.time is for actual system clock time.
        System time will impact time.time leading to incorrect values """

    start = time.perf_counter()

    # step 5: wrap everything in try/except for redis failure
    """ what exception does redis raise on connection failure: redis.exceptions.RedisError
        what is the fallback behavior: the system gracefully degrades as if the redis cache never existed and calls the llm api for inference
        where does this try/except live — around step 3 only, or the whole function: Around step 3 where we get cached response and not the whole function """

    try:
        # step 3: attempt cache read via get_cached_response
        """what does a hit look like, what does a miss look like: In case of hit we return the deserialized cache response and in case of a miss we call the model and send it as a response."""

        response, model_name = get_cached_response(
            redis_client, query=query, use_reranker=use_reranker
        )
    except redis.exceptions.RedisError:
        response = None
        model_name = None

    # step 4a: CACHE HIT path
    """ where does model_used come from on a hit: from cached data
        what is reranker_used on a hit: it means the user wanted to use reranker and the same request had already been raised and hence it is sending reranker based response. """

    if response:
        latency_ms = (time.perf_counter() - start) * 1000
        latency_ms = round(latency_ms, 2)  # Cache Latency
        result = CopilotResponse(
            cache_state="HIT",
            query=query,
            latency_ms=latency_ms,
            request_id=request_id,
            model_used=model_name,
            resolution=response,
            reranker_used=use_reranker,
        )

    # step 4b: CACHE MISS path
    # - where does model_used come from on a miss: It comes from the environment variable stored in .env file
    else:
        response, model_name = run_pipeline(query, use_reranker)
        try:
            cache_response(
                redis_client=redis_client,
                query=query,
                use_reranker=use_reranker,
                resolution=response,
                model_name=model_name,
                ttl_seconds=3600,
            )
        except redis.exceptions.RedisError:
            pass
        latency_ms = (time.perf_counter() - start) * 1000
        latency_ms = round(latency_ms, 2)
        result = CopilotResponse(
            cache_state="MISS",
            query=query,
            latency_ms=latency_ms,
            request_id=request_id,
            model_used=model_name,
            resolution=response,
            reranker_used=use_reranker,
        )

    return result
