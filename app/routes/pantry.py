from flask import Blueprint, jsonify, request

from .. import config
from ..services import db

bp = Blueprint("pantry", __name__)
TABLE = config.PANTRY_TABLE


@bp.get("/")
def list_items():
    items = db.query_user(TABLE, config.USER_ID)
    items.sort(key=lambda i: i.get("name", "").lower())
    return jsonify(items)


@bp.post("/")
def add_item():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    item_id = data.get("item_id") or db.new_id("p_")
    attrs = {
        "name": name,
        "quantity": data.get("quantity", 1),
        "unit": data.get("unit", ""),
        "category": data.get("category", ""),
        "expiry_date": data.get("expiry_date", ""),
    }
    item = db.put(TABLE, config.USER_ID, item_id, attrs)
    return jsonify(item), 201


@bp.put("/<item_id>")
def update_item(item_id: str):
    data = request.get_json(force=True) or {}
    existing = db.get(TABLE, config.USER_ID, item_id) or {}
    merged = {**existing, **{k: v for k, v in data.items() if k not in {"user_id", "sk"}}}
    merged.pop("user_id", None)
    merged.pop("sk", None)
    item = db.put(TABLE, config.USER_ID, item_id, merged)
    return jsonify(item)


@bp.delete("/<item_id>")
def delete_item(item_id: str):
    db.delete(TABLE, config.USER_ID, item_id)
    return "", 204
