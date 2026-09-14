import json
from pathlib import Path


def load_policies() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "data" / "policies.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
