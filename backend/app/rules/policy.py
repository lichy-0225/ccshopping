UNKNOWN_POLICY_TERMS = ("赠品", "促销", "退换", "库存", "线上同价", "授权", "门店政策")


def asks_unknown_policy(message: str) -> bool:
    return any(term in message for term in UNKNOWN_POLICY_TERMS)
