import re, math


# ── Teléfono ──────────────────────────────────────────────────────────────────

def normalize_phone(raw):
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("0"):
        digits = "56" + digits[1:]
    elif digits.startswith("9") and len(digits) == 9:
        digits = "56" + digits
    return digits


# ── Geo ───────────────────────────────────────────────────────────────────────

def haversine(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat/2)**2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlng/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def nearest_neighbor_route(origin, stops):
    if not stops:
        return []
    unvisited = stops[:]
    route, current = [], origin
    while unvisited:
        nearest = min(unvisited,
                      key=lambda s: haversine(current["lat"], current["lng"],
                                              s["lat"], s["lng"]))
        route.append(nearest)
        current = nearest
        unvisited = [s for s in unvisited if s["id"] != nearest["id"]]
    return route
