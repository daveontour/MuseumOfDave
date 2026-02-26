"""Chat and subject configuration routes."""
import json
import re
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy import func

from ...services.exceptions import ValidationError, NotFoundError
from ...services.gemini_service import GeminiService
from ...services.chat_conversation_service import ChatConversationService
from ..deps import db, chat_service, subject_config_service
from ..state import (
    conversation_summary_lock,
    conversation_summary_in_progress,
    update_conversation_summary_progress_state,
    get_conversation_summary_progress_state,
    broadcast_conversation_summary_event_sync,
)
from src.services import subject_configuration_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    prompt: str
    voice: Optional[str] = None
    temperature: Optional[float] = None
    conversation_id: Optional[int] = None
    mood: Optional[str] = None
    companionMode: Optional[bool] = False


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str
    voice: Optional[str] = None
    embedded_json: Optional[Dict[str, Any]] = None


class ConversationCreateRequest(BaseModel):
    """Request model for creating a conversation."""
    title: str
    voice: str


class ConversationUpdateRequest(BaseModel):
    """Request model for updating a conversation."""
    title: Optional[str] = None
    voice: Optional[str] = None


class SubjectConfigurationRequest(BaseModel):
    """Request model for subject configuration."""
    subject_name: str
    system_instructions: str
    gender: Optional[str] = "Male"
    family_name: Optional[str] = None
    other_names: Optional[str] = None  # Comma-separated names
    email_addresses: Optional[str] = None  # Comma-separated email addresses
    phone_numbers: Optional[str] = None  # Comma-separated phone numbers
    whatsapp_handle: Optional[str] = None
    instagram_handle: Optional[str] = None


# ---------------------------------------------------------------------------
# Chat routes
# ---------------------------------------------------------------------------

@router.post("/chat/generate", response_model=ChatResponse)
async def generate_chat_response(request: ChatRequest):
    """Generate a chat response using ChatService with Gemini LLM.

    This endpoint allows users to send a prompt and receive a response from the ChatService.
    The ChatService includes reference documents (with available_for_task=True) and
    maintains conversation history (last 20 turns).

    Args:
        request: ChatRequest with prompt and optional voice selection

    Returns:
        ChatResponse with generated response text

    Raises:
        HTTPException: 500 on error
    """

    print(f"[generate_chat_response] Request: {request}")
    try:
        # Use global ChatService instance (maintains conversation history across requests)
        # Set voice if provided
        # if request.voice:
        #     try:
        #         chat_service.set_voice(request.voice)
        #         print(f"[generate_chat_response] Voice set to: {request.voice}")
        #     except Exception as e:
        #         print(f"[generate_chat_response] Warning: Could not set voice '{request.voice}': {str(e)}")

        #     if request.voice == "owner":
        #         try:
        #             print(f"[generate_chat_response] Setting mood to '{request.mood}'")
        #             chat_service.set_mood(request.mood)
        #             configuration = subject_config_service.get_configuration()
        #             if configuration:
        #                 chat_service.set_psychological_profile(configuration.psychological_profile_ai)
        #                 chat_service.set_writing_style(configuration.writing_style_ai)
        #         except Exception as e:
        #             print(f"[generate_chat_response] Warning: Could not set voice 'secret_admirer': {str(e)}")
        #     else:
        #         print(f"[generate_chat_response]  Setting mood to 'neutral'")
        #         chat_service.set_mood("neutral")
        #         print(f"[generate_chat_response]Setting Psychological profile and writing style to None")
        #         chat_service.set_psychological_profile(None)
        #         chat_service.set_writing_style(None)

        mood = "neutral"
        if request.mood:
            mood = request.mood
        # Generate response using global chat_service instance
        #(Reference documents are uploaded to Gemini in the chat service )
        temperature = request.temperature if request.temperature is not None else 0.0
        response_text, metadata_json_str = chat_service.generate_response(
            request.prompt,
            temperature=temperature,
            voice=request.voice,
            mood=mood,
            conversation_id=request.conversation_id,
            db=db,
            companionMode=request.companionMode
        )

        # Parse response to extract embedded JSON from markdown code blocks
        text_content = response_text
        metadata_json = json.loads(metadata_json_str)
        embedded_json = None

        # Pattern to match JSON in markdown code blocks (```json ... ```)
        json_pattern = r'```json\s*\n(.*?)\n```'
        matches = re.findall(json_pattern, response_text, re.DOTALL)

        if matches:
            # Parse all JSON blocks and merge them
            merged_json = {}
            for json_str in matches:
                try:
                    parsed_json = json.loads(json_str.strip())



                    # Merge: if keys conflict, later blocks override earlier ones
                    # But preserve metadata keys (referenced_files, function_calls) separately
                    if isinstance(parsed_json, dict):
                        # If this block has metadata keys, merge them specially
                        if "referenced_files" in parsed_json or "function_calls" in parsed_json:
                            # This is metadata block - merge metadata keys
                            if "referenced_files" in parsed_json:
                                metadata_json["referenced_files"] = parsed_json["referenced_files"]
                            if "function_calls" in parsed_json:
                                metadata_json["function_calls"] = parsed_json["function_calls"]
                            # Also merge other keys
                            for key, value in parsed_json.items():
                                if key not in ["referenced_files", "function_calls"]:
                                    metadata_json[key] = value
                        else:
                            # Regular JSON block - merge normally
                            metadata_json.update(parsed_json)
                except json.JSONDecodeError as e:
                    print(f"[generate_chat_response] Warning: Could not parse embedded JSON block: {str(e)}")
                    continue

            if metadata_json:
                #embedded_json = merged_json
                # Remove all JSON code blocks from the text content
                text_content = re.sub(json_pattern, '', response_text, flags=re.DOTALL).strip()
                metadata_json["temperature"] = request.temperature
                metadata_json["prompt"] = request.prompt
                metadata_json["voice"] = chat_service.voice
                metadata_json["response_text"] = text_content

        return ChatResponse(
            response=text_content,
            voice=chat_service.voice,
            embedded_json=metadata_json
        )

    except ValueError as e:
        # Missing API key or invalid data
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    except Exception as e:
        # Other errors
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating chat response: {error_msg}"
        )


# ---------------------------------------------------------------------------
# Conversation Management Endpoints
# ---------------------------------------------------------------------------

@router.post("/chat/conversations")
async def create_conversation(request: ConversationCreateRequest):
    """Create a new conversation.

    Args:
        request: ConversationCreateRequest with title and voice

    Returns:
        Dictionary with conversation details
    """
    try:
        conversation_service = ChatConversationService(db=db)
        conversation = conversation_service.create_conversation(request.title, request.voice)

        return {
            "id": conversation.id,
            "title": conversation.title,
            "voice": conversation.voice,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in create_conversation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creating conversation: {str(e)}")


@router.get("/chat/conversations")
async def list_conversations(limit: Optional[int] = Query(None)):
    """List all conversations, ordered by most recent activity.

    Args:
        limit: Optional limit on number of conversations to return

    Returns:
        List of conversation dictionaries
    """
    try:
        conversation_service = ChatConversationService(db=db)
        conversations = conversation_service.list_conversations(limit=limit)

        # Import here to avoid circular imports
        from ...database.models import ChatTurn

        result = []
        session = db.get_session()
        try:
            for conv in conversations:
                # Get turn count using a query (more reliable than lazy loading)
                # Use the conversation ID directly since we can't rely on the relationship
                # across different sessions
                turn_count = session.query(func.count(ChatTurn.id)).filter(
                    ChatTurn.conversation_id == conv.id
                ).scalar() or 0

                result.append({
                    "id": conv.id,
                    "title": conv.title,
                    "voice": conv.voice,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                    "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
                    "turn_count": turn_count
                })
        finally:
            session.close()

        return result
    except Exception as e:
        import traceback
        print(f"Error in list_conversations: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error listing conversations: {str(e)}")


@router.get("/chat/conversations/{conversation_id}")
async def get_conversation(conversation_id: int):
    """Get conversation details including turns.

    Args:
        conversation_id: ID of the conversation

    Returns:
        Dictionary with conversation details and turns
    """
    try:
        conversation_service = ChatConversationService(db=db)
        conversation = conversation_service.get_conversation(conversation_id)

        # Get turns
        turns = conversation_service.get_conversation_turns(conversation_id, limit=30)

        turns_data = []
        for turn in turns:
            turns_data.append({
                "id": turn.id,
                "user_input": turn.user_input,
                "response_text": turn.response_text,
                "voice": turn.voice,
                "temperature": turn.temperature,
                "turn_number": turn.turn_number,
                "created_at": turn.created_at.isoformat() if turn.created_at else None
            })

        return {
            "id": conversation.id,
            "title": conversation.title,
            "voice": conversation.voice,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
            "turns": turns_data
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in get_conversation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting conversation: {str(e)}")


@router.put("/chat/conversations/{conversation_id}")
async def update_conversation(conversation_id: int, request: ConversationUpdateRequest):
    """Update conversation metadata.

    Args:
        conversation_id: ID of the conversation
        request: ConversationUpdateRequest with optional title and voice

    Returns:
        Dictionary with updated conversation details
    """
    try:
        conversation_service = ChatConversationService(db=db)
        conversation = conversation_service.update_conversation(
            conversation_id,
            title=request.title,
            voice=request.voice
        )

        return {
            "id": conversation.id,
            "title": conversation.title,
            "voice": conversation.voice,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in update_conversation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating conversation: {str(e)}")


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int):
    """Delete a conversation and all its turns.

    Args:
        conversation_id: ID of the conversation

    Returns:
        Dictionary with success status
    """
    try:
        conversation_service = ChatConversationService(db=db)
        conversation_service.delete_conversation(conversation_id)

        return {"success": True, "message": f"Conversation {conversation_id} deleted successfully"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in delete_conversation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error deleting conversation: {str(e)}")


@router.get("/chat/conversations/{conversation_id}/turns")
async def get_conversation_turns(conversation_id: int, limit: int = Query(30, ge=1, le=100)):
    """Get turns for a conversation.

    Args:
        conversation_id: ID of the conversation
        limit: Maximum number of turns to return (default 30, max 100)

    Returns:
        List of turn dictionaries
    """
    try:
        conversation_service = ChatConversationService(db=db)
        turns = conversation_service.get_conversation_turns(conversation_id, limit=limit)

        turns_data = []
        for turn in turns:
            turns_data.append({
                "id": turn.id,
                "user_input": turn.user_input,
                "response_text": turn.response_text,
                "voice": turn.voice,
                "temperature": turn.temperature,
                "turn_number": turn.turn_number,
                "created_at": turn.created_at.isoformat() if turn.created_at else None
            })

        return turns_data
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in get_conversation_turns: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting conversation turns: {str(e)}")


# ---------------------------------------------------------------------------
# Subject Configuration Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/subject-configuration")
async def get_subject_configuration():
    """Get current subject configuration.

    Returns:
        Dictionary with subject configuration or 404 if not set
    """
    try:

        configuration = subject_config_service.get_configuration()

        if not configuration:
            raise HTTPException(status_code=404, detail="Subject configuration not found")

        return {
            "id": configuration.id,
            "subject_name": configuration.subject_name,
            "gender": configuration.gender,
            "family_name": configuration.family_name,
            "other_names": configuration.other_names,
            "email_addresses": configuration.email_addresses,
            "phone_numbers": configuration.phone_numbers,
            "whatsapp_handle": configuration.whatsapp_handle,
            "instagram_handle": configuration.instagram_handle,
            "writing_style_ai": configuration.writing_style_ai,
            "psychological_profile_ai": configuration.psychological_profile_ai,
            "system_instructions": configuration.system_instructions,
            "core_system_instructions": configuration.core_system_instructions,
            "created_at": configuration.created_at.isoformat() if configuration.created_at else None,
            "updated_at": configuration.updated_at.isoformat() if configuration.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error in get_subject_configuration: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting subject configuration: {str(e)}")


@router.post("/api/subject-configuration")
async def create_or_update_subject_configuration(request: SubjectConfigurationRequest):
    """Create or update subject configuration.

    Args:
        request: SubjectConfigurationRequest with subject_name and system_instructions

    Returns:
        Dictionary with created/updated configuration
    """
    try:
        configuration = subject_config_service.create_or_update_configuration(
            subject_name=request.subject_name,
            system_instructions=request.system_instructions,
            gender=request.gender,
            family_name=request.family_name,
            other_names=request.other_names,
            email_addresses=request.email_addresses,
            phone_numbers=request.phone_numbers,
            whatsapp_handle=request.whatsapp_handle,
            instagram_handle=request.instagram_handle
        )

        # Reload system prompt in chat service to use new configuration
        chat_service.reload_system_prompt(db=db)

        return {
            "id": configuration.id,
            "subject_name": configuration.subject_name,
            "gender": configuration.gender,
            "family_name": configuration.family_name,
            "other_names": configuration.other_names,
            "email_addresses": configuration.email_addresses,
            "phone_numbers": configuration.phone_numbers,
            "whatsapp_handle": configuration.whatsapp_handle,
            "instagram_handle": configuration.instagram_handle,
            "system_instructions": configuration.system_instructions,
            "core_system_instructions": configuration.core_system_instructions,
            "created_at": configuration.created_at.isoformat() if configuration.created_at else None,
            "updated_at": configuration.updated_at.isoformat() if configuration.updated_at else None
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in create_or_update_subject_configuration: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error saving subject configuration: {str(e)}")
