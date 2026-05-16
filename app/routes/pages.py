"""Page routes — server-rendered Jinja shells. The JS hydrates from /api/*."""
from flask import Blueprint, render_template

bp = Blueprint("pages", __name__)


@bp.get("/")
def home():
    return render_template("pantry.html", active="pantry")


@bp.get("/recipes")
def recipes_page():
    return render_template("recipes.html", active="recipes")


@bp.get("/grocery")
def grocery_page():
    return render_template("grocery.html", active="grocery")


@bp.get("/meals")
def meals_page():
    return render_template("meals.html", active="meals")
