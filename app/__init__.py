import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

    from .routes.pages import bp as pages_bp
    from .routes.pantry import bp as pantry_bp
    from .routes.recipes import bp as recipes_bp
    from .routes.grocery import bp as grocery_bp
    from .routes.meals import bp as meals_bp
    from .routes.chat import bp as chat_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(pantry_bp, url_prefix="/api/pantry")
    app.register_blueprint(recipes_bp, url_prefix="/api/recipes")
    app.register_blueprint(grocery_bp, url_prefix="/api/grocery")
    app.register_blueprint(meals_bp, url_prefix="/api/meals")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")

    return app
