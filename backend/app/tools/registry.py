"""Tool registry and common metadata for the Agent V2 loop."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCE_VERSION = "brand-manual-v2"


def _read(name: str) -> Any:
    with (DATA_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fact_result(data: Any, evidence: list[str]) -> dict[str, Any]:
    return {
        "data": data,
        "source": "澄初个人护理智能导购品牌手册及受控本地知识库",
        "source_version": SOURCE_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "validity": "current",
        "evidence": evidence,
    }


@dataclass
class RegisteredTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., dict[str, Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def definitions(self) -> list[dict[str, Any]]:
        return [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in self._tools.values()]

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.get(name)
        if not tool:
            return fact_result({"error": "unknown_tool", "tool": name}, ["Tool Registry"])
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(tool.handler, **arguments)
                return future.result(timeout=float(os.getenv("AGENT_TOOL_TIMEOUT", "8")))
        except TimeoutError:
            return fact_result({"error": "tool_timeout", "tool": name}, [name])
        except Exception as exc:  # tool failures become structured facts, never crashes
            return fact_result({"error": "tool_error", "message": type(exc).__name__}, [name])

    def catalog_context(self) -> str:
        """Build a compact catalog snapshot for the LLM system prompt."""
        prices = _prices()
        rows = []
        for item in _products():
            rows.append(f"{item['sku_id']}｜{item['name']}｜品类:{item['category']}｜规格:{item['spec']}｜价格:¥{prices.get(item['sku_id'], item.get('price'))}｜标签:{'、'.join(item.get('tags', []))}")
        return "\n".join(rows)


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    product_schema = {"type": "object", "properties": {"category": {"type": "string"}, "budget_max": {"type": ["number", "null"]}, "preferences": {"type": "array", "items": {"type": "string"}}, "exclusions": {"type": "array", "items": {"type": "string"}}, "concerns": {"type": "array", "items": {"type": "string"}}}}
    registry.register(RegisteredTool("search_products", "在受控商品库中按品类、预算、偏好和关注点检索商品。", product_schema, _search_products))
    registry.register(RegisteredTool("get_product_detail", "获取指定 SKU 的完整商品事实。", {"type": "object", "properties": {"sku_id": {"type": "string"}}, "required": ["sku_id"]}, _get_product_detail))
    registry.register(RegisteredTool("compare_products", "比较两个或多个已知 SKU 的商品事实。", {"type": "object", "properties": {"sku_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["sku_ids"]}, _compare_products))
    registry.register(RegisteredTool("get_price", "获取商品当前受控价格。", {"type": "object", "properties": {"sku_id": {"type": "string"}}, "required": ["sku_id"]}, _get_price))
    registry.register(RegisteredTool("get_policy", "查询品牌政策；知识库没有的政策返回 unknown。", {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}, _get_policy))
    registry.register(RegisteredTool("get_bundle_options", "查询适用的商品组合。", {"type": "object", "properties": {"sku_ids": {"type": "array", "items": {"type": "string"}}, "category": {"type": "string"}}}, _get_bundle_options))
    return registry


def _products() -> list[dict[str, Any]]:
    return _read("products.json")


def _prices() -> dict[str, Any]:
    return {x["sku_id"]: x["price"] for x in _read("prices.json")}


def _search_products(category: str | None = None, budget_max: float | None = None, preferences: list[str] | None = None, exclusions: list[str] | None = None, concerns: list[str] | None = None) -> dict[str, Any]:
    preferences, exclusions, concerns = preferences or [], exclusions or [], concerns or []
    if not category:
        return fact_result({"needs_category": True, "items": []}, ["products.json:category_required"])
    prices = _prices()
    result = []
    for item in _products():
        if category and item.get("category") != category:
            continue
        price = prices.get(item["sku_id"], item.get("price"))
        if budget_max is not None and (price is None or price > budget_max):
            continue
        if ("无香" in preferences or "香味" in exclusions) and not item.get("fragrance_free", False):
            continue
        if "刺激性成分" in exclusions and item.get("stimulant", False):
            continue
        row = dict(item)
        row["price"] = price
        result.append(row)
    result.sort(key=lambda x: (0 if any(c in x.get("tags", []) for c in concerns) else 1, x["price"]))
    return fact_result(result, [f"products.json:{item['sku_id']}" for item in result])


def _get_product_detail(sku_id: str) -> dict[str, Any]:
    item = next((x for x in _products() if x["sku_id"] == sku_id), None)
    return fact_result(item or {"unknown_sku": sku_id}, [f"products.json:{sku_id}"])


def _compare_products(sku_ids: list[str]) -> dict[str, Any]:
    items = [x for x in _products() if x["sku_id"] in sku_ids]
    prices = _prices()
    data = [{**x, "price": prices.get(x["sku_id"], x.get("price"))} for x in items]
    return fact_result(data, [f"products.json:{sku}" for sku in sku_ids])


def _get_price(sku_id: str) -> dict[str, Any]:
    price = _prices().get(sku_id)
    return fact_result({"sku_id": sku_id, "price": price, "known": price is not None}, [f"prices.json:{sku_id}"])


def _get_policy(topic: str) -> dict[str, Any]:
    policies = _read("policies.json")
    known = next((x for x in policies if topic in x.get("supported_topics", [])), None)
    if known:
        return fact_result(known, [f"policies.json:{known['policy_id']}"])
    return fact_result({"topic": topic, "status": "unknown", "reply": "需要向门店或系统确认"}, ["policies.json:knowledge_boundary"])


def _get_bundle_options(sku_ids: list[str] | None = None, category: str | None = None) -> dict[str, Any]:
    bundles = _read("bundles.json")
    if sku_ids:
        bundles = [b for b in bundles if all(sku in b["sku_ids"] for sku in sku_ids)]
    return fact_result(bundles, [f"bundles.json:{b['bundle_id']}" for b in bundles])
