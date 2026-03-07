"""Shared application dependencies."""
from pathlib import Path
from fastapi.templating import Jinja2Templates

from src.services.subject_configuration_service import SubjectConfigurationService
from ..database import Database
from ..services.gemini_service import ChatService
from ..services.claude_service import ClaudeChatService
from ..services.configuration_service import ConfigurationService
from ..config import get_config

db = Database(get_config())

config_service = ConfigurationService(db)

subject_config_service = SubjectConfigurationService(db=db, config_service=config_service)
chat_service = ChatService(subject_config_service=subject_config_service, config_service=config_service)
chat_service.set_database(db)

claude_chat_service = ClaudeChatService(subject_config_service=subject_config_service, config_service=config_service)
claude_chat_service.set_database(db)

# Jinja2 templates - shared across routers
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
