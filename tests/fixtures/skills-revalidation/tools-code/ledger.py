def canonical_label(text):
    return " ".join(text.split()).casefold()


def preview(accounts, transfers, *, cancelled=False, formatter=None):
    if cancelled:
        return {"state": "cancelled", "accounts": None}
    projected = dict(accounts)
    for source, target, amount in transfers:
        if projected[source]["balance"] < amount:
            return {"state": "unavailable", "accounts": None}
        projected[source]["balance"] -= amount
        projected[target]["balance"] += amount
    if formatter is not None:
        formatter(projected)
    return {"state": "ready", "accounts": projected}
