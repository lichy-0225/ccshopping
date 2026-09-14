import json
from pathlib import Path


def load_prices() -> dict[str, float]:
    path = Path(__file__).resolve().parents[1] / "data" / "prices.json"
    with path.open("r", encoding="utf-8") as handle:
        return {item["sku_id"]: item["price"] for item in json.load(handle)}
