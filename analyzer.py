def analyze(prev, current):
    events = {
        "sales": [],
        "price_changes": [],
        "total_value": 0
    }

    prev_map = {i["name"]: i for i in prev}
    current_map = {i["name"]: i for i in current}

    # Total inventory value
    for item in current:
        events["total_value"] += item["price"]

    # Detect SALES (item disappeared)
    for name, old_item in prev_map.items():
        if name not in current_map:
            events["sales"].append(old_item)

    # Detect PRICE CHANGES
    for name, item in current_map.items():
        if name in prev_map:
            old_price = prev_map[name]["price"]
            if item["price"] != old_price:
                events["price_changes"].append({
                    "name": name,
                    "old": old_price,
                    "new": item["price"]
                })

    return events
