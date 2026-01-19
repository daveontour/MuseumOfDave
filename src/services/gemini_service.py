"""Gemini LLM service for conversation summarization."""

import os
import json
import time
from typing import Dict, Any, Optional, List
from io import BytesIO
import google.generativeai as genai
from ..database import Database
from ..database.models import ReferenceDocument


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
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
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
            response = self.model.generate_content(prompt)
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
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

        self.voice_instructions_list = self._load_voice_instructions()
        self.voice = "expert"
        self.voice_instructions = self.voice_instructions_list[self.voice]
        self.system_prompt = self._load_system_prompt()
        self.session_turns = []  # List of {"user_input": str, "response_text": str}
        self.db = None  # Will be set when needed
        self._uploaded_files_cache: Dict[int, Any] = {}  # Cache: doc_id -> File object or file info dict

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
        # Optionally clear file cache when clearing session
        # self._uploaded_files_cache.clear()

    def _upload_file_to_gemini(self, doc: ReferenceDocument) -> Optional[Any]:
        """Upload a reference document to Gemini File API and return the File object.
        
        Args:
            doc: ReferenceDocument instance
            
        Returns:
            File object if successful, None otherwise
        """
        try:
            # Check cache first
            if doc.id in self._uploaded_files_cache:
                cached_file = self._uploaded_files_cache[doc.id]
                # Verify file still exists (files expire after ~48 hours)
                try:
                    file_info = genai.get_file(cached_file.name)
                    if file_info.state.name == "ACTIVE":
                        return cached_file
                    else:
                        # File expired or not active, remove from cache
                        del self._uploaded_files_cache[doc.id]
                except Exception:
                    # File doesn't exist anymore, remove from cache
                    del self._uploaded_files_cache[doc.id]
            
            # Create a temporary file-like object from binary data
            file_data = BytesIO(doc.data)
            file_data.name = doc.filename
            
            # Upload file to Gemini
            print(f"[ChatService._upload_file_to_gemini] Uploading file: {doc.filename}")
            # If the content type is application/json, change it to text/plain
            # This is because Gemini does not support application/json files
            if doc.content_type == "application/json" or "json" in doc.content_type.lower():
                doc.content_type = "text/plain"
            uploaded_file = genai.upload_file(
                path=file_data,
                mime_type=doc.content_type,
                display_name=doc.title or doc.filename
            )
            
            # Wait for file to be processed (some file types need processing)
            max_wait_time = 60  # seconds
            wait_interval = 2  # seconds
            elapsed = 0
            
            while uploaded_file.state.name != "ACTIVE" and elapsed < max_wait_time:
                time.sleep(wait_interval)
                elapsed += wait_interval
                uploaded_file = genai.get_file(uploaded_file.name)
                print(f"[ChatService._upload_file_to_gemini] File state: {uploaded_file.state.name}, waiting...")
            
            if uploaded_file.state.name == "ACTIVE":
                # Cache the File object
                self._uploaded_files_cache[doc.id] = uploaded_file
                print(f"[ChatService._upload_file_to_gemini] File uploaded successfully: {doc.filename}")
                return uploaded_file
            else:
                print(f"[ChatService._upload_file_to_gemini] File {doc.filename} did not become ACTIVE in time (state: {uploaded_file.state.name})")
                return None
                
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

    def generate_response(self, user_input: str, db: Optional[Database] = None) -> str:
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
        
        # Upload and include reference documents as files
        uploaded_files = []
        if db:
            try:
                session = db.get_session()
                try:
                    documents = session.query(ReferenceDocument).filter(
                        ReferenceDocument.available_for_task == True
                    ).all()
                    
                    for doc in documents:
                        uploaded_file = self._upload_file_to_gemini(doc)
                        if uploaded_file:
                            uploaded_files.append(uploaded_file)
                            print(f"[ChatService.generate_response] Added file reference: {doc.filename}")
                finally:
                    session.close()
            except Exception as e:
                print(f"[ChatService.generate_response] Warning: Could not retrieve reference documents: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Build text prompt with voice instructions, conversation history, and user input
        prompt_parts = []

        prompt_parts.append(self.system_prompt)
        
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
        # But we need to structure it as a list where each item can be a string or File object
        contents = []
        
        # Add file references - pass File objects directly
        for uploaded_file in uploaded_files:
            contents.append(uploaded_file)
        
        # Add text content as a string
        contents.append(prompt_text)
        
        # Note: If this still causes 500 errors, it might be a model compatibility issue
        # Some models may not support files, or files might need to be referenced differently

        try:
            # Generate content with file references and text
            print(f"[ChatService.generate_response] Generating response with {len(uploaded_files)} file(s) and text prompt")
            response = self.model.generate_content(contents)
            response_text = response.text.strip()
            
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
                    response = self.model.generate_content(prompt_text)
                    response_text = response.text.strip()
                    
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
