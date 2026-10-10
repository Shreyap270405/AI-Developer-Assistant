from typing import List, Dict, Any, Optional
from app.database import db
from app.models.conversation import Conversation, Message, MessageCitation
from app.models.project import Project


class ConversationRepository:
    """
    Data-access layer for Conversation, Message, and MessageCitation models.
    Enforces user isolation so users cannot view or post to another user's conversation history.
    """

    @staticmethod
    def create_conversation(project_id: int, user_id: Optional[int] = None, title: str = "Codebase Discussion") -> Conversation:
        conv = Conversation(
            project_id=project_id,
            user_id=user_id,
            title=title
        )
        db.session.add(conv)
        db.session.commit()
        return conv

    @staticmethod
    def get_conversation_secure(conv_id: int, user_id: Optional[int] = None):
        """
        Retrieves a conversation by ID, checking ownership if user_id is provided.
        Returns: (conversation, error_status: str|None)
        """
        conv = db.session.get(Conversation, conv_id)
        if not conv:
            return None, "not_found"

        if conv.user_id is not None and user_id is not None:
            if conv.user_id != user_id:
                return None, "forbidden"

        return conv, None

    @staticmethod
    def list_conversations_secure(project_id: int, user_id: Optional[int] = None):
        """
        Lists conversations for a project, filtered by user if authenticated.
        """
        query = Conversation.query.filter_by(project_id=project_id)
        if user_id:
            query = query.filter((Conversation.user_id == user_id) | (Conversation.user_id == None))
        return query.order_by(Conversation.updated_at.desc()).all()

    @staticmethod
    def rename_conversation(conv_id: int, new_title: str, user_id: Optional[int] = None):
        """
        Renames a conversation, checking ownership if user_id is provided.
        Returns: (conversation, error_status: str|None)
        """
        conv, err = ConversationRepository.get_conversation_secure(conv_id, user_id)
        if err or not conv:
            return None, err
        conv.title = (new_title or "Codebase Discussion").strip()[:255]
        db.session.commit()
        return conv, None

    @staticmethod
    def delete_conversation(conv_id: int, user_id: Optional[int] = None):
        """
        Deletes a conversation and its cascaded messages/citations, checking ownership.
        Returns: (success: bool, error_status: str|None)
        """
        conv, err = ConversationRepository.get_conversation_secure(conv_id, user_id)
        if err or not conv:
            return False, err
        db.session.delete(conv)
        db.session.commit()
        return True, None

    @staticmethod
    def add_message(conversation_id: int, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        if metadata:
            msg.set_metadata(metadata)
        db.session.add(msg)
        db.session.commit()
        return msg

    @staticmethod
    def add_citations(message_id: int, citations: List[Dict[str, Any]]) -> List[MessageCitation]:
        created = []
        for c in citations:
            citation = MessageCitation(
                message_id=message_id,
                file_path=c.get("file_path", ""),
                start_line=int(c.get("start_line", 1)),
                end_line=int(c.get("end_line", 1)),
                snippet=c.get("snippet", "")
            )
            db.session.add(citation)
            created.append(citation)
        db.session.commit()
        return created

