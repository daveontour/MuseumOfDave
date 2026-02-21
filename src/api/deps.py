"""Shared application dependencies."""
from pathlib import Path
from fastapi.templating import Jinja2Templates
from ..database import Database
from ..services.gemini_service import ChatService
from ..config import get_config

db = Database(get_config())

chat_service = ChatService()
chat_service.set_database(db)

# Jinja2 templates - shared across routers
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
