"""Weekly meal planner. 7 days x 3 meals = 21 slots.

slot_id format: 'd{day}_m{meal}' where day is 0-6 and meal in {b,l,d}.
Using underscores consistently in both API and JS to avoid mismatch bugs.
"""
from flask import Blueprint, jsonify, request

from .. import config
from ..services import db, matching

bp = Blueprint("meals", __name__)
TABLE = config.MEALS_TABLE
RECIPES = config.RECIPES_TABLE
LIBRARY = "LIBRARY"

VALID_MEALS = {"b", "l", "d"}


def _slot_id(day: int, meal: str) -> str:
    return f"d{day}_m{meal}"


def _all_recipes_index() -> dict[str, dict]:
    idx = {}
    for r in db.query_user(RECIPES, config.USER_ID) + db.query_user(RECIPES, LIBRARY):
        idx[r["sk"]] = r
    return idx


@bp.get("/")
def get_plan():
    slots = db.query_user(TABLE, config.USER_ID)
    idx = _all_recipes_index()
    out = []
    for s in slots:
        r = idx.get(s.get("recipe_id", ""))
        out.append({
            "slot_id": s["sk"],
            "day": s.get("day"),
            "meal": s.get("meal"),
            "recipe_id": s.get("recipe_id"),
            "recipe": r,
        })
    return jsonify(out)


@bp.post("/")
def set_slot():
    data = request.get_json(force=True) or {}
    try:
        day = int(data["day"])
        meal = data["meal"]
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "day (0-6) and meal (b/l/d) required"}), 400
    if not 0 <= day <= 6 or meal not in VALID_MEALS:
        return jsonify({"error": "invalid day or meal"}), 400
    recipe_id = (data.get("recipe_id") or "").strip()
    slot_id = _slot_id(day, meal)
    if not recipe_id:
        db.delete(TABLE, config.USER_ID, slot_id)
        return jsonify({"slot_id": slot_id, "cleared": True})
    return jsonify(db.put(TABLE, config.USER_ID, slot_id, {
        "day": day, "meal": meal, "recipe_id": recipe_id,
    }))


@bp.delete("/<slot_id>")
def clear_slot(slot_id: str):
    db.delete(TABLE, config.USER_ID, slot_id)
    return "", 204


@bp.get("/grocery_preview")
def grocery_preview():
    """Aggregate ingredients across the week, classify against the pantry."""
    pantry = db.query_user(config.PANTRY_TABLE, config.USER_ID)
    pantry_norms = {matching.normalize(p.get("name", "")) for p in pantry}
    pantry_norms.discard("")

    slots = db.query_user(TABLE, config.USER_ID)
    idx = _all_recipes_index()

    needed: dict[str, dict] = {}
    for s in slots:
        r = idx.get(s.get("recipe_id", ""))
        if not r:
            continue
        for ing in r.get("ingredients", []):
            norm = matching.normalize(ing)
            if not norm:
                continue
            in_pantry = matching.ingredient_matches_pantry(ing, pantry_norms)
            entry = needed.setdefault(norm, {"name": ing, "in_pantry": in_pantry, "count": 0, "recipes": []})
            entry["count"] += 1
            entry["recipes"].append(r.get("title", ""))

    have = [v for v in needed.values() if v["in_pantry"]]
    buy = [v for v in needed.values() if not v["in_pantry"]]
    return jsonify({"have": have, "buy": buy})
