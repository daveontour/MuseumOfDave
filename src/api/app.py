"""FastAPI HTTP Server."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Initialise shared singletons (db, chat_service, templates) before routers load
from .deps import db, chat_service, templates  # noqa: F401

# Import routers
from .routers import admin, emails, attachments, messages, media, chat, relationships, documents, artefacts, sensitive, imap, configuration, saved_responses

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Museum of Dave API",
    description="API server for email processing and retrieval",
    version="1.0.0",
)




# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(admin.router)
#Static file. This comes here to allow the routes in admin to take priority to serve the files that require templating# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.include_router(emails.router)
app.include_router(attachments.router)
app.include_router(messages.router)
app.include_router(media.router)
app.include_router(chat.router)
app.include_router(relationships.router)
app.include_router(documents.router)
app.include_router(artefacts.router)
app.include_router(sensitive.router)
app.include_router(imap.router)
app.include_router(configuration.router)
app.include_router(saved_responses.router)