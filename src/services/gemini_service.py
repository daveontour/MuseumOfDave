"""Gemini LLM service for conversation summarization."""

import os
import json
from typing import Dict, Any, Optional
import google.generativeai as genai


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
        prompt = f"""Please provide a concise summary of the following conversation. 
Focus on the main topics discussed, key decisions made, and important information shared. Include a characterisation of the participants relationships and dynamics.

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
