"""Recipe matching engine. Programmatic (no LLM).

Strategy:
  1. Normalize ingredient strings: strip quantities, units, parentheticals,
     punctuation, and common adjectives. Lowercase. Singularize a small set
     of common food plurals (tomatoes -> tomato).
  2. Compare each recipe ingredient to the pantry as a set of normalized
     tokens. A pantry item matches a recipe ingredient if:
       - exact normalized name match, OR
       - depluralized match, OR
       - one is a substring of the other (handles "chicken breast" vs "chicken")
  3. Score = matched / total. Return a breakdown with matched and missing
     ingredient lists so the UI can show "one ingredient away".
"""
from __future__ import annotations

import re

UNITS = {
    "cup", "cups", "tbsp", "tablespoon", "tablespoons", "tsp", "teaspoon", "teaspoons",
    "oz", "ounce", "ounces", "lb", "lbs", "pound", "pounds", "g", "gram", "grams",
    "kg", "kilo", "kilos", "ml", "l", "liter", "liters", "litre", "litres",
    "pinch", "dash", "clove", "cloves", "slice", "slices", "can", "cans",
    "package", "packages", "pkg", "pack", "stick", "sticks", "bunch", "bunches",
    "head", "heads", "piece", "pieces", "qt", "quart", "quarts", "pt", "pint", "pints",
}

ADJECTIVES = {
    "fresh", "frozen", "dried", "chopped", "diced", "minced", "sliced", "grated",
    "shredded", "crushed", "ground", "whole", "large", "small", "medium",
    "extra", "ripe", "raw", "cooked", "boneless", "skinless", "lean", "organic",
    "unsalted", "salted", "low", "fat", "free", "reduced", "softened", "melted",
    "room", "temperature", "warm", "cold", "hot", "fine", "coarse", "thin", "thick",
    "halved", "quartered", "peeled", "seeded", "trimmed", "cored", "rinsed",
    "drained", "divided", "optional", "to", "taste",
}

NOISE = {"of", "the", "a", "an", "and", "or", "with", "for", "in", "into", "from"}

# Common food plurals -> singular. Avoid generic -s stripping (e.g. "molasses").
PLURALS = {
    "tomatoes": "tomato", "potatoes": "potato", "onions": "onion",
    "carrots": "carrot", "peppers": "pepper", "eggs": "egg",
    "berries": "berry", "strawberries": "strawberry", "blueberries": "blueberry",
    "raspberries": "raspberry", "cherries": "cherry", "leaves": "leaf",
    "loaves": "loaf", "knives": "knife",
}

_FRACTION_RE = re.compile(r"\d+\s*/\s*\d+|\d+(?:\.\d+)?")
_PARENS_RE = re.compile(r"\([^)]*\)")
_NON_ALPHA_RE = re.compile(r"[^a-z\s-]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Strip quantities, units, adjectives, and punctuation."""
    if not text:
        return ""
    s = text.lower().strip()
    s = _PARENS_RE.sub(" ", s)
    s = _FRACTION_RE.sub(" ", s)
    s = _NON_ALPHA_RE.sub(" ", s)
    tokens = [t for t in s.split() if t]
    cleaned: list[str] = []
    for t in tokens:
        if t in UNITS or t in ADJECTIVES or t in NOISE:
            continue
        cleaned.append(PLURALS.get(t, t))
    return _WHITESPACE_RE.sub(" ", " ".join(cleaned)).strip()


def _depluralize(s: str) -> str:
    """Cheap suffix strip for unknown plurals."""
    if len(s) > 3 and s.endswith("ies"):
        return s[:-3] + "y"
    if len(s) > 3 and s.endswith("es") and not s.endswith(("ses", "xes", "zes", "ches", "shes")):
        return s[:-2]
    if len(s) > 3 and s.endswith("s") and not s.endswith(("ss", "us", "is")):
        return s[:-1]
    return s


def ingredient_matches_pantry(ingredient: str, pantry_norms: set[str]) -> bool:
    norm = normalize(ingredient)
    if not norm:
        return False
    # exact
    if norm in pantry_norms:
        return True
    # depluralized
    dep = _depluralize(norm)
    if dep in pantry_norms:
        return True
    # substring (recipe says "chicken breast", pantry has "chicken")
    for p in pantry_norms:
        if not p:
            continue
        if p in norm or norm in p:
            return True
        if _depluralize(p) == dep:
            return True
    return False


def score_recipe(recipe: dict, pantry_items: list[dict]) -> dict:
    """Return {score, matched, missing, total} for a single recipe."""
    pantry_norms = {normalize(p.get("name", "")) for p in pantry_items}
    pantry_norms.discard("")

    ingredients = recipe.get("ingredients", []) or []
    matched: list[str] = []
    missing: list[str] = []
    for ing in ingredients:
        if ingredient_matches_pantry(ing, pantry_norms):
            matched.append(ing)
        else:
            missing.append(ing)

    total = len(ingredients)
    score = (len(matched) / total) if total else 0.0
    return {
        "score": round(score, 3),
        "matched": matched,
        "missing": missing,
        "total": total,
    }


def score_all(recipes: list[dict], pantry_items: list[dict]) -> list[dict]:
    """Return recipes with a 'match' field, sorted by score desc."""
    out = []
    for r in recipes:
        m = score_recipe(r, pantry_items)
        out.append({**r, "match": m})
    out.sort(key=lambda r: r["match"]["score"], reverse=True)
    return out


def smart_suggestions(recipes: list[dict], pantry_items: list[dict], top_n: int = 5) -> list[dict]:
    """Find the smallest set of missing ingredients that unlock the most recipes.

    Greedy: at each step, pick the ingredient that appears in the most
    currently-blocked recipes; mark all recipes that ingredient unlocks; repeat
    until top_n recipes are unlocked or no progress.
    """
    scored = score_all(recipes, pantry_items)
    # only consider recipes that aren't already 100% makeable
    blocked = [r for r in scored if r["match"]["score"] < 1.0 and r["match"]["total"] > 0]
    pantry_norms = {normalize(p.get("name", "")) for p in pantry_items}
    pantry_norms.discard("")

    suggested_buy: list[str] = []
    unlocked: list[dict] = []
    virtual_pantry = set(pantry_norms)

    while blocked and len(unlocked) < top_n:
        # count missing ingredients across blocked recipes (normalized)
        counts: dict[str, int] = {}
        repr_for_norm: dict[str, str] = {}
        for r in blocked:
            for ing in r["match"]["missing"]:
                n = normalize(ing)
                if not n or n in virtual_pantry:
                    continue
                counts[n] = counts.get(n, 0) + 1
                repr_for_norm.setdefault(n, ing)
        if not counts:
            break
        best = max(counts, key=lambda k: counts[k])
        suggested_buy.append(repr_for_norm[best])
        virtual_pantry.add(best)

        new_blocked = []
        for r in blocked:
            rem = [m for m in r["match"]["missing"] if normalize(m) not in virtual_pantry]
            if not rem:
                unlocked.append({**r, "newly_unlocked_by": suggested_buy[:]})
            else:
                new_blocked.append({**r, "match": {**r["match"], "missing": rem}})
        blocked = new_blocked

    return [{"buy": suggested_buy, "unlocks": unlocked}]
