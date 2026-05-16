"""Chef Charlie chat endpoint.

Builds a real-time context snapshot (pantry, grocery, meal plan, recipe titles)
and asks Bedrock for a structured block response. v1 does not persist history;
each request is stateless, with optional client-supplied history.
"""
from flask import Blueprint, jsonify, request

from .. import config
from ..services import db, bedrock
from ..services.bedrock import BedrockUnavailable

bp = Blueprint("chat", __name__)


def _build_context() -> dict:
    pantry = db.query_user(config.PANTRY_TABLE, config.USER_ID)
    grocery = db.query_user(config.GROCERY_TABLE, config.USER_ID)
    meals = db.query_user(config.MEALS_TABLE, config.USER_ID)
    user_recipes = db.query_user(config.RECIPES_TABLE, config.USER_ID)
    lib_recipes = db.query_user(config.RECIPES_TABLE, "LIBRARY")
    recipes = user_recipes + lib_recipes

    def slim_pantry(p):
        return {"name": p.get("name"), "qty": p.get("quantity"), "unit": p.get("unit")}

    def slim_recipe(r):
        return {
            "recipe_id": r.get("sk"),
            "title": r.get("title"),
            "ingredient_count": len(r.get("ingredients", [])),
        }

    return {
        "pantry": [slim_pantry(p) for p in pantry],
        "grocery": [
            {"name": g.get("name"), "purchased": g.get("purchased", False)}
            for g in grocery
        ],
        "meal_plan": [
            {"day": m.get("day"), "meal": m.get("meal"), "recipe_id": m.get("recipe_id")}
            for m in meals
        ],
        "recipes": [slim_recipe(r) for r in recipes],
    }


@bp.post("/")
def chat():
    data = request.get_json(force=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    if not message:
        return jsonify({"error": "message required"}), 400
    context = _build_context()
    try:
        blocks = bedrock.chef_chat(message, context, history)
    except BedrockUnavailable as e:
        return jsonify({"error": str(e)}), 503
    return jsonify({"blocks": blocks})
