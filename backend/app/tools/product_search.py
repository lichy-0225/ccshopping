import json
from pathlib import Path


def load_products() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "data" / "products.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
