import os
from typing import List, Dict, Any
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def gpt_classify_batch(
    keywords: List[str],
    allowed_buckets: List[str],
    allowed_intents: List[str],
    allowed_stages: List[str]
) -> List[Dict[str, Any]]:
    """
    Returns list of {keyword,bucket_id,intent,stage,is_negative,negative_type,negative_theme,notes}
    """
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string"},
                        "bucket_id": {"type": "string", "enum": allowed_buckets},
                        "intent": {"type": "string", "enum": allowed_intents},
                        "stage": {"type": "string", "enum": allowed_stages},
                        "is_negative": {"type": "string", "enum": ["Y", "N"]},
                        "negative_type": {"type": "string"},
                        "negative_theme": {"type": "string"},
                        "notes": {"type": "string"}
                    },
                    "required": ["keyword","bucket_id","intent","stage","is_negative","negative_type","negative_theme","notes"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["items"],
        "additionalProperties": False
    }

    prompt = (
        "Classify each keyword into the provided bucket taxonomy.\n"
        "Rules:\n"
        "- If Kerala Ayurveda brand token is present, never output NB-* buckets.\n"
        "- If competitor brand token is present (and no KA token), never output KA-* buckets.\n"
        "- If keyword is corporate/jobs/services/US-geo, mark is_negative='Y' and choose KA-NF* bucket if KA token present.\n"
        "Return strictly the JSON schema.\n\n"
        "Keywords:\n" + "\n".join(f"- {k}" for k in keywords)
    )

    resp = client.responses.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-5"),  # set in Render env
        input=prompt,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "kw_classification", "schema": schema, "strict": True}
        }
    )

    # SDK returns parsed JSON in output_text for schema mode (safe), but keep robust:
    data = resp.output_parsed  # structured output parsing
    return data["items"]
