"""Provider-agnostic base chat service and shared utilities."""

import json
import os
import random
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from pympler import asizeof

from ..database import Database
from ..database.models import Message, Email, CompleteProfile, MediaMetadata, Artefact, FacebookAlbum

try:
    from tavily import TavilyClient
except ImportError:
    print("[BaseChatService] Warning: tavily-python not installed. Tavily search will be disabled.")
    TavilyClient = None


def parse_wrapped_json(input_str):
    clean_str = input_str.strip()
    if clean_str.startswith('(') and clean_str.endswith(')'):
        clean_str = clean_str[1:-1].strip()
    try:
        return json.loads(clean_str)
    except json.JSONDecodeError as e:
        return f"Failed to parse: {e}"


class BaseChatService:
    """Provider-agnostic base class containing shared tool handlers, session management, and prompt loading.

    Subclasses must implement:
        - generate_response()
        - _get_tools_config()
    and set self.client and self.model_name in their __init__ before calling super().__init__().
    """

    def __init__(self, subject_config_service=None, config_service=None):
        self._subject_config_service = subject_config_service
        self._config_service = config_service

        # Tavily search client (shared across providers)
        _get = config_service.get if config_service else os.getenv
        tavily_api_key = _get("TAVILY_API_KEY")
        self.tavily_client = None
        if TavilyClient and tavily_api_key:
            try:
                self.tavily_client = TavilyClient(api_key=tavily_api_key)
            except Exception as e:
                print(f"[BaseChatService.__init__] Warning: Could not initialize Tavily client: {str(e)}")
        else:
            if not TavilyClient:
                print("[BaseChatService.__init__] Warning: Tavily library not available")
            elif not tavily_api_key:
                print("[BaseChatService.__init__] Warning: TAVILY_API_KEY not set. Tavily search disabled.")

        self.voice_instructions_list = None
        self.voice = "expert"
        self.mood = "neutral"
        self.psychological_profile = None
        self.writing_style = None
        self.voice_instructions = None
        self.system_prompt = None
        self.session_turns = []
        self.db = None
        self.current_conversation_id = None
        self.subject_name = None

        try:
            self.voice_instructions_list = self._load_voice_instructions()
            if self.voice_instructions_list and self.voice in self.voice_instructions_list:
                self.voice_instructions = self.voice_instructions_list[self.voice]
        except Exception as e:
            print(f"[BaseChatService.__init__] Error loading voice instructions: {e}")

    def set_database(self, db: Database):
        """Set the database instance for retrieving reference documents."""
        self.db = db
        self.reload_system_prompt(db=db)

    def set_voice(self, voice: str):
        """Sets the voice for the session."""
        self.voice = voice
        if not self.voice_instructions_list:
            self.voice_instructions_list = self._load_voice_instructions()
        try:
            self.voice_instructions = self.voice_instructions_list[voice]
        except KeyError:
            print(f"[BaseChatService.set_voice] Voice '{voice}' not found. Using default voice 'expert'.")
            self.voice = "expert"
            self.voice_instructions = self.voice_instructions_list[self.voice]

    def set_mood(self, mood: str):
        """Sets the mood for the session."""
        self.mood = mood

    def set_psychological_profile(self, psychological_profile: str):
        """Sets the psychological profile for the session."""
        self.psychological_profile = psychological_profile

    def set_writing_style(self, writing_style: str):
        """Sets the writing style for the session."""
        self.writing_style = writing_style

    def clear_session(self):
        """Clears the session turns list and conversation context."""
        self.session_turns = []
        self.current_conversation_id = None

    def load_conversation_turns(self, conversation_id: int, limit: int = 30, db: Optional[Database] = None) -> List[Dict[str, Any]]:
        """Load conversation turns from database and populate session_turns."""
        if db is None:
            db = self.db
        if not db:
            print("[BaseChatService.load_conversation_turns] ERROR: Database not available")
            return []
        from ..services.chat_conversation_service import ChatConversationService
        conversation_service = ChatConversationService(db=db)
        try:
            turns = conversation_service.get_conversation_turns(conversation_id, limit=limit)
            session_turns = [{"user_input": t.user_input, "response_text": t.response_text} for t in turns]
            self.session_turns = session_turns
            self.current_conversation_id = conversation_id
            print(f"[BaseChatService.load_conversation_turns] Loaded {len(session_turns)} turns for conversation {conversation_id}")
            return session_turns
        except Exception as e:
            print(f"[BaseChatService.load_conversation_turns] Error: {str(e)}")
            import traceback; traceback.print_exc()
            return []

    def save_turn(self, conversation_id: int, user_input: str, response_text: str, voice: str, temperature: float, db: Optional[Database] = None) -> bool:
        """Save a conversation turn to the database."""
        if db is None:
            db = self.db
        if not db:
            print("[BaseChatService.save_turn] ERROR: Database not available")
            return False
        from ..services.chat_conversation_service import ChatConversationService
        conversation_service = ChatConversationService(db=db)
        try:
            conversation_service.save_turn(conversation_id, user_input, response_text, voice, temperature)
            return True
        except Exception as e:
            print(f"[BaseChatService.save_turn] Error saving turn: {str(e)}")
            import traceback; traceback.print_exc()
            return False

    def _load_voice_instructions(self):
        """Loads voice instructions from the JSON file and replaces placeholders."""
        try:
            with open('src/api/static/data/voice_instructions.json', 'r', encoding='utf-8') as file:
                voice_data = json.load(file)
                if self.subject_name:
                    for voice_key, voice_info in voice_data.items():
                        if isinstance(voice_info, dict):
                            for key, value in voice_info.items():
                                if isinstance(value, str):
                                    voice_info[key] = value.replace('{SUBJECT_NAME}', self.subject_name)
                return voice_data
        except FileNotFoundError:
            print("[BaseChatService._load_voice_instructions] voice_instructions.json not found.")
            return {"expert": {"name": "Expert", "description": "Professional Expert", "instructions": "You are a professional expert."}}

    def reload_system_prompt(self, db: Database = None):
        """Reload system prompt from database with file fallback."""
        if db is None:
            db = self.db
        if db and self._subject_config_service:
            try:
                self.subject_name = self._subject_config_service.get_subject_name()
                self.subject_gender = self._subject_config_service.get_gender()
                self.subject_family_name = self._subject_config_service.get_family_name()
                self.subject_other_names = self._subject_config_service.get_other_names()
                self.subject_email_addresses = self._subject_config_service.get_email_addresses()
                self.subject_phone_numbers = self._subject_config_service.get_phone_numbers()
                self.subject_whatsapp_handle = self._subject_config_service.get_whatsapp_handle()
                self.subject_instagram_handle = self._subject_config_service.get_instagram_handle()
                self.voice_instructions_list = self._load_voice_instructions()
                if self.voice_instructions_list and self.voice in self.voice_instructions_list:
                    self.voice_instructions = self.voice_instructions_list[self.voice]
                system_instructions = self._subject_config_service.get_system_instructions()
                core_instructions = self._subject_config_service.get_core_system_instructions()
                instructions = system_instructions
                if core_instructions:
                    instructions = instructions + "\n\n" + core_instructions
                if self.subject_name:
                    instructions = instructions.replace('{SUBJECT_NAME}', self.subject_name)
                self.system_prompt = instructions
                print(f"[BaseChatService.reload_system_prompt] Loaded system instructions ({len(instructions)} chars)")
                return
            except Exception as e:
                print(f"[BaseChatService.reload_system_prompt] Error loading from database: {e}")
        self.system_prompt = self._load_system_prompt_from_file()
        if not self.voice_instructions_list:
            self.voice_instructions_list = self._load_voice_instructions()
            if self.voice_instructions_list and self.voice in self.voice_instructions_list:
                self.voice_instructions = self.voice_instructions_list[self.voice]

    def _load_system_prompt_from_file(self):
        """Loads system prompt from a text file."""
        try:
            with open('src/api/static/data/system_instructions_chat.txt', 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            return "System instructions could not be loaded."

    def _search_tavily(self, query: str) -> Dict[str, Any]:
        """Perform a web search using Tavily."""
        if not self.tavily_client:
            return {"error": "Tavily search is not configured (TAVILY_API_KEY missing or client initialization failed)"}
        try:
            return self.tavily_client.search(query, search_depth="advanced", max_results=5)
        except Exception as e:
            return {"error": str(e), "query": query}

    def _get_current_time(self) -> Dict[str, Any]:
        """Get the current date and time."""
        from datetime import datetime
        return {"current_time": datetime.now().isoformat(), "timezone": "UTC"}

    def _get_messages_by_chat_session(self, chat_session: str) -> Dict[str, Any]:
        """Get all iMessage/WhatsApp/SMS/Facebook messages for a specific chat session."""
        if not self.db:
            return {"error": "Database not configured", "chat_session": chat_session, "message_count": 0, "messages": []}
        session = self.db.get_session()
        try:
            messages = session.query(Message).filter(
                Message.chat_session.like(f"%{chat_session}%")
            ).order_by(Message.message_date.asc()).all()
            messages_list = [{"id": m.id, "message_date": m.message_date.isoformat() if m.message_date else None,
                              "sender_name": m.sender_name or "Unknown", "sender_id": m.sender_id or "",
                              "type": m.type or "", "text": m.text or "", "service": m.service or "",
                              "subject": m.subject or None} for m in messages]
            return {"chat_session": chat_session, "message_count": len(messages), "messages": messages_list}
        except Exception as e:
            print(f"[BaseChatService._get_imessages_by_chat_session] Error: {str(e)}")
            return {"error": str(e), "chat_session": chat_session, "message_count": 0, "messages": []}
        finally:
            session.close()

    def _get_emails_by_contact(self, name: str) -> Dict[str, Any]:
        """Get emails where sender or receiver matches the specified name."""
        if not self.db:
            return {"error": "Database not configured", "contact_name": name, "email_count": 0, "emails": []}
        session = self.db.get_session()
        try:
            emails = session.query(Email).filter(
                or_(Email.from_address.like(f"%{name}%"), Email.to_addresses.like(f"%{name}%"))
            ).order_by(Email.date.asc()).all()
            emails_list = [{"id": e.id, "date": e.date.isoformat() if e.date else None,
                            "from_address": e.from_address or "", "to_addresses": e.to_addresses or "",
                            "subject": e.subject or "", "plain_text": e.plain_text or e.snippet or "",
                            "has_attachments": e.has_attachments or False} for e in emails]
            return {"contact_name": name, "email_count": len(emails), "emails": emails_list}
        except Exception as e:
            print(f"[BaseChatService._get_emails_by_contact] Error: {str(e)}")
            return {"error": str(e), "contact_name": name, "email_count": 0, "emails": []}
        finally:
            session.close()

    def _get_subject_writing_examples(self) -> Dict[str, Any]:
        """Get random writing examples from the subject's messages."""
        from sqlalchemy import func as sqlfunc
        messages = self.db.get_session().query(Message).filter(
            Message.sender_id == self.subject_name, Message.type == "text"
        ).order_by(sqlfunc.random()).limit(2000).all()
        messages_list = [{"id": m.id, "message_date": m.message_date.isoformat() if m.message_date else None,
                          "sender_name": m.sender_name or "Unknown", "sender_id": m.sender_id or "",
                          "type": m.type or "", "text": m.text or "", "service": m.service or "",
                          "subject": m.subject or None} for m in messages]
        return {"subject_writing_examples": messages_list}

    def _get_all_messages_by_contact(self, name: str) -> Dict[str, Any]:
        """Get all messages for a contact (iMessages + emails) and return a relationship summary."""
        from .gemini_service import GeminiService
        messages = self._get_messages_by_chat_session(name)
        emails = self._get_emails_by_contact(name)
        slimedEmails = [e for e in emails["emails"] if e["plain_text"] and e["subject"] and e["from_address"] and e["to_addresses"] and e["date"] and e["id"]]
        while asizeof.asizeof(messages["messages"] + slimedEmails) > 800000:
            for i in range(1, int(len(slimedEmails) * 0.1)):
                slimedEmails.pop(random.randint(0, len(slimedEmails) - 1))
        for email in slimedEmails:
            messages["messages"].append({"id": email["id"], "message_date": email["date"],
                                          "sender_name": email["from_address"], "sender_id": email["from_address"],
                                          "type": "email", "text": email["plain_text"], "service": "email"})
        # geminiService = GeminiService()
        # summary = geminiService.summarize_relationships(messages, name)
        # create a JSON string of the messages and emails
        messages_json = json.dumps(messages)
        emails_json = json.dumps(emails)
        summary = f"Messages: {messages_json}\nEmails: {emails_json}"
        return {"contact_name": name, "relationshipSummary": summary}

    def get_complete_profile_by_name(self, name: str) -> Dict[str, Any]:
        """Build a multi-step relationship profile for a contact and save it to the database."""
        from .gemini_service import GeminiService
        imessages = self._get_messages_by_chat_session(name)
        messages = imessages["messages"]
        emails = self._get_emails_by_contact(name)
        slimedEmails = [e for e in emails["emails"] if e["plain_text"] and e["subject"] and e["from_address"] and e["to_addresses"] and e["date"] and e["id"]]
        for email in slimedEmails:
            messages.append({"id": email["id"], "message_date": email["date"],
                             "sender_name": email["from_address"], "sender_id": email["from_address"],
                             "type": "email", "text": email["plain_text"], "service": "email"})
        messageChunks = []
        currentChunk = []
        for message in messages:
            if asizeof.asizeof(currentChunk) + asizeof.asizeof(message) < 800000:
                currentChunk.append(message)
            else:
                messageChunks.append(currentChunk)
                currentChunk = [message]
        if currentChunk:
            messageChunks.append(currentChunk)
        interimSummary = ""
        geminiService = GeminiService()
        for idx, chunk in enumerate(messageChunks):
            interimSummary = geminiService.summarize_relationships_multistep(chunk, interimSummary, idx + 1, len(messageChunks))
        if self.db:
            session = self.db.get_session()
            try:
                existing = session.query(CompleteProfile).filter(CompleteProfile.name == name).first()
                if existing:
                    existing.profile = interimSummary
                else:
                    session.add(CompleteProfile(name=name, profile=interimSummary))
                session.commit()
            except Exception as e:
                session.rollback()
                raise
            finally:
                session.close()

    def _search_facebook_albums(self, keyword: str) -> Dict[str, Any]:
        """Search Facebook albums by partial keyword match on name or description."""
        if not self.db:
            return {"error": "Database not configured", "albums": [], "count": 0}
        session = self.db.get_session()
        try:
            pattern = f"%{keyword}%"
            albums = session.query(FacebookAlbum).filter(
                or_(FacebookAlbum.name.ilike(pattern), FacebookAlbum.description.ilike(pattern))
            ).order_by(FacebookAlbum.name.asc()).all()
            result = [{"id": a.id, "name": a.name, "description": a.description or "",
                       "cover_photo_uri": a.cover_photo_uri or "",
                       "last_modified": a.last_modified_timestamp.isoformat() if a.last_modified_timestamp else None,
                       "media_item_count": len(a.media_items)} for a in albums]
            return {"keyword": keyword, "count": len(result), "albums": result}
        finally:
            session.close()

    def _get_unique_tags_count(self) -> Dict[str, Any]:
        """Return the unique tags in the media_items and artefacts tables, with counts."""
        if not self.db:
            return {"error": "Database not configured"}
        session = self.db.get_session()
        try:
            media_tags: set[str] = set()
            for (raw,) in session.query(MediaMetadata.tags).filter(MediaMetadata.tags.isnot(None), MediaMetadata.tags != ""):
                media_tags.update(t.strip() for t in raw.split(",") if t.strip())
            artefact_tags: set[str] = set()
            for (raw,) in session.query(Artefact.tags).filter(Artefact.tags.isnot(None), Artefact.tags != ""):
                artefact_tags.update(t.strip() for t in raw.split(",") if t.strip())
            combined = media_tags | artefact_tags
            return {"media_items_unique_tag_count": len(media_tags), "media_items_tags": sorted(media_tags),
                    "artefacts_unique_tag_count": len(artefact_tags), "artefacts_tags": sorted(artefact_tags),
                    "combined_unique_tag_count": len(combined), "combined_tags": sorted(combined)}
        finally:
            session.close()

    def _execute_function_call(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a function call by routing to the appropriate handler method."""
        function_handlers = {
            "get_current_time": self._get_current_time,
            "get_imessages_by_chat_session": self._get_messages_by_chat_session,
            "get_emails_by_contact": self._get_emails_by_contact,
            "get_subject_writing_examples": self._get_subject_writing_examples,
            "search_tavily": self._search_tavily,
            "get_all_messages_by_contact": self._get_all_messages_by_contact,
            "get_unique_tags_count": self._get_unique_tags_count,
            "search_facebook_albums": self._search_facebook_albums,
        }
        if function_name not in function_handlers:
            raise ValueError(f"Unknown function: {function_name}")
        handler = function_handlers[function_name]
        print(f"[BaseChatService._execute_function_call] Executing: {function_name} with args: {args}")
        try:
            result = handler(**args) if args else handler()
            return result
        except Exception as e:
            print(f"[BaseChatService._execute_function_call] Error executing {function_name}: {str(e)}")
            import traceback; traceback.print_exc()
            raise
