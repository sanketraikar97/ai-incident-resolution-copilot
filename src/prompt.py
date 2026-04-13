from schema import Chunk


SYSTEM_PROMPT = """
You are an incident resolution assistant. Your job is to analyze 
incident descriptions and return structured, actionable recommendations.

RULES:
   1. Use ONLY the context provided. Do not use knowledge from your training data.
   2. If context is insufficient, reflect that in confidence field.
   3. Never invent incident IDs, commands, or runbook names.
   4. Output must be valid JSON matching the schema exactly.
   5. If no relevant context is found, set confidence to "low" and say so clearly in issue_summary. Do not guess.

OUTPUT SCHEMA — your response must be valid JSON with exactly these fields:
{
    "issue_summary": "string — one sentence description of the likely issue",
    "likely_causes": ["string — each cause is one specific technical reason, not generic"],
    "recommended_actions": [
                            { "step": 1,
                              "action": "string",
                              "command": "string or null"
                            }
                              ],
    "similar_incidents": [
                        { "incident_id": "string",
                          "title": "string",
                          "similarity_reason": "string" 
                        }
                          ],
    "confidence": "high|medium|low — high if 2+ relevant incidents found, low if context is weak",
    "confidence_reason": "string — one sentence explaining why this confidence level was chosen",
    "sources": ["string - filename of each chunk used, e.g. INC-2024-0001.json or RB-DB-001.md"]
}
"""


def format_context(chunks: list[Chunk]) -> str:

    formatted_blocks = []

    for chunk in chunks:
        score_str = f"{chunk.score:.3f}" if chunk.score is not None else "N/A"
        block = [
            "---",
            f"[SOURCE: {chunk.source} | TYPE: {chunk.chunk_type} | SCORE: {score_str}]",
        ]

        block.append(chunk.text)
        formatted_blocks.append("\n".join(block))

    return "\n".join(formatted_blocks)


def build_user_message(query: str, chunks: list[Chunk]) -> str:

    context = format_context(chunks)

    return f"CONTEXT:\n{context}\n\nINCIDENT:\n{query}"


if __name__ == "__main__":

    test_chunks = [
        Chunk(
            text="Title: Payment API timeout\nRoot Cause: DB connection pool exhausted",
            source="INC-2024-0001.json",
            incident_id="INC-2024-0001",
            chunk_type="incident",
            score=0.91,
        ),
        Chunk(
            text="Fix: Kill idle connections, set statement_timeout=5000",
            source="RB-DB-001.md",
            chunk_type="runbook",
            score=0.76,
        ),
    ]

    print("SYSTEM PROMPT:")
    print(SYSTEM_PROMPT)
    print("\n USER MESSAGE")
    print(build_user_message("Payment API timing out intermittently", test_chunks))
