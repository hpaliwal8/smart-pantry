"""Create all DynamoDB tables. Idempotent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.services import db  # noqa: E402

if __name__ == "__main__":
    print("Ensuring tables exist...")
    statuses = db.ensure_tables()
    for name, status in statuses.items():
        print(f"  {name}: {status}")
    print("Done.")
