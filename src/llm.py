import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import ValidationError
from .schema import IncidentResolution
from .prompt import SYSTEM_PROMPT, build_user_message


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")


def call_llm(query: str, chunks: list) -> IncidentResolution:

    user_message = build_user_message(query, chunks)

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    json_text = response.choices[0].message.content
    try:
        json_dict = json.loads(json_text)
    except json.JSONDecodeError as je:
        print(f"Error: LLM returned invalid JSON syntax. {je}")
        raise

    try:
        parsed = IncidentResolution.model_validate(json_dict)
    except ValidationError as e:
        print(
            f"JSON data parsed but does not match Incident Resolution Schema. {e.json()}"
        )
        raise

    return parsed
