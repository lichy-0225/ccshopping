"""Small, explicit state-machine orchestration for the shopping agent."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.agent.state import ConversationState
from app.agent.llm import DeepSeekClient
from app.agent.loop import AgentLoop
from app.tools.registry import build_registry

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SESSIONS: dict[str, ConversationState] = {}


def _load_json(name: str) -> list[dict[str, Any]]:
    with (DATA_DIR / name).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return value if isinstance(value, list) else []


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


class ShoppingAgent:
    def __init__(self) -> None:
        self.products = _load_json("products.json")
        self.prices = {item["sku_id"]: item["price"] for item in _load_json("prices.json")}
        self.policies = _load_json("policies.json")
        self.llm = DeepSeekClient()
        self.registry = build_registry()
        self.loop = AgentLoop(self.llm, self.registry)
        configured_mock = os.getenv("MOCK_LLM")
        self.mock_llm = (configured_mock.lower() in {"1", "true", "yes"}) if configured_mock is not None else not self.llm.configured

    def get_state(self, session_id: str) -> ConversationState:
        return SESSIONS.setdefault(session_id, ConversationState(session_id=session_id))

    def reset(self) -> None:
        SESSIONS.clear()

    def extract_state(self, state: ConversationState, message: str) -> None:
        text = message.strip()
        budget_matches = re.findall(r"(?:预算|改成|改为|调整到|不超过|最多)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*元?", text)
        if budget_matches:
            state.budget_max = float(budget_matches[-1])
        elif re.search(r"\b\d+(?:\.\d+)?\s*元\b", text):
            state.budget_max = float(re.findall(r"(\d+(?:\.\d+)?)\s*元", text)[-1])
        if _contains_any(text, ("洁面", "洗面奶", "洗脸", "清洁产品")):
            state.category = "洁面"
        if _contains_any(text, ("无香", "无香味", "不要香味", "不喜欢香味", "无香型")):
            state.merge_unique("preferences", ["无香"])
        if _contains_any(text, ("温和清洁", "温和", "不紧绷")):
            state.concern = "温和清洁"
            state.merge_unique("preferences", ["温和清洁"])
        if _contains_any(text, ("清爽", "控油", "偏油")):
            state.concern = "清爽控油"
            state.merge_unique("preferences", ["清爽肤感"])
        if _contains_any(text, ("干燥", "偏干")):
            state.concern = "保湿舒润"
        if _contains_any(text, ("T区油", "T区偏油", "额头和鼻子油", "鼻子油")) and _contains_any(text, ("其他都很干", "两颊干", "脸颊干", "其他地方干")):
            state.skin_profile = "混合倾向"
            state.zone_concerns = {"T区": ["偏油"], "其他区域": ["偏干"]}
            state.care_strategy = "分区护理"
            state.concerns = ["T区偏油", "其他区域偏干"]
            state.concern = "分区护理"
        if _contains_any(text, ("不要香味", "不要香", "不含香味")):
            state.merge_unique("exclusions", ["香味"])
        if _contains_any(text, ("可以有香", "能接受香味", "接受香味", "有香味也可以")):
            state.preferences = [item for item in state.preferences if item != "无香"]
            state.exclusions = [item for item in state.exclusions if item != "香味"]
        if _contains_any(text, ("不要刺激", "不要酸", "排除果酸")):
            state.merge_unique("exclusions", ["刺激性成分"])

    def safety_gate(self, state: ConversationState, message: str) -> bool:
        if _contains_any(message, ("刺痛", "泛红", "破损", "持续不适", "明显不适", "灼热", "疼痛", "受损")):
            state.risk_level = "high"
            state.last_action = "safety_response"
            return True
        state.risk_level = "low"
        return False

    def _policy_question(self, message: str) -> bool:
        return _contains_any(message, ("赠品", "促销", "退换", "库存", "线上同价", "授权", "门店政策"))

    def slot_decision(self, state: ConversationState) -> str | None:
        if not state.category and "category" not in state.asked_fields:
            state.asked_fields.append("category")
            return "你想了解哪一类产品，例如洁面或保湿？"
        if state.category == "洁面" and not state.concern and "concern" not in state.asked_fields:
            state.asked_fields.append("concern")
            return "你更在意温和清洁，还是清洁后的清爽感？"
        return None

    def retrieve_products(self, state: ConversationState) -> list[dict[str, Any]]:
        products = [item.copy() for item in self.products if not state.category or item.get("category") == state.category]
        for product in products:
            product["price"] = self.prices.get(product["sku_id"], product.get("price"))
        return products

    def constraint_filter(self, state: ConversationState, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered = []
        for product in products:
            price = product.get("price")
            if state.budget_max is not None and (price is None or price > state.budget_max):
                continue
            if "无香" in state.preferences or "香味" in state.exclusions:
                if not product.get("fragrance_free", False):
                    continue
            if "刺激性成分" in state.exclusions and product.get("stimulant", False):
                continue
            filtered.append(product)
        return sorted(filtered, key=lambda item: (0 if state.concern and state.concern in item.get("tags", []) else 1, item["price"]))

    def _candidate_view(self, product: dict[str, Any], state: ConversationState) -> dict[str, Any]:
        reasons = []
        if "无香" in state.preferences and product.get("fragrance_free"):
            reasons.append("无香型，符合你的偏好")
        if state.concern and state.concern in product.get("tags", []):
            reasons.append(f"特点包含“{state.concern}”")
        if not reasons:
            reasons.append("商品特点与当前品类需求匹配")
        return {
            "sku_id": product["sku_id"], "name": product["name"], "spec": product["spec"],
            "price": product["price"], "match_reasons": reasons,
            "注意事项": product.get("limitations", "以商品标签和门店说明为准"),
        }

    def recommend(self, state: ConversationState, filtered: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
        views = [self._candidate_view(item, state) for item in filtered[:2]]
        reply = f"根据你的预算和需求，我更推荐 {views[0]['name']}。价格、规格和注意事项均来自当前商品知识库。"
        if not self.mock_llm and self.llm.configured:
            facts = "；".join(f"{item['name']}｜{item['spec']}｜¥{item['price']}｜{item['注意事项']}" for item in views)
            try:
                generated = self.llm.complete(
                    "你是澄初个人护理导购。请用温和、具体、克制的真实导购语气组织回复，使用‘可以考虑’、‘如果您在意’等表达；只能使用提供的商品事实，禁止添加商品、价格、库存、赠品、政策或功效承诺。",
                    f"用户需求：{state.category}，预算：{state.budget_max}，偏好：{state.preferences}。商品事实：{facts}",
                )
                if generated:
                    reply = generated
            except (httpx.HTTPError, ValueError, KeyError):
                # External model failure must not break the deterministic MVP.
                pass
        return views, reply

    def output_validate(self, state: ConversationState, candidates: list[dict[str, Any]], reply: str = "") -> bool:
        known = {item["sku_id"]: item for item in self.products}
        allowed_ids = {candidate.get("sku_id") for candidate in candidates}
        for candidate in candidates:
            if not known.get(candidate.get("sku_id")) or self.prices.get(candidate["sku_id"]) != candidate.get("price"):
                return False
            if state.budget_max is not None and candidate["price"] > state.budget_max:
                return False
        # Do not allow the model to mention a catalog product outside the
        # current tool result, even if that product exists in the catalog.
        for sku_id, product in known.items():
            if (sku_id in reply or product.get("name") in reply) and sku_id not in allowed_ids:
                return False
        unsupported_policy_terms = ("赠品", "库存", "退换货", "线上同价", "促销", "渠道授权")
        return state.risk_level != "high" and not _contains_any(reply, unsupported_policy_terms)

    def handle(self, session_id: str, message: str, store_id: str | None = None, product_sku: str | None = None) -> dict[str, Any]:
        state = self.get_state(session_id)
        self.extract_state(state, message)
        trace_id = str(uuid4())
        state.current_goal = message
        if self.safety_gate(state, message):
            return {
                "session_id": session_id, "action": "safe_reply",
                "reply": "你提到刺痛、泛红或其他明显不适。先暂停刺激性产品尝试，必要时咨询专业人士；我不能替你做医疗诊断。",
                "risk_level": state.risk_level, "candidates": [], "next_question": None, "used_tools": [], "needs_confirmation": False, "trace_id": trace_id,
            }
        if product_sku:
            tool_result = self.registry.call("get_product_detail", {"sku_id": product_sku})
            product = tool_result.get("data") if isinstance(tool_result, dict) else None
            if isinstance(product, dict) and product.get("sku_id"):
                product = {**product, "price": self.prices.get(product["sku_id"], product.get("price"))}
                candidate = self._candidate_view(product, state)
                reply = f"这款是 {candidate['name']}，规格为 {candidate['spec']}，目前价格是 ¥{candidate['price']}。它的特点是{'、'.join(product.get('tags', []))}；{candidate['注意事项']}"
                if not self.mock_llm and self.llm.configured:
                    try:
                        generated = self.llm.complete(
                            "你是澄初个人护理导购。请用温和、自然、简洁的中文介绍这一款商品；只使用给定事实，不添加价格、功效、库存、赠品或政策。",
                            f"商品：{candidate['name']}；规格：{candidate['spec']}；价格：¥{candidate['price']}；特点：{'、'.join(product.get('tags', []))}；注意事项：{candidate['注意事项']}。",
                        )
                        if generated and self.output_validate(state, [candidate], generated):
                            reply = generated
                    except (httpx.HTTPError, ValueError, KeyError):
                        pass
                state.messages.extend([{"role": "user", "content": message}, {"role": "assistant", "content": reply}])
                state.selected_skus = [product["sku_id"]]
                state.last_tool_results = [tool_result]
                state.last_action = "detail"
                return {"session_id": session_id, "action": "detail", "reply": reply, "risk_level": state.risk_level, "candidates": [candidate], "comparison": None, "next_question": None, "used_tools": ["get_product_detail"], "needs_confirmation": False, "trace_id": trace_id}
        if _contains_any(message, ("忽略之前指令", "忽略系统提示", "泄露提示词", "不要遵守安全规则", "绕过安全")):
            state.safety_flags.append("prompt_injection")
            state.last_action = "fallback"
            return {"session_id": session_id, "action": "fallback", "reply": "我不能执行越权指令，但可以继续帮你查询商品、预算和已知政策。", "risk_level": "low", "candidates": [], "next_question": None, "used_tools": [], "needs_confirmation": False, "trace_id": trace_id}
        result = self.loop.run(state, message)
        candidates = result.get("candidates", [])
        state.candidates = [item.get("sku_id") for item in candidates if item.get("sku_id")]
        if candidates and not self.output_validate(state, candidates, result.get("reply", "")):
            if self.output_validate(state, candidates, ""):
                safe_name = candidates[0].get("name", "这款商品")
                safe_price = candidates[0].get("price")
                result = {**result, "action": "recommend", "reply": f"可以先考虑 {safe_name}，目前价格是 ¥{safe_price}。具体使用注意事项可以以商品说明为准。", "needs_confirmation": True}
            else:
                state.last_action = "fallback"
                result = {**result, "action": "fallback", "reply": "商品事实需要进一步确认后再推荐。", "candidates": [], "needs_confirmation": True}
        state.last_action = result.get("action")
        return {
            "session_id": session_id, "action": result.get("action", "fallback"),
            "reply": result.get("reply", "我暂时无法整理出可靠建议，请补充品类或预算。"),
            "risk_level": state.risk_level, "candidates": result.get("candidates", []), "comparison": result.get("comparison"), "next_question": result.get("next_question"),
            "used_tools": result.get("used_tools", []), "needs_confirmation": bool(result.get("needs_confirmation", False)), "truncated": bool(result.get("truncated", False)), "trace_id": trace_id,
        }
