import json
from retrieve import retrieve, load_index
from llm import call_llm
from schema import IncidentResolution


def run_pipeline(query: str) -> IncidentResolution:

    index, connector = load_index()

    chunks = retrieve(query, index, connection=connector, top_k=8, top_n=5)
    connector.close()
    print(f"No of chunks retrieved: {len(chunks)}")

    llm_json = call_llm(query, chunks)

    return llm_json


if __name__ == "__main__":

    result = run_pipeline(query="Payment API timing out intermittently")
    print(json.dumps(result.model_dump(), indent=2))
