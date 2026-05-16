from flask import Blueprint, jsonify, request
import requests
from bs4 import BeautifulSoup

from .. import config
from ..services import db, bedrock, matching
from ..services.bedrock import BedrockUnavailable

bp = Blueprint("recipes", __name__)
TABLE = config.RECIPES_TABLE
LIBRARY = "LIBRARY"  # shared partition


def _all_recipes() -> list[dict]:
    user = db.query_user(TABLE, config.USER_ID)
    lib = db.query_user(TABLE, LIBRARY)
    return user + lib


@bp.get("/")
def list_recipes():
    return jsonify(_all_recipes())


@bp.get("/match")
def match_recipes():
    pantry = db.query_user(config.PANTRY_TABLE, config.USER_ID)
    scored = matching.score_all(_all_recipes(), pantry)
    return jsonify(scored)


@bp.get("/suggest")
def smart_suggest():
    pantry = db.query_user(config.PANTRY_TABLE, config.USER_ID)
    top = int(request.args.get("top", 5))
    suggestions = matching.smart_suggestions(_all_recipes(), pantry, top_n=top)
    return jsonify(suggestions)


@bp.post("/")
def create_recipe():
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    library = bool(data.get("library", False))
    owner = LIBRARY if library else config.USER_ID
    recipe_id = data.get("recipe_id") or db.new_id("r_")
    attrs = {
        "title": title,
        "ingredients": data.get("ingredients", []),
        "instructions": data.get("instructions", []),
        "image_url": data.get("image_url", ""),
        "tags": data.get("tags", []),
        "servings": data.get("servings", 0),
    }
    return jsonify(db.put(TABLE, owner, recipe_id, attrs)), 201


@bp.delete("/<recipe_id>")
def delete_recipe(recipe_id: str):
    # try user partition first, then library
    db.delete(TABLE, config.USER_ID, recipe_id)
    db.delete(TABLE, LIBRARY, recipe_id)
    return "", 204


@bp.post("/import")
def import_from_url():
    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400
    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
    except Exception as e:
        return jsonify({"error": f"fetch failed: {e}"}), 502
    # Ignore status code: some sites (AllRecipes) return 403 with full page
    if not resp.text or len(resp.text) < 500:
        return jsonify({"error": "empty or blocked response"}), 502
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    try:
        parsed = bedrock.import_recipe(text)
    except BedrockUnavailable as e:
        return jsonify({"error": str(e)}), 503
    if not parsed:
        return jsonify({"error": "could not extract recipe"}), 422
    parsed.setdefault("ingredients", [])
    parsed.setdefault("instructions", [])
    return jsonify(parsed)


@bp.post("/generate")
def generate_from_title():
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    try:
        parsed = bedrock.generate_recipe(prompt)
    except BedrockUnavailable as e:
        return jsonify({"error": str(e)}), 503
    if not parsed:
        return jsonify({"error": "generation failed"}), 502
    return jsonify(parsed)
