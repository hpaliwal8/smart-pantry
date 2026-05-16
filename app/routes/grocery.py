from flask import Blueprint, jsonify, request

from .. import config
from ..services import db

bp = Blueprint("grocery", __name__)
TABLE = config.GROCERY_TABLE


@bp.get("/")
def list_items():
    items = db.query_user(TABLE, config.USER_ID)
    items.sort(key=lambda i: (i.get("purchased", False), i.get("name", "").lower()))
    return jsonify(items)


@bp.post("/")
def add_item():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    item_id = data.get("item_id") or db.new_id("g_")
    attrs = {
        "name": name,
        "quantity": data.get("quantity", 1),
        "unit": data.get("unit", ""),
        "purchased": bool(data.get("purchased", False)),
        "source_recipe_id": data.get("source_recipe_id", ""),
    }
    return jsonify(db.put(TABLE, config.USER_ID, item_id, attrs)), 201


@bp.post("/bulk")
def bulk_add():
    """Add many items at once (used by recipe / meal-plan ingredient ingest)."""
    data = request.get_json(force=True) or {}
    items_in = data.get("items", [])
    created = []
    for it in items_in:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        item_id = db.new_id("g_")
        attrs = {
            "name": name,
            "quantity": it.get("quantity", 1),
            "unit": it.get("unit", ""),
            "purchased": False,
            "source_recipe_id": it.get("source_recipe_id", ""),
        }
        created.append(db.put(TABLE, config.USER_ID, item_id, attrs))
    return jsonify(created), 201


@bp.put("/<item_id>")
def update_item(item_id: str):
    data = request.get_json(force=True) or {}
    existing = db.get(TABLE, config.USER_ID, item_id) or {}
    merged = {**existing, **{k: v for k, v in data.items() if k not in {"user_id", "sk"}}}
    merged.pop("user_id", None)
    merged.pop("sk", None)
    return jsonify(db.put(TABLE, config.USER_ID, item_id, merged))


@bp.delete("/<item_id>")
def delete_item(item_id: str):
    db.delete(TABLE, config.USER_ID, item_id)
    return "", 204


@bp.post("/move_to_pantry")
def move_purchased():
    """Move all purchased items into pantry, then delete them from grocery."""
    items = db.query_user(TABLE, config.USER_ID)
    moved = []
    for it in items:
        if not it.get("purchased"):
            continue
        pid = db.new_id("p_")
        db.put(
            config.PANTRY_TABLE,
            config.USER_ID,
            pid,
            {
                "name": it["name"],
                "quantity": it.get("quantity", 1),
                "unit": it.get("unit", ""),
                "category": "",
                "expiry_date": "",
            },
        )
        db.delete(TABLE, config.USER_ID, it["sk"])
        moved.append(it["name"])
    return jsonify({"moved": moved})
