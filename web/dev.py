"""Dev server entry point — run with: uvicorn web.dev:app --reload"""

import os
from dotenv import load_dotenv

load_dotenv()

# Force SQLite for local dev if no DATABASE_URL is set
os.environ.pop("DATABASE_URL", None)

from db.schema import init_db

init_db()

from web import create_app

app = create_app()
