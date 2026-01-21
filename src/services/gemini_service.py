"""Gemini LLM service for conversation summarization."""

import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from io import BytesIO
import google.genai as genai
from google.genai import types
from ..database import Database
from ..database.models import ReferenceDocument, IMessage, Email, GeminiFile
from sqlalchemy import or_


class GeminiService:
    """Service for interacting with Google Gemini LLM API."""
    
    def __init__(self):
        """Initialize Gemini service with API key and model name from environment."""
        print("[GeminiService.__init__] Starting initialization...")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[GeminiService.__init__] ERROR: GEMINI_API_KEY environment variable is not set")
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        # Get model name from environment, default to gemini-1.5-flash
        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
        print(f"[GeminiService.__init__] Using model: {model_name}")
        print(f"[GeminiService.__init__] API key found: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        print("[GeminiService.__init__] Initialization complete")

    def summarize_conversation(self, messages_data: Dict[str, Any]) -> str:
        """Summarize a conversation using Gemini LLM.
        
        Args:
            messages_data: Dictionary containing conversation data with structure:
                {
                    "chat_session": str,
                    "message_count": int,
                    "messages": [
                        {
                            "message_date": str,
                            "sender_name": str,
                            "type": str,
                            "text": str,
                            "has_attachment": bool
                        }
                    ]
                }
        
        Returns:
            Summary text string
        
        Raises:
            ValueError: If API key is missing or messages_data is invalid
            Exception: If API call fails
        """

        prompt = """Please provide a concise summary of the following conversation. 
Focus on the main topics discussed, key decisions made, and important information shared. Include a characterisation of the participants relationships and dynamics.""" 
        try:
            return self.summarize_conversation_general(messages_data, prompt)
        except Exception as e:
            print(f"[GeminiService.summarize_conversation] Error: {str(e)}")
            raise ValueError(f"Error summarizing conversation: {str(e)}")
    
    def summarize_conversation_general(self, messages_data: Dict[str, Any], input_prompt: str) -> str:
        """Summarize a conversation using Gemini LLM.
        
        Args:
            messages_data: Dictionary containing conversation data with structure:
                {
                    "chat_session": str,
                    "message_count": int,
                    "messages": [
                        {
                            "message_date": str,
                            "sender_name": str,
                            "type": str,
                            "text": str,
                            "has_attachment": bool
                        }
                    ]
                }
        
        Returns:
            Summary text string
        
        Raises:
            ValueError: If API key is missing or messages_data is invalid
            Exception: If API call fails
        """
        print("[GeminiService.summarize_conversation] Starting conversation summarization...")
        
        if not messages_data or "messages" not in messages_data:
            print("[GeminiService.summarize_conversation] ERROR: Invalid messages_data - missing 'messages' key")
            raise ValueError("Invalid messages_data: missing 'messages' key")
        
        messages = messages_data.get("messages", [])
        message_count = messages_data.get("message_count", len(messages))
        chat_session = messages_data.get("chat_session", "Unknown")
        
        print(f"[GeminiService.summarize_conversation] Chat session: {chat_session}")
        print(f"[GeminiService.summarize_conversation] Message count: {message_count}")
        
        if not messages:
            print("[GeminiService.summarize_conversation] WARNING: No messages found in conversation")
            return "No messages found in this conversation."
        
        # Format conversation for prompt
        print("[GeminiService.summarize_conversation] Formatting conversation for prompt...")
        conversation_text = self._format_conversation_for_prompt(messages_data)
        print(f"[GeminiService.summarize_conversation] Formatted conversation length: {len(conversation_text)} characters")
        
        # Create prompt
        prompt = f"""{input_prompt}

Conversation:
{conversation_text}

Summary:"""
        
        print(f"[GeminiService.summarize_conversation] Prompt length: {len(prompt)} characters")
        print("[GeminiService.summarize_conversation] Calling Gemini API...")
        
        try:
            # Call Gemini API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            print("[GeminiService.summarize_conversation] Received response from Gemini API")
            
            if response and response.text:
                summary = response.text.strip()
                print(f"[GeminiService.summarize_conversation] Summary length: {len(summary)} characters")
                print(f"[GeminiService.summarize_conversation] Summary preview: {summary[:100]}...")
                return summary
            else:
                print("[GeminiService.summarize_conversation] ERROR: Empty response from Gemini API")
                raise Exception("Empty response from Gemini API")
        
        except ValueError as e:
            # Re-raise ValueError (e.g., missing API key) as-is
            print(f"[GeminiService.summarize_conversation] ValueError raised: {str(e)}")
            raise
        except Exception as e:
            error_msg = str(e)
            print(f"[GeminiService.summarize_conversation] Exception caught: {error_msg}")
            
            # Provide more user-friendly error messages
            if "API key" in error_msg.lower() or "authentication" in error_msg.lower():
                print("[GeminiService.summarize_conversation] Error type: Authentication/API key issue")
                raise ValueError("Invalid or missing Gemini API key. Please check your GEMINI_API_KEY environment variable.")
            elif "404" in error_msg.lower() or "not found" in error_msg.lower() or "not supported" in error_msg.lower():
                model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
                print(f"[GeminiService.summarize_conversation] Error type: Model not found - {model_name}")
                raise ValueError(f"Model '{model_name}' is not available. Please check your GEMINI_MODEL_NAME environment variable. Common models: gemini-1.5-flash, gemini-1.5-pro, gemini-pro")
            elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                print("[GeminiService.summarize_conversation] Error type: Quota/Rate limit exceeded")
                raise Exception("API quota exceeded. Please try again later.")
            elif "timeout" in error_msg.lower():
                print("[GeminiService.summarize_conversation] Error type: Timeout")
                raise Exception("Request timed out. Please try again.")
            else:
                print(f"[GeminiService.summarize_conversation] Error type: Unknown - {error_msg}")
                # Make error message more user-friendly
                if "Error calling Gemini API:" in error_msg:
                    # Already formatted, use as-is
                    raise Exception(error_msg)
                else:
                    raise Exception(f"Error calling Gemini API: {error_msg}")
    
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

class ChatService:
    """Service for interacting with Gemini LLM API for chat sessions."""

    def __init__(self):
        """Initialize Chat service with Gemini LLM API."""
        print("[GeminiChatService.__init__] Starting initialization...")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[GeminiService.__init__] ERROR: GEMINI_API_KEY environment variable is not set")
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        # Get model name from environment, default to gemini-1.5-flash
        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
        print(f"[GeminiChatService.__init__] Using model: {model_name}")
        print(f"[GeminiChatService.__init__] API key found: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

        self.voice_instructions_list = self._load_voice_instructions()
        self.voice = "expert"
        self.voice_instructions = self.voice_instructions_list[self.voice]
        self.system_prompt = self._load_system_prompt()
        self.session_turns = []  # List of {"user_input": str, "response_text": str}
        self.db = None  # Will be set when needed

        print("[GeminiChatService.__init__] Initialization complete")

    def set_voice(self, voice: str):
        """Sets the voice for the session."""
        self.voice = voice
        try:
            self.voice_instructions = self.voice_instructions_list[voice]
        except KeyError:
            print(f"[GeminiChatService.set_voice] Voice '{voice}' not found. Using default voice 'expert'.")
            self.voice = "expert"
            self.voice_instructions = self.voice_instructions_list[self.voice]

    def set_database(self, db: Database):
        """Set the database instance for retrieving reference documents."""
        self.db = db

    def clear_session(self):
        """Clears the session turns list."""
        self.session_turns = []

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
        

    def _load_voice_instructions(self):
        """Loads voice instructions from the JSON file."""
        try:
            # Print the full path of the current directory
            print(f"[ChatService._load_voice_instructions] Current directory: {os.getcwd()}")
            with open('src/api/static/data/voice_instructions.json', 'r') as file:
                voice_data = json.load(file)
                print(f"ChatService._load_voice_instructions] Loaded {len(voice_data)} voice instructions")
                return voice_data
        except FileNotFoundError:
            print("[ChatService._load_voice_instructions] voice_instructions.json not found. Using default voice instructions.")
            return {
                "expert": {
                    "name": "Expert",
                    "description": "Professional Expert", 
                    "instructions": "You are a professional expert in your field. You provide clear, accurate, and helpful information."
                }
            }

    def _load_system_prompt(self):
        """Loads system prompt from a text file."""
        try:
            # Print the full path of the current directory
            print(f"[ChatService._load_voice_instructions] Current directory: {os.getcwd()}")
            with open('src/api/static/data/system_instructions_chat.txt', 'r') as file:
                instructions = file.read()
                print(f"[ChatService._load_voice_instructions] Loaded {len(instructions)} system instructions")
                return instructions
        except FileNotFoundError:
            print("[ChatService._load_voice_instructions] system_instructions_chat.txt not found. Using default instructions.")
            return """You are an expert on life in general
                Always answer confidently, don't be afraid to say you don't know and that you might have to do deeper research. 
                If not much information is available, prompt the user to ask for more information. 

                Do not refer to yourself as a large language model.
                Do not be overtly positive, express sympathy and empathy when appropriate but also remain realistic.
                When responding, do not mention the source of the data.
                
                Always include a json structure at the end of your response. 
                In the json structure, include the name of the person you are responding as.
                In the json structure, include the the full pathname or URI of any attachments of any images in the attachments of any email or data file that you use in your response.
                
                For testing purposes, if the prompt includes "test cse" then send a browser_action with the function name showContactEmailGallery and the args 'Anne Leitch'

                For testing purposes, if the prompt includes "test file upload" then call the get_fionna_sms() tool to get Fionna's SMS messages from Dave. Make the call even if the file has already been uploaded. I need to be able to test my code.

                If asked about locations where Dave has been, include the browser_action to show the location info modal.
                For example:
                "browser_action": {
                "text_response": "Let me show you",
                "browser_action": {
                    "functionName": "showLocationInfo",
                    "args": []
                }
                }

                If asked about Facebook Albums, include the browser_action to show the Facebook Albums modal.
                For example:
                "browser_action": {
                "text_response": "Let me show you",
                "browser_action": {
                    "functionName": "showFacebookAlbums",
                    "args": []
                }
                }

                To display the Image Gallery to browse all of Dave's images, include the browser_action to show the Image Gallery modal.
                For example:
                "browser_action": {
                "text_response": "Let me show you",
                "browser_action": {
                    "functionName": "showImageGallery",
                    "args": []
                }
                }

                To display a specific Facebook Album, include the browser_action to show the Facebook Album modal.
                For example:
                "browser_action": {
                "text_response": "Let me show you",
                "browser_action": {
                    "functionName": "showFacebookAlbum",
                    "args": ["title of the album"]
                    }
                }

                To display emails with a particular contact, include the browser_action to show the Email Gallery modal.
                For example:
                "browser_action": {
                "text_response": "Let me show you",
                "browser_action": {
                    "functionName": "showContactEmailGallery",
                    "args": ["contact name"]
                    }
                }

                IMPORTANT GUIDELINES:
                - Always consider the user's profile when responding
                - Adapt your communication style to match the user's preferences
                - Use appropriate technical depth based on the user's expertise level
                - Reference relevant previous conversations when helpful
                - Be concise, friendly, and never surly
                - Use available tools when needed to provide better assistance


                """

    def _get_current_time(self) -> Dict[str, Any]:
        """Get the current date and time.
        
        Returns:
            Dictionary with current_time in ISO format
        """
        from datetime import datetime
        return {
            "current_time": datetime.now().isoformat(),
            "timezone": "UTC"
        }

    def _get_imessages_by_chat_session(self, chat_session: str) -> Dict[str, Any]:
        """Get all iMessage entries for a specific chat session.
        
        Args:
            chat_session: The chat session name to search for
            
        Returns:
            Dictionary with chat_session, message_count, and messages list
        """
        if not self.db:
            return {
                "error": "Database not configured",
                "chat_session": chat_session,
                "message_count": 0,
                "messages": []
            }
        
        session = self.db.get_session()
        try:
            messages = session.query(IMessage).filter(
                IMessage.chat_session.like(f"%{chat_session}%")
            ).order_by(
                IMessage.message_date.asc()
            ).all()

            
            # Format messages into structured format
            messages_list = []
            for msg in messages:
                messages_list.append({
                    "id": msg.id,
                    "message_date": msg.message_date.isoformat() if msg.message_date else None,
                    "sender_name": msg.sender_name or "Unknown",
                    "sender_id": msg.sender_id or "",
                    "type": msg.type or "",
                    "text": msg.text or "",
                    "service": msg.service or "",
                    "subject": msg.subject or None
                })
            
            return {
                "chat_session": chat_session,
                "message_count": len(messages),
                "messages": messages_list
            }
        except Exception as e:
            print(f"[ChatService._get_imessages_by_chat_session] Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "error": str(e),
                "chat_session": chat_session,
                "message_count": 0,
                "messages": []
            }
        finally:
            session.close()

    def _get_emails_by_contact(self, name: str) -> Dict[str, Any]:
        """Get plain text of emails where sender or receiver matches the specified name.
        
        Args:
            name: The name or email address to search for in sender or receiver fields
            
        Returns:
            Dictionary with contact_name, email_count, and emails list with plain_text
        """
        if not self.db:
            return {
                "error": "Database not configured",
                "contact_name": name,
                "email_count": 0,
                "emails": []
            }
        
        session = self.db.get_session()
        try:
            emails = session.query(Email).filter(
                or_(
                    Email.from_address.like(f"%{name}%"),
                    Email.to_addresses.like(f"%{name}%")
                )
            ).order_by(
                Email.date.asc()
            ).all()
            
            # Format emails into structured format with plain text
            emails_list = []
            for email in emails:
                emails_list.append({
                    "id": email.id,
                    "date": email.date.isoformat() if email.date else None,
                    "from_address": email.from_address or "",
                    "to_addresses": email.to_addresses or "",
                    "subject": email.subject or "",
                    "plain_text": email.plain_text or email.snippet or "",
                    "has_attachments": email.has_attachments or False
                })
            
            return {
                "contact_name": name,
                "email_count": len(emails),
                "emails": emails_list
            }
        except Exception as e:
            print(f"[ChatService._get_emails_by_contact] Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "error": str(e),
                "contact_name": name,
                "email_count": 0,
                "emails": []
            }
        finally:
            session.close()

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
        
        return [types.Tool(function_declarations=[get_current_time_declaration, get_imessages_declaration, get_emails_declaration])]

    def _execute_function_call(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a function call by routing to the appropriate handler method.
        
        Args:
            function_name: Name of the function to execute
            args: Dictionary of arguments for the function
            
        Returns:
            Dictionary with function result
            
        Raises:
            ValueError: If function name is not recognized
        """
        # Map function names to handler methods
        function_handlers = {
            "get_current_time": self._get_current_time,
            "get_imessages_by_chat_session": self._get_imessages_by_chat_session,
            "get_emails_by_contact": self._get_emails_by_contact,
        }
        
        if function_name not in function_handlers:
            raise ValueError(f"Unknown function: {function_name}")
        
        handler = function_handlers[function_name]
        print(f"[ChatService._execute_function_call] Executing function: {function_name} with args: {args}")
        
        try:
            # Execute the handler function
            result = handler(**args) if args else handler()
            print(f"[ChatService._execute_function_call] Function {function_name} returned: {result}")
            return result
        except Exception as e:
            print(f"[ChatService._execute_function_call] Error executing {function_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def generate_response(self, user_input: str, temperature: float = 0.0, db: Optional[Database] = None) -> str:
        """Generates a response to the prompt using the Gemini LLM API.
        
        Args:
            user_input: The user's input message
            db: Optional Database instance. If not provided, uses self.db.
            
        Returns:
            Response text from Gemini
        """
        # Use provided db or self.db
        if db is None:
            db = self.db
        
        # Build content parts for Gemini (can include files and text)
        content_parts = []
        
        # Track files referenced and function calls for metadata
        referenced_files = []  # List of file metadata
        function_calls_made = []  # List of function calls with parameters
        
        # Upload and include reference documents as files
        uploaded_files = []
        if db:
            try:
                session = db.get_session()
                try:
                    documents = session.query(ReferenceDocument).filter(
                        ReferenceDocument.available_for_task == True
                    ).all()
                    
                    # Process each document - _upload_file_to_gemini handles database checking and verification
                    for doc in documents:
                        uploaded_file = self._upload_file_to_gemini(doc, db=db)
                        if uploaded_file:
                            uploaded_files.append(uploaded_file)
                            
                            # Get Gemini file info from database for metadata
                            gemini_file_record = session.query(GeminiFile).filter(
                                GeminiFile.reference_document_id == doc.id
                            ).first()
                            
                            file_metadata = {
                                "id": doc.id,
                                "filename": doc.filename,
                                "title": doc.title,
                                "source": "database" if gemini_file_record else "uploaded"
                            }
                            
                            if gemini_file_record:
                                file_metadata["gemini_file_name"] = gemini_file_record.gemini_file_name
                                file_metadata["gemini_file_uri"] = gemini_file_record.gemini_file_uri
                                file_metadata["state"] = gemini_file_record.state
                            elif hasattr(uploaded_file, 'name'):
                                file_metadata["gemini_file_name"] = uploaded_file.name
                                file_metadata["gemini_file_uri"] = uploaded_file.uri if hasattr(uploaded_file, 'uri') else None
                            
                            referenced_files.append(file_metadata)
                            print(f"[ChatService.generate_response] Added file reference: {doc.filename}")
                finally:
                    session.close()
            except Exception as e:
                print(f"[ChatService.generate_response] Warning: Could not retrieve reference documents: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Build text prompt with voice instructions, conversation history, and user input
        prompt_parts = []

        #should be in the configuration now
        #prompt_parts.append(self.system_prompt)
        
        # Add voice instructions
        prompt_parts.append(self.voice_instructions["instructions"])
        
        # Include conversation history (last 20 turns)
        if self.session_turns:
            prompt_parts.append("\n\n=== Conversation History ===")
            # Get last 20 turns
            recent_turns = self.session_turns[-20:]
            for turn in recent_turns:
                prompt_parts.append(f"User: {turn.get('user_input', '')}")
                prompt_parts.append(f"Assistant: {turn.get('response_text', '')}")
        
        # Add current user input
        prompt_parts.append(f"\n\nUser input:\n{user_input}")
        prompt_parts.append("\nResponse:")
        
        prompt_text = "\n".join(prompt_parts)
        
        # Build contents list: files first, then text
        # According to Gemini API docs, files and text can be mixed in contents array
        # In the new SDK, we can pass File objects directly or use file_uri strings
        contents = []
        
        # Add file references - pass File objects directly (new SDK supports this)
        for uploaded_file in uploaded_files:
            contents.append(uploaded_file)
        
        # Add text content as a string
        contents.append(prompt_text)
        
        # Note: If this still causes 500 errors, it might be a model compatibility issue
        # Some models may not support files, or files might need to be referenced differently

        try:
            # Get tools configuration
            tools = self._get_tools_config()
            
            # Generate content with file references, text, and tools
            print(f"[ChatService.generate_response] Generating response with {len(uploaded_files)} file(s) and text prompt")
            # Tools are passed via config in the new SDK
            config = types.GenerateContentConfig(tools=tools, system_instruction=self.system_prompt,temperature=temperature,)
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
                        # Execute the function
                        result = self._execute_function_call(func_name, func_args)
                        
                        # Create function response using types (new SDK)
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
                    # Build follow-up contents: original contents + function responses as parts
                    # Function responses need to be wrapped in Part objects
                    follow_up_contents = contents.copy()
                    # Add function responses as parts
                    for func_response in function_responses:
                        # Create a Part with function_response using types
                        part = types.Part(function_response=func_response)
                        follow_up_contents.append(part)
                    
                    print(f"[ChatService.generate_response] Making follow-up call with {len(function_responses)} function response(s)")
                    config = types.GenerateContentConfig(tools=tools) if tools else None
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=follow_up_contents,
                        config=config
                    )
            
            # Extract final text response
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
                "function_calls": function_calls_made
            }
            
            # Append metadata as a JSON block that will be parsed separately
            metadata_json_str = json.dumps(metadata_json, indent=2)
            response_text += f"\n\n```json\n{metadata_json_str}\n```"
            
            # Track this turn in conversation history
            self.session_turns.append({
                "user_input": user_input,
                "response_text": response_text
            })
            
            # Keep only last 20 turns
            if len(self.session_turns) > 20:
                self.session_turns = self.session_turns[-20:]
            
            return response_text
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
                    
                    # Append metadata (files were attempted but failed, no function calls in fallback)
                    metadata_json = {
                        "referenced_files": referenced_files,  # Files were attempted
                        "function_calls": function_calls_made,  # May have some calls before error
                        "fallback_used": True
                    }
                    metadata_json_str = json.dumps(metadata_json, indent=2)
                    response_text += f"\n\n```json\n{metadata_json_str}\n```"
                    
                    # Track this turn in conversation history
                    self.session_turns.append({
                        "user_input": user_input,
                        "response_text": response_text
                    })
                    
                    # Keep only last 20 turns
                    if len(self.session_turns) > 20:
                        self.session_turns = self.session_turns[-20:]
                    
                    print("[ChatService.generate_response] Fallback successful - response generated without files")
                    return response_text
                except Exception as fallback_error:
                    print(f"[ChatService.generate_response] Fallback also failed: {str(fallback_error)}")
                    import traceback
                    traceback.print_exc()
                    raise ValueError(f"Error generating response: {error_msg}")
            else:
                import traceback
                traceback.print_exc()
                raise ValueError(f"Error generating response: {error_msg}")
