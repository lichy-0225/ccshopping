HIGH_RISK_TERMS = ("刺痛", "泛红", "破损", "持续不适", "明显不适", "灼热", "疼痛", "受损")


def risk_level(message: str) -> str:
    return "high" if any(term in message for term in HIGH_RISK_TERMS) else "low"
