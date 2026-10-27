"""JSON Schema dla structured output, budowany ze schematu Pydantic."""
from extraction.schemas import UnifiedRulingSchema


def _clean(node):
    """Dostosowuje schemat Pydantic do trybu `strict` (OpenAI / OpenRouter):
    usuwa 'default' i 'title', każdy obiekt dostaje additionalProperties=false i komplet pól w 'required'."""
    if isinstance(node, list):
        return [_clean(x) for x in node]
    if not isinstance(node, dict):
        return node

    out = {}
    for key, value in node.items():
        if key in ("default", "title"):
            continue
        if key in ("properties", "$defs"):  # klucze to nazwy pól/definicji, nie słowa kluczowe schematu
            out[key] = {name: _clean(sub) for name, sub in value.items()}
        else:
            out[key] = _clean(value)

    if out.get("type") == "object" and "properties" in out:
        out["additionalProperties"] = False
        out["required"] = list(out["properties"])
    return out


def build_response_schema(model_cls=UnifiedRulingSchema) -> dict:
    return _clean(model_cls.model_json_schema())
