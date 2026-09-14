def within_budget(price: float, budget_max: float | None) -> bool:
    return budget_max is None or price <= budget_max
