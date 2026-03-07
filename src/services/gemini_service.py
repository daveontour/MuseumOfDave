"""Gemini LLM service for conversation summarization."""

import os
import json
import re
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from io import BytesIO
import google.genai as genai
from google.genai import types

from ..database import Database
from ..database.models import ReferenceDocument, GeminiFile
from .base_chat_service import BaseChatService, parse_wrapped_json

try:
    from tavily import TavilyClient
except ImportError:
    print("[GeminiService] Warning: tavily-python not installed. Tavily search will be disabled.")
    TavilyClient = None


class GeminiService:
    """Service for interacting with Google Gemini LLM API."""
    
    def __init__(self):
        """Initialize Gemini service with API key and model name from environment."""
        print("[GeminiService.__init__] Starting initialization...")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[GeminiService.__init__] ERROR: GEMINI_API_KEY environment variable is not set")
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
        print(f"[GeminiService.__init__] Using model: {model_name}")
        print(f"[GeminiService.__init__] API key found: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

        # Initialize Tavily client
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.tavily_client = None
        if TavilyClient and tavily_api_key:
            try:
                self.tavily_client = TavilyClient(api_key=tavily_api_key)
                print("[GeminiService.__init__] Tavily client initialized")
            except Exception as e:
                print(f"[GeminiService.__init__] Warning: Could not initialize Tavily client: {str(e)}")
        else:
            if not TavilyClient:
                print("[GeminiService.__init__] Warning: Tavily library not available")
            elif not tavily_api_key:
                print("[GeminiService.__init__] Warning: TAVILY_API_KEY not set. Tavily search disabled.")

        print("[GeminiService.__init__] Initialization complete")

    def oneshot_llm_request(self, messages_data: Dict[str, Any], input_prompt: str) -> str:
        """Make a one-shot LLM request.
        Args:
            messages_data: Dictionary containing conversation data
            input_prompt: Prompt to use for the summary
        Returns:
            Response text string
        Raises:
            ValueError: If API key is missing or messages_data is invalid
            Exception: If API call fails
        """
        print("[GeminiService.oneshot_llm_request] Starting one-shot LLM request...")
        
        if not messages_data or "messages" not in messages_data:
            print("[GeminiService.oneshot_llm_request] ERROR: Invalid messages_data - missing 'messages' key")
            raise ValueError("Invalid messages_data: missing 'messages' key")
        
        messages = messages_data.get("messages", [])
               
        if not messages:
            print("[GeminiService.oneshot_llm_request] WARNING: No messages found in conversation")
            return "No messages found in this conversation."
        
        # Format conversation for prompt
        conversation_text = self._format_conversation_for_prompt(messages_data)
        print(f"[GeminiService.oneshot_llm_request] Formatted conversation length: {len(conversation_text)} characters")
        
        # Create prompt
        prompt = f"""{input_prompt}

                 Data to be processed:
                     {conversation_text}"""
        
        print(f"[GeminiService.oneshot_llm_request] Calling Gemini API with prompt length: {len(prompt)} characters")
        
        try:
            # Call Gemini API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            print("[GeminiService.oneshot_llm_request] Received response from Gemini API")
            
            if response and response.text:
                summary = response.text.strip()
                print(f"[GeminiService.oneshot_llm_request] Summary length: {len(summary)} characters")
                print(f"[GeminiService.oneshot_llm_request] Summary preview: {summary[:100]}...")
                return summary
            else:
                print("[GeminiService.oneshot_llm_request] ERROR: Empty response from Gemini API")
                raise Exception("Empty response from Gemini API")
        
        except ValueError as e:
            # Re-raise ValueError (e.g., missing API key) as-is
            print(f"[GeminiService.oneshot_llm_request] ValueError raised: {str(e)}")
            raise
        except Exception as e:
            error_msg = str(e)
            print(f"[GeminiService.oneshot_llm_request] Exception caught: {error_msg}")
            
            # Provide more user-friendly error messages
            if "API key" in error_msg.lower() or "authentication" in error_msg.lower():
                print("[GeminiService.oneshot_llm_request] Error type: Authentication/API key issue")
                raise ValueError("Invalid or missing Gemini API key. Please check your GEMINI_API_KEY environment variable.")
            elif "404" in error_msg.lower() or "not found" in error_msg.lower() or "not supported" in error_msg.lower():
                model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
                print(f"[GeminiService.oneshot_llm_request] Error type: Model not found - {model_name}")
                raise ValueError(f"Model '{model_name}' is not available. Please check your GEMINI_MODEL_NAME environment variable. Common models: gemini-1.5-flash, gemini-1.5-pro, gemini-pro")
            elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                print("[GeminiService.oneshot_llm_request] Error type: Quota/Rate limit exceeded")
                raise Exception("API quota exceeded. Please try again later.")
            elif "timeout" in error_msg.lower():
                print("[GeminiService.oneshot_llm_request] Error type: Timeout")
                raise Exception("Request timed out. Please try again.")
            else:
                print(f"[GeminiService.oneshot_llm_request] Error type: Unknown - {error_msg}")
                # Make error message more user-friendly
                if "Error calling Gemini API:" in error_msg:
                    # Already formatted, use as-is
                    raise Exception(error_msg)
                else:
                    raise Exception(f"Error calling Gemini API: {error_msg}")

    def summarize_conversation(self, messages_data: Dict[str, Any]) -> str:
        """Summarize a conversation using Gemini LLM.
        Args:
            messages_data: Dictionary containing conversation data
        Returns:
            Summary text string
        Raises:
            ValueError: If API key is missing or messages_data is invalid
            Exception: If API call fails
        """

        input_prompt = """
                     Please provide a concise summary of the following conversation. 
                     Focus on the main topics discussed, key decisions made,
                     and important information shared. Include a characterisation
                     of the participants relationships and dynamics.
                     Write in clear, structured markdown""" 
        try:
            return self.oneshot_llm_request(messages_data, input_prompt)
        except Exception as e:
            print(f"[GeminiService.summarize_conversation] Error: {str(e)}")
            raise ValueError(f"Error summarizing conversation: {str(e)}")

    def summarize_writing_style(self, messages_data: Dict[str, Any]) -> str:
        """Summarize a user's writing style using Gemini LLM.

        Reads an optional 'input_prompt' key from messages_data to override the
        default writing-style prompt, then delegates to summarize_conversation_general.
        """
        input_prompt = """
            Please provide a detailed analysis of the writing style of the following text.
            Write in clear, structured markdown suitable for use by an LLM to understand the writing style."""
        
        try:
            return self.oneshot_llm_request(messages_data, input_prompt)
        except Exception as e:
            print(f"[GeminiService.summarize_writing_style] Error: {str(e)}")
            raise

    def summarize_psychological_profile(self, messages_data: Dict[str, Any]) -> str:
        """Generate a psychological profile from message content using Gemini LLM.

        Reads an optional 'input_prompt' key from messages_data to override the
        default psychological-profile prompt, then delegates to summarize_conversation_general.
        """
        input_prompt = """
            Based on the following messages, provide a psychological profile of the person. 
            Consider personality traits, communication patterns, values, interests, emotional tendencies, 
            and any other psychological dimensions evident from the text. 
            Write in clear, structured markdown suitable for use by an LLM to understand the person's psychology.
        """
        try:
            return self.oneshot_llm_request(messages_data, input_prompt)
        except Exception as e:
            print(f"[GeminiService.summarize_psychological_profile] Error: {str(e)}")
            raise

    def summarize_relationships(self, messages_data: Dict[str, Any], contact_name: str) -> str:
        """Generate a psychological profile from message content using Gemini LLM.

        Reads an optional 'input_prompt' key from messages_data to override the
        default psychological-profile prompt, then delegates to summarize_conversation_general.
        """
        input_prompt = """
            Based on the following messages, provide a detailedsummary of the relationships between {contact_name} and other contacts.
            Include the nature of the relationship.
            Include the names of the contacts involved in the relationships.
            Include the dates of the relationships.
            Include the types of relationships.
            Include the descriptions of the relationships.
            Include the strengths of the relationships.
            Include the frequencies of communication.
            Include the dates of the relationships.
            Include the types of relationships.
            Include significant events or milestones in the relationships.
            Include any interesting anecdotes or stories about the relationships.
            Include any information on the person's personality and psychology.
            Include any information on the person's values and interests.
            Include any information on sexual activities and preferences and any romantic intent between the contacts.
            Include any other relevant information.
            Write in clear, structured markdown suitable for use by an LLM to understand the relationships.
        """
        try:
            return self.oneshot_llm_request(messages_data, input_prompt)
        except Exception as e:
            print(f"[GeminiService.summarize_psychological_profile] Error: {str(e)}")
            raise

    def summarize_relationships_multistep(self, messages_data: Dict[str, Any], interimSummary: str, idx: int, total: int) -> str:
        """Summarize relationships in multiple steps using Gemini LLM.
        Args:
            messages_data: Dictionary containing conversation data
            interimSummary: Interim summary of the relationships
            idx: Index of the current chunk
            total: Total number of chunks
        Returns:
            Summary text string
        """
        print (f"Summarizing relationships in multiple steps... {idx}/{total}")

        #create a dictionary with the messages data
        temp = {"messages": messages_data}

        prompt = f"""
            You are a helpful assistant that summarizes communication patterns, relationships and psychological profiles in multiple steps.
            You will be given a list of messages and an interim summary that has been generated so far.
            You will need to summarize communication patterns, relationships and psychological profiles on the messages based on the interim summary.
            You will need to return the next interim summary which will be used as context for the next chunk of messages.

            The goal is to build on the interim summary not to just replace it with the summary of the current chunk of messages.
            The interim summaries should be a cumulative summary of all the messages processed so far.

            There will be a total of {total} chunks of messages to process.
            This is the {idx} chunk of messages to process.


            The interim summary is: 
            {interimSummary}


            """
        try:
            return self.oneshot_llm_request(temp, prompt)
        except Exception as e:
            print(f"[GeminiService.summarize_relationships_multistep] Error: {str(e)}")
            raise
        return f"Error summarizing relationships in multiple steps: {str(e)} {idx}/{total}"

    def _format_conversation_for_prompt(self, messages_data: Dict[str, Any]) -> str:
        """Format conversation data into a readable text format for the prompt.
        
        Args:
            messages_data: Dictionary containing conversation data
        
        Returns:
            Formatted conversation text
        """
        print("[GeminiService._format_conversation_for_prompt] Starting conversation formatting...")
        messages = messages_data.get("messages", [])
        formatted_lines = []
        
        print(f"[GeminiService._format_conversation_for_prompt] Processing {len(messages)} messages")
        
        for idx, msg in enumerate(messages):
            sender = msg.get("sender_name", "Unknown")
            msg_type = msg.get("type", "")
            text = msg.get("text", "")
            date = msg.get("message_date", "")
            has_attachment = msg.get("has_attachment", False)
            
            # Format sender label
            if msg_type.lower() == "outgoing":
                sender_label = f"You ({sender})"
            else:
                sender_label = sender
            
            # Format date if available
            date_str = ""
            if date:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception as e:
                    print(f"[GeminiService._format_conversation_for_prompt] Warning: Could not parse date '{date}': {str(e)}")
                    date_str = date[:16] if len(date) > 16 else date
            
            # Build message line
            line = f"[{date_str}] {sender_label}: {text}"
            if has_attachment:
                line += " [Attachment]"
            
            formatted_lines.append(line)
            
            # Log every 10th message for debugging
            if (idx + 1) % 10 == 0:
                print(f"[GeminiService._format_conversation_for_prompt] Processed {idx + 1}/{len(messages)} messages...")
        
        result = "\n".join(formatted_lines)
        print(f"[GeminiService._format_conversation_for_prompt] Formatting complete. Result length: {len(result)} characters")
        return result

class ChatService(BaseChatService):
    """Service for interacting with Gemini LLM API for chat sessions."""

    def __init__(self, subject_config_service=None, config_service=None):
        print("[GeminiChatService.__init__] Starting initialization...")
        _get = config_service.get if config_service else os.getenv
        api_key = _get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        model_name = _get("GEMINI_MODEL_NAME", "gemini-2.5-flash") or "gemini-2.5-flash"
        print(f"[GeminiChatService.__init__] Using model: {model_name}")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        super().__init__(subject_config_service, config_service)
        print("[GeminiChatService.__init__] Initialization complete")

    def _upload_file_to_gemini(self, doc: ReferenceDocument, db: Optional[Database] = None) -> Optional[Any]:
        """Upload a reference document to Gemini File API and return the File object.
        
        Uses database-backed caching to avoid re-uploading files that are already available on Gemini.
        Checks database first, then verifies with Gemini API before uploading.
        
        Args:
            doc: ReferenceDocument instance
            db: Optional Database instance. If not provided, uses self.db.
            
        Returns:
            File object if successful, None otherwise
        """
        if db is None:
            db = self.db
        
        if not db:
            print("[ChatService._upload_file_to_gemini] ERROR: Database not available")
            return None
        
        try:
            session = db.get_session()
            try:
                # Check database for existing Gemini file mapping
                gemini_file_record = session.query(GeminiFile).filter(
                    GeminiFile.reference_document_id == doc.id
                ).first()
                
                if gemini_file_record:
                    # Found existing mapping, verify file is still ACTIVE with Gemini API
                    try:
                        file_info = self.client.files.get(name=gemini_file_record.gemini_file_name)
                        file_state = file_info.state.name if hasattr(file_info.state, 'name') else str(file_info.state)
                        
                        if file_state == "ACTIVE":
                            # File is still active, update verification timestamp and return File object
                            gemini_file_record.verified_at = datetime.now(timezone.utc)
                            gemini_file_record.state = "ACTIVE"
                            gemini_file_record.updated_at = datetime.now(timezone.utc)
                            # Update URI if available and different
                            if hasattr(file_info, 'uri') and file_info.uri:
                                gemini_file_record.gemini_file_uri = file_info.uri
                            session.commit()
                            
                            print(f"[ChatService._upload_file_to_gemini] Using existing Gemini file: {doc.filename} (verified)")
                            return file_info  # Return the File object from Gemini
                        else:
                            # File is not ACTIVE, mark as expired and upload new one
                            print(f"[ChatService._upload_file_to_gemini] Existing file {doc.filename} is not ACTIVE (state: {file_state}), uploading new file")
                            gemini_file_record.state = file_state
                            session.commit()
                            # Continue to upload new file below
                    except Exception as e:
                        # File doesn't exist anymore in Gemini, delete record and upload new one
                        print(f"[ChatService._upload_file_to_gemini] Existing file {doc.filename} no longer exists in Gemini: {str(e)}, uploading new file")
                        session.delete(gemini_file_record)
                        session.commit()
                        # Continue to upload new file below
                
                # Upload file to Gemini (either no existing record or existing file is invalid)
                print(f"[ChatService._upload_file_to_gemini] Uploading file: {doc.filename}")
                # If the content type is application/json, change it to text/plain
                # This is because Gemini does not support application/json files
                content_type = doc.content_type
                if content_type == "application/json" or "json" in content_type.lower():
                    content_type = "text/plain"
                
                # Save BytesIO to a temporary file for upload (new SDK requires file path)
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{doc.filename}") as tmp_file:
                    tmp_file.write(doc.data)
                    tmp_file_path = tmp_file.name
                
                try:
                    # Build config dict for file upload (new SDK uses config parameter)
                    upload_config = {}
                    if content_type:
                        upload_config['mime_type'] = content_type
                    if doc.title or doc.filename:
                        upload_config['display_name'] = doc.title or doc.filename
                    
                    # Only pass config if we have values
                    if upload_config:
                        uploaded_file = self.client.files.upload(
                            file=tmp_file_path,
                            config=upload_config
                        )
                    else:
                        uploaded_file = self.client.files.upload(file=tmp_file_path)
                finally:
                    # Clean up temporary file
                    if os.path.exists(tmp_file_path):
                        os.unlink(tmp_file_path)
                
                # Wait for file to be processed (some file types need processing)
                max_wait_time = 60  # seconds
                wait_interval = 2  # seconds
                elapsed = 0
                
                while uploaded_file.state.name != "ACTIVE" and elapsed < max_wait_time:
                    time.sleep(wait_interval)
                    elapsed += wait_interval
                    uploaded_file = self.client.files.get(name=uploaded_file.name)
                    print(f"[ChatService._upload_file_to_gemini] File state: {uploaded_file.state.name}, waiting...")
                
                if uploaded_file.state.name == "ACTIVE":
                    # Save or update database record
                    file_name = uploaded_file.name if hasattr(uploaded_file, 'name') else None
                    file_uri = uploaded_file.uri if hasattr(uploaded_file, 'uri') else None
                    
                    if gemini_file_record:
                        # Update existing record
                        gemini_file_record.gemini_file_name = file_name
                        gemini_file_record.gemini_file_uri = file_uri
                        gemini_file_record.state = "ACTIVE"
                        gemini_file_record.verified_at = datetime.now(timezone.utc)
                        gemini_file_record.updated_at = datetime.now(timezone.utc)
                    else:
                        # Create new record
                        gemini_file_record = GeminiFile(
                            reference_document_id=doc.id,
                            gemini_file_name=file_name,
                            gemini_file_uri=file_uri,
                            filename=doc.filename,
                            state="ACTIVE",
                            verified_at=datetime.now(timezone.utc)
                        )
                        session.add(gemini_file_record)
                    
                    session.commit()
                    print(f"[ChatService._upload_file_to_gemini] File uploaded successfully: {doc.filename}")
                    return uploaded_file
                else:
                    print(f"[ChatService._upload_file_to_gemini] File {doc.filename} did not become ACTIVE in time (state: {uploaded_file.state.name})")
                    return None
                    
            finally:
                session.close()
                
        except Exception as e:
            print(f"[ChatService._upload_file_to_gemini] Error uploading file {doc.filename}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    def _build_reference_manifest(self, db: Database):
        """Return (manifest_text, available_docs) for all available_for_task docs."""
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
            print(f"[ChatService] Warning: Could not retrieve reference documents: {e}")
        if not available_docs:
            return "", []
        lines = [
            "## Available Reference Documents",
            "Use the `get_reference_document` tool to retrieve one or more of these documents when relevant.\n",
        ]
        for doc in available_docs:
            lines.append(f"- **ID {doc['id']}** — {doc['title']}: {doc['description']}")
        return "\n".join(lines), available_docs

    def _fetch_reference_documents_for_gemini(self, document_ids: list, db: Database):
        """Upload requested docs to Gemini File API and return (files, metadata).

        Uses existing _upload_file_to_gemini caching — only uploads if not already ACTIVE.
        """
        uploaded_files = []
        metadata = []
        session = db.get_session()
        try:
            for doc_id in document_ids:
                doc = session.query(ReferenceDocument).filter(ReferenceDocument.id == doc_id).first()
                if doc is None:
                    print(f"[ChatService] Document ID {doc_id} not found")
                    continue
                uploaded_file = self._upload_file_to_gemini(doc, db=db)
                if uploaded_file:
                    uploaded_files.append(uploaded_file)
                    metadata.append({"id": doc.id, "filename": doc.filename, "title": doc.title})
                    print(f"[ChatService] Fetched reference doc via tool: {doc.filename}")
        finally:
            session.close()
        return uploaded_files, metadata

    def _get_tools_config(self) -> List[Any]:
        """Get the tools configuration for Gemini function calling.
        
        Returns:
            List of Tool objects with function declarations
        """
        get_current_time_declaration = types.FunctionDeclaration(
            name="get_current_time",
            description="Get the current date and time in ISO format. Useful when user asks about the current time or date.",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
        
        get_imessages_declaration = types.FunctionDeclaration(
            name="get_imessages_by_chat_session",
            description="Get all messages for WhatsApp, SMS, and iMessage and Facebook messages for a specific chat. Use this when the user asks about messages, conversations, or chats with a specific person or group.",
            parameters={
                "type": "object",
                "properties": {
                    "chat_session": {
                        "type": "string",
                        "description": "The chat session name (person or group name) to retrieve messages for"
                    }
                },
                "required": ["chat_session"]
            }
        )
        
        get_emails_declaration = types.FunctionDeclaration(
            name="get_emails_by_contact",
            description="Get plain text of emails where the sender or receiver matches the specified name or email address. Use this when the user asks about emails with a specific person or contact.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name or email address to search for in sender (from_address) or receiver (to_addresses) fields"
                    }
                },
                "required": ["name"]
            }
        )

        get_all_messages_by_contact_declaration = types.FunctionDeclaration(
            name="get_all_messages_by_contact",
            description="Get all messages for a specific contact. Use this when the user asks about messages with a specific person or contact or when background information is needed on that person for a discussion.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name or email address to search"
                    }
                },
                "required": ["name"]
            }
        )

        get_subject_writing_examples_declaration = types.FunctionDeclaration(
            name="get_subject_writing_examples",
            description="Get the subject writing examples. Use this when the user asks about subject writing examples.",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            }
        )

        search_tavily_declaration = types.FunctionDeclaration(
            name="search_tavily",
            description="Perform a web search for real-time information and current events using Tavily. Use this when the user asks about current events, news, or information not available in the internal database.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }
        )

        search_facebook_albums_declaration = types.FunctionDeclaration(
            name="search_facebook_albums",
            description="Search Facebook photo albums by a partial keyword match against album name or description. Use this when the user asks about Facebook albums, photo collections, or wants to find albums related to a topic or event or when background information is needed on that person for a discussion.",
            parameters={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Partial keyword to search for in album names and descriptions fields"
                    }
                },
                "required": ["keyword"]
            }
        )

        get_unique_tags_count_declaration = types.FunctionDeclaration(
            name="get_unique_tags_count",
            description="Get the unique tags used in the media items (photos/videos) library and the artefacts collection, along with counts. Use this when the user asks what tags exist, how many tags there are, or wants a summary of tagging across the museum collections.",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            }
        )

        get_reference_document_declaration = types.FunctionDeclaration(
            name="get_reference_document",
            description="Retrieve the full content of one or more reference documents by their IDs. Call this when the user's question is best answered using a specific reference document listed in the system prompt.",
            parameters={
                "type": "object",
                "properties": {
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of reference document IDs to retrieve.",
                    }
                },
                "required": ["document_ids"]
            }
        )

        return [types.Tool(
            function_declarations=[
                get_current_time_declaration,
                get_imessages_declaration,
                get_emails_declaration,
                get_subject_writing_examples_declaration,
                search_tavily_declaration,
                get_all_messages_by_contact_declaration,
                get_unique_tags_count_declaration,
                search_facebook_albums_declaration,
                get_reference_document_declaration,
            ],
            google_search=types.GoogleSearch()
        )]

    def generate_response(self, user_input: str, temperature: float = 0.0, voice: str = "expert", mood: str = "neutral", psychological_profile: str = None, writing_style: str = None, conversation_id: Optional[int] = None, db: Optional[Database] = None, companionMode: Optional[bool] = False) -> str:
        """Generates a response to the prompt using the Gemini LLM API.
        
        Args:
            user_input: The user's input message
            temperature: Temperature for generation (default 0.0)
            conversation_id: Optional conversation ID. If provided, loads conversation context and saves turn.
            db: Optional Database instance. If not provided, uses self.db.
            
        Returns:
            Response text from Gemini
        """
        # Use provided db or self.db
        if db is None:
            db = self.db

        #set the voice and voice instructions
        self.voice = voice
        if not self.voice_instructions_list:
            # Reload voice instructions if not loaded yet
            self.voice_instructions_list = self._load_voice_instructions()
        try:
            self.voice_instructions = self.voice_instructions_list[voice]
        except KeyError:
            print(f"[GeminiChatService.set_voice] Voice '{voice}' not found. Using default voice 'expert'.")
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
                    print(f"[generate_chat_response] Warning: Could not set voice 'owner': {str(e)}")
                    self.mood = "neutral"
                    self.psychological_profile = None
                    self.writing_style = None

        subject_name = self._subject_config_service.get_subject_name()
        subject_gender = self._subject_config_service.get_gender()


        # Build the system prompt
        system_instructions = self._subject_config_service.get_system_instructions()
        system_instructions = system_instructions.replace('{SUBJECT_NAME}', subject_name)
        if subject_gender == "Male":
            system_instructions = system_instructions.replace('{he}', "he")
            system_instructions = system_instructions.replace('{him}', "him")
            system_instructions = system_instructions.replace('{his}', "his")
        elif subject_gender == "Female":
            system_instructions = system_instructions.replace('{he}', "she")
            system_instructions = system_instructions.replace('{him}', "her")
            system_instructions = system_instructions.replace('{his}', "her")

        core_instructions = self._subject_config_service.get_core_system_instructions()
        core_instructions = core_instructions.replace('{SUBJECT_NAME}', subject_name)
        if subject_gender == "Male":
            core_instructions = core_instructions.replace('{he}', "he")
            core_instructions = core_instructions.replace('{him}', "him")
            core_instructions = core_instructions.replace('{his}', "his")
        elif subject_gender == "Female":
            core_instructions = core_instructions.replace('{he}', "she")
            core_instructions = core_instructions.replace('{him}', "her")
            core_instructions = core_instructions.replace('{his}', "her")

        voice_instructions = self.voice_instructions["instructions"]
        voice_instructions = voice_instructions.replace('{SUBJECT_NAME}', subject_name)
        if subject_gender == "Male":
            voice_instructions = voice_instructions.replace('{he}', "he")
            voice_instructions = voice_instructions.replace('{him}', "him")
            voice_instructions = voice_instructions.replace('{his}', "his")
        elif subject_gender == "Female":
            voice_instructions = voice_instructions.replace('{he}', "she")
            voice_instructions = voice_instructions.replace('{him}', "her")
            voice_instructions = voice_instructions.replace('{his}', "her")

        system_prompt = core_instructions + "\n\n **Your Personae:**\n" + voice_instructions + "\n\n **Additional Information:**\n" + system_instructions

        manifest_text, available_docs = self._build_reference_manifest(db) if db else ("", [])
        if manifest_text:
            system_prompt = system_prompt + "\n\n" + manifest_text

        print(f"<====System Prompt===============>")
        print(f"\n{system_prompt}\n")
        print(f"=================================>")

        # Load conversation context if conversation_id is provided and different from current
        if conversation_id is not None and conversation_id != self.current_conversation_id:
            if db:
                self.load_conversation_turns(conversation_id, limit=30, db=db)
            else:
                print("[ChatService.generate_response] Warning: conversation_id provided but database not available")

        # Update current conversation ID
        if conversation_id is not None:
            self.current_conversation_id = conversation_id

        # Track files referenced and function calls for metadata
        referenced_files = []  # Populated when get_reference_document tool is called
        function_calls_made = []  # List of function calls with parameters

        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        
        # Build text prompt with voice instructions, conversation history, and user input
        prompt_parts = []

        #should be in the configuration now
        #prompt_parts.append(self.system_prompt)
        
        # Add voice instructions
        #prompt_parts.append(self.voice_instructions["instructions"])

        if self.voice == "owner":
            prompt_parts.append(f"IMPORTANT:Respond in the first person voice. Speak as if you are the owner of the subject's life and you are talking to the user who is asking you about the subject's life.")
            prompt_parts.append(f"IMPORTANT:Your current mood is {self.mood}")
            prompt_parts.append(f"IMPORTANT:Respond consistent with your prescribed psychological profile: <psychologicalprofile>{self.psychological_profile}</psychologicalprofile>")
            prompt_parts.append(f"IMPORTANT:Respond consistent with your prescribed writing style: <writingstyle>{self.writing_style}</writingstyle>")
        
        if companionMode:
                prompt_parts.append(f"""IMPORTANT:You are in companion mode. You are talking to a user who is your friend and companion. 
                You are not talking to a customer or a user who is asking you for help. You are talking to a friend who is asking you about your life and your thoughts and feelings. 
                Respond conversationally, as if you are talking to a friend. Ask questions, make comments as well as answering questions. Do not automatically validate the user's input. Just respond to the user's input as if you are talking to a friend.
                Present opposing views if necessary. Set a snarky tone if necessary. Use humor if appropriate. Use sarcasm if appropriate. 
                Use irony if appropriate. Use word play if appropriate. Use puns if appropriate. Use play on words if appropriate. 
                Use word games if appropriate. Use word puzzles if appropriate.""")
        
        # Include conversation history (last 20 turns)
        if self.session_turns:
            prompt_parts.append("\n\n=== Conversation History ===")
            # Get last 20 turns
            recent_turns = self.session_turns[-20:]
            for turn in recent_turns:
                prompt_parts.append(f"User: {turn.get('user_input', '')}")
                prompt_parts.append(f"Assistant: {turn.get('response_text', '')}")
        
        # Add current user input
        prompt_parts.append(f"\nUser input:\n{user_input}")
        prompt_text = "\n".join(prompt_parts)

        
        # Build contents list: text prompt only (files delivered on-demand via get_reference_document tool)
        contents = [prompt_text]

        try:
            # Get tools configuration
            tools = self._get_tools_config()
            
            # Generate content with file references, text, and tools
            # Tools are passed via config in the new SDK

            print(f"System Prompt:\n {system_prompt}")
            print(f"Contents:\n {contents}")
            print(f"Temperature:\n {temperature}")

            config = types.GenerateContentConfig(
                tools=tools, 
                system_instruction=system_prompt,
                temperature=temperature)
                
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )
            
            # Handle function calling loop
            max_iterations = 5  # Prevent infinite loops
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # Check if response contains function calls
                function_calls = []
                if response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    # Only add function calls with valid names
                                    if hasattr(part.function_call, 'name') and part.function_call.name:
                                        function_calls.append(part.function_call)
                                    else:
                                        print(f"[ChatService.generate_response] Skipping function call with empty name: {part.function_call}")
                
                # If no function calls, we're done
                if not function_calls:
                    break
                
                print(f"[ChatService.generate_response] Found {len(function_calls)} function call(s)")
                
                # Execute function calls and build responses
                function_responses = []
                # Extra parts to add alongside function responses (e.g. file_data for get_reference_document)
                extra_parts = []
                for func_call in function_calls:
                    # Extract function name and validate
                    func_name = func_call.name if hasattr(func_call, 'name') else ""
                    if not func_name or not func_name.strip():
                        print(f"[ChatService.generate_response] Skipping function call with empty or invalid name: {func_call}")
                        continue

                    func_args = dict(func_call.args) if hasattr(func_call, 'args') and func_call.args else {}
                    print(f"[ChatService.generate_response] Processing function call: {func_name} with args: {func_args}")

                    # Track this function call
                    function_calls_made.append({
                        "name": func_name,
                        "arguments": func_args,
                        "iteration": iteration
                    })

                    try:
                        if func_name == "get_reference_document" and db:
                            # Upload requested docs via File API (cached) and attach as file_data parts
                            doc_ids = func_args.get("document_ids", [])
                            uploaded_files, file_metadata = self._fetch_reference_documents_for_gemini(doc_ids, db)
                            referenced_files.extend(file_metadata)
                            function_responses.append(
                                types.FunctionResponse(
                                    name=func_name,
                                    response={
                                        "status": "success",
                                        "note": "The requested document(s) have been provided as file attachments in this message.",
                                        "documents": file_metadata,
                                    }
                                )
                            )
                            # Attach the actual Gemini File objects as file_data parts
                            for uf in uploaded_files:
                                mime = uf.mime_type if hasattr(uf, 'mime_type') else "application/octet-stream"
                                extra_parts.append(
                                    types.Part(file_data=types.FileData(file_uri=uf.uri, mime_type=mime))
                                )
                        else:
                            # Execute the function normally
                            result = self._execute_function_call(func_name, func_args)
                            function_responses.append(
                                types.FunctionResponse(
                                    name=func_name,
                                    response=result  # result is already a dict
                                )
                            )
                    except ValueError as e:
                        # Unknown function - skip it, don't create error response
                        print(f"[ChatService.generate_response] Unknown function {func_name}, skipping: {str(e)}")
                        continue
                    except Exception as e:
                        print(f"[ChatService.generate_response] Error executing function {func_name}: {str(e)}")
                        # Create error response only if we have a valid function name
                        function_responses.append(
                            types.FunctionResponse(
                                name=func_name,
                                response={"error": str(e)}
                            )
                        )

                # If we have function responses, make a follow-up call
                if function_responses:
                    # Build follow-up contents: original contents + function responses + any extra parts (e.g. files)
                    follow_up_contents = contents.copy()
                    for func_response in function_responses:
                        follow_up_contents.append(types.Part(function_response=func_response))
                    for part in extra_parts:
                        follow_up_contents.append(part)
                    
                    print(f"[ChatService.generate_response] Making follow-up call with {len(function_responses)} function response(s)")
                    config = types.GenerateContentConfig(
                        tools=tools,
                        system_instruction=system_prompt,
                        temperature=temperature,
                    )
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=follow_up_contents,
                        config=config
                    )
            
            # Extract final text response
            input_tokens = response.usage_metadata.prompt_token_count
            output_tokens = response.usage_metadata.candidates_token_count
            total_tokens = response.usage_metadata.total_token_count

            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts'):
                        text_parts = []
                        for part in candidate.content.parts:
                            if hasattr(part, 'text'):
                                text_parts.append(part.text)
                        if text_parts:
                            response_text = " ".join(text_parts).strip()
                        else:
                            response_text = response.text.strip() if hasattr(response, 'text') else ""
                    else:
                        response_text = response.text.strip() if hasattr(response, 'text') else ""
                else:
                    response_text = response.text.strip() if hasattr(response, 'text') else ""
            else:
                response_text = response.text.strip() if hasattr(response, 'text') else ""
            
            if not response_text:
                response_text = "I apologize, but I couldn't generate a response."
            
            # Append metadata about files and function calls as JSON
            # This will be parsed by the API endpoint and included in embedded_json
            metadata_json = {
                "referenced_files": referenced_files,
                "function_calls": function_calls_made,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens
            }
            


            # Strip embedded JSON blocks, collecting them into metadata
            embedded_json = []
            def _collect_json(m):
                try:
                    data = parse_wrapped_json(m.group(1))
                    embedded_json.append(data)
                except json.JSONDecodeError:
                    embedded_json.append(m.group(1))
                return ''
            plain_text = re.sub(r'```json\s*(.*?)\s*```', _collect_json, response_text, flags=re.DOTALL).strip()

            # Merge any embedded JSON blocks into metadata
            for block in embedded_json:
                if isinstance(block, dict):
                    metadata_json.update(block)

            # Save turn to database if conversation_id is provided
            if conversation_id is not None and db:
                self.save_turn(conversation_id, user_input, plain_text, self.voice, temperature, db=db)
            # Track this turn in conversation history (in-memory)
            self.session_turns.append({
                "user_input": user_input,
                "response_text": plain_text
            })

            # Keep only last 50 turns in memory (for context)
            if len(self.session_turns) > 50:
                self.session_turns = self.session_turns[-50:]

            metadata_json_str = json.dumps(metadata_json, indent=2)

            return plain_text, metadata_json_str
        except Exception as e:
            error_msg = str(e)
            print(f"[ChatService.generate_response] Error: {error_msg}")
            
            # If error is related to files (500 error), try fallback without files
            if "500" in error_msg or "internal error" in error_msg.lower():
                print("[ChatService.generate_response] Attempting fallback: generating response without file references")
                try:
                    # Fallback: use text-only prompt (files may not be supported by this model/API version)
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt_text
                    )
                    response_text = response.text.strip()

                    # Strip embedded JSON blocks, collecting them into metadata
                    embedded_json = []
                    def _collect_json_fb(m):
                        try:
                            data = json.loads(m.group(1).strip())
                            embedded_json.append(data)
                        except json.JSONDecodeError:
                            embedded_json.append(m.group(1))
                        return ''
                    plain_text = re.sub(r'```json\s*(.*?)\s*```', _collect_json_fb, response_text, flags=re.DOTALL).strip()

                    # Append metadata (files were attempted but failed, no function calls in fallback)
                    metadata_json = {
                        "referenced_files": referenced_files,
                        "function_calls": function_calls_made,
                        "fallback_used": True,
                    }
                    for block in embedded_json:
                        if isinstance(block, dict):
                            metadata_json.update(block)
                    metadata_json_str = json.dumps(metadata_json, indent=2)

                    # Track this turn in conversation history
                    self.session_turns.append({
                        "user_input": user_input,
                        "response_text": plain_text
                    })

                    # Keep only last 20 turns
                    if len(self.session_turns) > 20:
                        self.session_turns = self.session_turns[-20:]

                    # Save turn to database if conversation_id is provided
                    if conversation_id is not None and db:
                        self.save_turn(conversation_id, user_input, plain_text, self.voice, temperature, db=db)

                    print("[ChatService.generate_response] Fallback successful - response generated without files")
                    return plain_text, metadata_json_str
                except Exception as fallback_error:
                    print(f"[ChatService.generate_response] Fallback also failed: {str(fallback_error)}")
                    import traceback
                    traceback.print_exc()
                    raise ValueError(f"Error generating response: {error_msg}")
            else:
                import traceback
                traceback.print_exc()
                raise ValueError(f"Error generating response: {error_msg}")


                # INSERT_YOUR_CODE
