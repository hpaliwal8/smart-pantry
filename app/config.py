import os

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6")

PANTRY_TABLE = os.environ.get("PANTRY_TABLE", "pantryai_pantry")
RECIPES_TABLE = os.environ.get("RECIPES_TABLE", "pantryai_recipes")
GROCERY_TABLE = os.environ.get("GROCERY_TABLE", "pantryai_grocery")
MEALS_TABLE = os.environ.get("MEALS_TABLE", "pantryai_meals")
CHAT_TABLE = os.environ.get("CHAT_TABLE", "pantryai_chat")

USER_ID = os.environ.get("USER_ID", "demo-user")
