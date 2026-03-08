"""Claude (Anthropic) chat service — drop-in alternative to ChatService."""

import base64
import json
import os
import re
from typing import Any, Dict, List, Optional

import anthropic

from ..database import Database
from .base_chat_service import BaseChatService, parse_wrapped_json


class ClaudeChatService(BaseChatService):
    """Chat service backed by Anthropic Claude.

    Implements the same public interface as ChatService (Gemini) so it can be
    swapped in transparently via the ``provider`` request field.

    Tool calling uses the Anthropic SDK's native tool-use API.
    Reference documents (available_for_task=True) are attached inline as
    Anthropic document content blocks (text or base64 PDF).
    """

    _TEXT_MIME_PREFIXES = ("text/", "application/json", "application/xml")

    def __init__(self, subject_config_service=None, config_service=None):
        print("[ClaudeChatService.__init__] Starting initialization...")
        _get = config_service.get if config_service else os.getenv
        api_key = _get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model_name = _get("CLAUDE_MODEL_NAME", "claude-sonnet-4-6") or "claude-sonnet-4-6"
    
        super().__init__(subject_config_service, config_service)
        print(f"[ClaudeChatService.__init__] Initialization complete. Using model: {self.model_name}")

    # ------------------------------------------------------------------
    # Tool declarations — Anthropic format
    # ------------------------------------------------------------------

    def _get_tools_config(self) -> List[Dict[str, Any]]:
        """Return tool definitions in Anthropic's tool schema format."""
        return [
            {
                "name": "get_current_time",
                "description": "Get the current date and time in ISO format. Useful when user asks about the current time or date.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "get_imessages_by_chat_session",
                "description": "Get all messages for WhatsApp, SMS, iMessage and Facebook messages for a specific chat. Use this when the user asks about messages, conversations, or chats with a specific person or group.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "chat_session": {"type": "string", "description": "The chat session name (person or group name) to retrieve messages for"}
                    },
                    "required": ["chat_session"],
                },
            },
            {
                "name": "get_emails_by_contact",
                "description": "Get plain text of emails where the sender or receiver matches the specified name or email address. Use this when the user asks about emails with a specific person or contact.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The name or email address to search for in sender (from_address) or receiver (to_addresses) fields"}
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "get_all_messages_by_contact",
                "description": "Get all messages for a specific contact. Use this when the user asks about messages with a specific person or contact or when background information is needed on that person.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The name or email address to search"}
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "get_subject_writing_examples",
                "description": "Get the subject writing examples. Use this when the user asks about subject writing examples.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "search_tavily",
                "description": "Perform a web search for real-time information and current events using Tavily. Use this when the user asks about current events, news, or information not available in the internal database.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"}
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_facebook_albums",
                "description": "Search Facebook photo albums by a partial keyword match against album name or description. Use this when the user asks about Facebook albums, photo collections, or wants to find albums related to a topic or event.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "Partial keyword to search for in album names and descriptions"}
                    },
                    "required": ["keyword"],
                },
            },
            {
                "name": "get_unique_tags_count",
                "description": "Get the unique tags used in the media items (photos/videos) library and the artefacts collection, along with counts. Use this when the user asks what tags exist, how many tags there are, or wants a summary of tagging across the museum collections.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "get_reference_document",
                "description": "Retrieve the full content of one or more reference documents by their IDs. Call this when the user's question is best answered using a specific reference document listed in the system prompt.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "document_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "List of reference document IDs to retrieve.",
                        }
                    },
                    "required": ["document_ids"],
                },
            },
        ]

    # ------------------------------------------------------------------
    # Reference document helpers
    # ------------------------------------------------------------------

    def _build_reference_manifest(self, db: Database):
        """Return (manifest_text, available_docs) for all available_for_task docs."""
        from ..database.models import ReferenceDocument
        available_docs = []
        try:
            session = db.get_session()
            try:
                docs = session.query(ReferenceDocument).filter(
                    ReferenceDocument.available_for_task == True
                ).all()
                for doc in docs:
                    available_docs.append({
                        "id": doc.id,
                        "filename": doc.filename,
                        "title": doc.title or doc.filename,
                        "description": doc.description or "",
                        "content_type": doc.content_type or "",
                    })
            finally:
                session.close()
        except Exception as e:
            print(f"[ClaudeChatService] Warning: Could not retrieve reference documents: {e}")

        if not available_docs:
            return "", []

        lines = [
            "## Available Reference Documents",
            "Use the `get_reference_document` tool to retrieve one or more of these documents when relevant.\n",
        ]
        for doc in available_docs:
            lines.append(f"- **ID {doc['id']}** — {doc['title']}: {doc['description']}")
        return "\n".join(lines), available_docs

    def _fetch_reference_documents(self, document_ids: list) -> dict:
        """Load reference document content by ID. Used as the get_reference_document tool handler."""
        from ..database.models import ReferenceDocument
        results = []
        db = self._current_db
        session = db.get_session()
        try:
            for doc_id in document_ids:
                doc = session.query(ReferenceDocument).filter(ReferenceDocument.id == doc_id).first()
                if doc is None:
                    results.append({"id": doc_id, "error": "Document not found"})
                    continue
                content_type = (doc.content_type or "").lower()
                if content_type == "application/pdf":
                    results.append({
                        "id": doc_id,
                        "title": doc.title or doc.filename,
                        "content_type": "application/pdf",
                        "encoding": "base64",
                        "content": base64.standard_b64encode(doc.data).decode("ascii"),
                    })
                else:
                    try:
                        text = doc.data.decode("utf-8", errors="replace")
                    except Exception:
                        text = "[Binary content — cannot decode]"
                    results.append({
                        "id": doc_id,
                        "title": doc.title or doc.filename,
                        "content": text,
                    })
                print(f"[ClaudeChatService] Fetched reference doc via tool: {doc.filename}")
        finally:
            session.close()
        return {"documents": results}

    def _get_reference_document_blocks(self, db: Database):
        """Return (doc_blocks, referenced_files) for all available_for_task docs."""
        from ..database.models import ReferenceDocument
        blocks = []
        referenced_files = []
        try:
            session = db.get_session()
            try:
                docs = session.query(ReferenceDocument).filter(
                    ReferenceDocument.available_for_task == True
                ).all()
                for doc in docs:
                    content_type = (doc.content_type or "").lower()
                    if content_type == "application/pdf":
                        block = {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": base64.standard_b64encode(doc.data).decode("ascii"),
                            },
                        }
                    elif any(content_type.startswith(p) for p in self._TEXT_MIME_PREFIXES):
                        # Anthropic supports text/plain, text/html, text/markdown, text/csv;
                        # everything else (application/json, etc.) is sent as text/plain
                        _SUPPORTED_TEXT_TYPES = {"text/plain", "text/html", "text/markdown", "text/csv"}
                        media_type = content_type if content_type in _SUPPORTED_TEXT_TYPES else "text/plain"
                        block = {
                            "type": "document",
                            "source": {
                                "type": "text",
                                "media_type": media_type,
                                "data": doc.data.decode("utf-8", errors="replace"),
                            },
                        }
                    else:
                        print(f"[ClaudeChatService] Skipping reference doc '{doc.filename}': unsupported type '{doc.content_type}'")
                        continue

                    if doc.title or doc.filename:
                        block["title"] = doc.title or doc.filename

                    blocks.append(block)
                    referenced_files.append({"id": doc.id, "filename": doc.filename, "title": doc.title})
                    print(f"[ClaudeChatService] Attached reference doc: {doc.filename}")
            finally:
                session.close()
        except Exception as e:
            print(f"[ClaudeChatService] Warning: Could not retrieve reference documents: {e}")
        return blocks, referenced_files

    def _execute_function_call(self, function_name: str, args: dict) -> dict:
        if function_name == "get_reference_document":
            return self._fetch_reference_documents(args.get("document_ids", []))
        return super()._execute_function_call(function_name, args)

    # ------------------------------------------------------------------
    # Core response generation
    # ------------------------------------------------------------------

    def generate_response(
        self,
        user_input: str,
        temperature: float = 0.0,
        voice: str = "expert",
        mood: str = "neutral",
        psychological_profile: str = None,
        writing_style: str = None,
        conversation_id: Optional[int] = None,
        db: Optional[Database] = None,
        companionMode: Optional[bool] = False,
    ):
        """Generate a chat response using the Claude API with tool calling.

        Returns the same (response_text, metadata_json_str) tuple as ChatService.
        """
        if db is None:
            db = self.db
        self._current_db = db

        # --- Voice / mood setup ---
        self.voice = voice
        if not self.voice_instructions_list:
            self.voice_instructions_list = self._load_voice_instructions()
        try:
            self.voice_instructions = self.voice_instructions_list[voice]
        except KeyError:
            self.voice = "expert"
            self.voice_instructions = self.voice_instructions_list[self.voice]

        self.mood = "neutral"
        self.set_psychological_profile(None)
        self.set_writing_style(None)

        if self.voice == "owner":
            try:
                self.mood = mood
                configuration = self._subject_config_service.get_configuration() if self._subject_config_service else None
                if configuration:
                    self.set_psychological_profile(configuration.psychological_profile_ai)
                    self.set_writing_style(configuration.writing_style_ai)
            except Exception as e:
                print(f"[ClaudeChatService.generate_response] Warning: Could not set owner voice: {e}")

        subject_name = self._subject_config_service.get_subject_name() if self._subject_config_service else "Unknown"
        subject_gender = self._subject_config_service.get_gender() if self._subject_config_service else "Male"

        # --- Build system prompt ---
        system_instructions = self._subject_config_service.get_system_instructions() if self._subject_config_service else ""
        core_instructions = self._subject_config_service.get_core_system_instructions() if self._subject_config_service else ""

        for src, dst in [("{SUBJECT_NAME}", subject_name),
                         ("{he}", "he" if subject_gender == "Male" else "she"),
                         ("{him}", "him" if subject_gender == "Male" else "her"),
                         ("{his}", "his" if subject_gender == "Male" else "her")]:
            system_instructions = system_instructions.replace(src, dst)
            core_instructions = core_instructions.replace(src, dst)

        voice_instructions_text = self.voice_instructions.get("instructions", "") if self.voice_instructions else ""
        for src, dst in [("{SUBJECT_NAME}", subject_name),
                         ("{he}", "he" if subject_gender == "Male" else "she"),
                         ("{him}", "him" if subject_gender == "Male" else "her"),
                         ("{his}", "his" if subject_gender == "Male" else "her")]:
            voice_instructions_text = voice_instructions_text.replace(src, dst)

        system_prompt = core_instructions + "\n\n**Your Personae:**\n" + voice_instructions_text + "\n\n**Additional Information:**\n" + system_instructions

        manifest_text, available_docs = self._build_reference_manifest(db) if db else ("", [])
        if manifest_text:
            system_prompt = system_prompt + "\n\n" + manifest_text

        # --- Load conversation history ---
        if conversation_id is not None and conversation_id != self.current_conversation_id:
            if db:
                self.load_conversation_turns(conversation_id, limit=30, db=db)
        if conversation_id is not None:
            self.current_conversation_id = conversation_id

        # --- Build messages list ---
        messages: List[Dict[str, Any]] = []

        # Conversation history (last 20 turns)
        recent_turns = self.session_turns[-20:]
        for turn in recent_turns:
            messages.append({"role": "user", "content": turn.get("user_input", "")})
            messages.append({"role": "assistant", "content": turn.get("response_text", "")})

        # Companion / owner mode additions
        user_content = user_input
        extra_parts = []
        if self.voice == "owner":
            extra_parts.append(f"IMPORTANT: Respond in the first person voice as the owner of the subject's life.")
            extra_parts.append(f"IMPORTANT: Your current mood is {self.mood}")
            if self.psychological_profile:
                extra_parts.append(f"IMPORTANT: Respond consistent with your psychological profile: {self.psychological_profile}")
            if self.writing_style:
                extra_parts.append(f"IMPORTANT: Respond consistent with your writing style: {self.writing_style}")
        if companionMode:
            extra_parts.append("IMPORTANT: You are in companion mode. Respond conversationally as a friend, not as an assistant.")
        if extra_parts:
            user_content = "\n".join(extra_parts) + "\n\nUser input:\n" + user_input
        else:
            user_content = user_input

        messages.append({"role": "user", "content": user_content})

        # --- Tool calling loop ---
        tools = self._get_tools_config()
        function_calls_made = []
        input_tokens = 0
        output_tokens = 0

        claude_temperature = min(temperature, 1.0)
        max_iterations = 5
        for iteration in range(1, max_iterations + 1):
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=8096,
                temperature=claude_temperature,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )
            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens

            if response.stop_reason != "tool_use":
                break

            # Extract tool_use blocks
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            if not tool_use_blocks:
                break

            print(f"[ClaudeChatService.generate_response] {len(tool_use_blocks)} tool call(s) in iteration {iteration}")

            # Append assistant message with tool calls
            messages.append({"role": "assistant", "content": response.content})

            # Execute tools and build tool_result blocks
            tool_results = []
            for block in tool_use_blocks:
                func_name = block.name
                func_args = dict(block.input) if block.input else {}
                function_calls_made.append({"name": func_name, "arguments": func_args, "iteration": iteration})
                print(f"[ClaudeChatService.generate_response] Calling {func_name} with {func_args}")
                try:
                    result = self._execute_function_call(func_name, func_args)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
                except Exception as e:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": str(e)}),
                        "is_error": True,
                    })

            messages.append({"role": "user", "content": tool_results})

        # --- Extract final text ---
        response_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                response_text += block.text
        response_text = response_text.strip()

        if not response_text:
            response_text = "I apologize, but I couldn't generate a response."

        # Strip any embedded JSON blocks from the saved plain text, collecting them
        embedded_json = []
        def _collect_json(m):
            try:
                data = parse_wrapped_json(m.group(1))
                embedded_json.append(data)
            except json.JSONDecodeError:
                embedded_json.append(m.group(1))
            return ''
        plain_text = re.sub(r'```json\s*(.*?)\s*```', _collect_json, response_text, flags=re.DOTALL).strip()

        # Save conversation turn
        if conversation_id is not None and db:
            self.save_turn(conversation_id, user_input, plain_text, self.voice, temperature, db=db)

        self.session_turns.append({"user_input": user_input, "response_text": plain_text})
        if len(self.session_turns) > 50:
            self.session_turns = self.session_turns[-50:]

        metadata_json = {
            "referenced_files": available_docs,
            "function_calls": function_calls_made,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "provider": "claude",
            "model": self.model_name,
        }
        for block in embedded_json:
            if isinstance(block, dict):
                metadata_json.update(block)

        return plain_text, json.dumps(metadata_json, indent=2)

