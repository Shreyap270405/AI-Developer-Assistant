import json
import re
from typing import List, Dict, Any, Optional
from app.config import Config
from app.models.base import db
from app.models.conversation import Conversation, Message, MessageCitation
from app.services.vector_service import VectorService
from app.services.gemini_service import (
    GeminiService,
    AIServiceError,
    AIConfigurationError,
    AIRateLimitError,
    AITimeoutError,
    AIProviderError,
    AIValidationError,
)
from app.utils.logger import logger


def extract_citations_from_retrieved(retrieved_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts unique source citations from retrieved vector chunks.
    Ensures that file names and line numbers are derived strictly from retrieved data.
    """
    citations = []
    seen = set()
    for item in retrieved_chunks:
        meta = item.get("metadata", {})
        file_path = meta.get("file_path", "")
        start_line = int(meta.get("start_line", 1))
        end_line = int(meta.get("end_line", 1))
        key = (file_path, start_line, end_line)
        if file_path and key not in seen:
            seen.add(key)
            citations.append({
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
                "snippet": item.get("content", "")[:350]
            })
    return citations


class RAGService:
    """
    End-to-end RAG retrieval service connecting FAISS vector search,
    Google Gemini reasoning, grounded source citations, and conversation persistence.
    """

    MAX_CONTEXT_CHARS = 16000  # Enforce bounded context size

    @classmethod
    def ask_question(
        cls,
        project_id: int,
        question: str,
        conversation_id: Optional[int] = None,
        top_k: int = 5,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes an end-to-end RAG workflow:
        1. Validates project index presence
        2. Retrieves relevant chunks from FAISS vector store
        3. Formulates a bounded, delimited prompt
        4. Queries Gemini through the backend service
        5. Saves conversation history and citations to MySQL/SQLite
        6. Returns structured answer and traceable source metadata
        """
        question = (question or "").strip()
        if not question:
            raise AIValidationError("Question cannot be empty.")

        # Check if project vector store exists. If status is stale or the FAISS files were lost,
        # recover the index from the project's current source files before returning the not-indexed guidance.
        index = VectorService.load_index(project_id)
        if index is None:
            try:
                from pathlib import Path
                from app.models.project import Project
                project = db.session.get(Project, project_id)
                if project and project.storage_path:
                    source_dir = Path(project.storage_path) / "source"
                    if source_dir.exists() and VectorService.ensure_project_index(project_id, source_dir):
                        index = VectorService.load_index(project_id)
            except Exception:
                logger.exception(f"Automatic recovery of project {project_id} index failed")

        if index is None:
            answer_text = (
                "⚠️ **Project Codebase Not Indexed**\n\n"
                "This project's code has not been indexed into the vector database yet. "
                "To enable AI codebase search and grounded Q&A, please upload your project archive or "
                "trigger indexing from the project workspace."
            )
            retrieved_chunks = []
            citations = []
            status = "not_indexed"
        else:
            # 1. Retrieve top-k relevant code chunks from FAISS
            retrieved_chunks = VectorService.similarity_search(project_id, question, top_k=top_k)
            citations = extract_citations_from_retrieved(retrieved_chunks)

            if not retrieved_chunks:
                answer_text = (
                    f"🔍 **No Relevant Code Context Found**\n\n"
                    f"I searched the indexed project for *\"{question}\"*, but no relevant code chunks were matched. "
                    f"Please try asking with specific function names, file paths, or architectural components."
                )
                status = "no_context"
            else:
                # 2. Build bounded, delimited context payload
                context_parts = []
                total_chars = 0
                for i, chunk in enumerate(retrieved_chunks, 1):
                    meta = chunk.get("metadata", {})
                    fp = meta.get("file_path", "unknown")
                    s = meta.get("start_line", 1)
                    e = meta.get("end_line", 1)
                    raw_content = chunk.get("content", "").strip()
                    if len(raw_content) > 3000:
                        raw_content = raw_content[:3000] + "\n... [content truncated for length]"
                    
                    part = f"--- [SNIPPET {i}: `{fp}` Lines {s}–{e}] ---\n{raw_content}\n--- [END SNIPPET {i}] ---"
                    if total_chars + len(part) > cls.MAX_CONTEXT_CHARS:
                        break
                    context_parts.append(part)
                    total_chars += len(part)

                context_text = "\n\n".join(context_parts)

                # 3. Call Gemini if configured
                if GeminiService.is_configured():
                    try:
                        answer_text = GeminiService.generate_rag_answer(
                            question=question,
                            context_text=context_text,
                            citations=citations
                        )
                        status = "success"
                    except AIServiceError as e:
                        logger.warning(f"AI Service error on RAG query: {e.message}")
                        answer_text = (
                            f"⚠️ **Gemini AI Service Notice**: {e.message}\n\n"
                            f"Retrieved **{len(retrieved_chunks)}** relevant source reference(s) from your repository:\n\n"
                            + "\n".join([f"- **`{c['file_path']}`** (lines {c['start_line']}–{c['end_line']})" for c in citations])
                        )
                        status = "provider_warning"
                    except Exception as e:
                        logger.error(f"Unexpected error invoking Gemini in RAG: {e}")
                        answer_text = (
                            f"⚠️ **AI Generation Error**: `{str(e)}`\n\n"
                            f"Here are the top relevant code sections found in your project index:\n\n"
                            + "\n".join([f"- **`{c['file_path']}`** (lines {c['start_line']}–{c['end_line']})" for c in citations])
                        )
                        status = "provider_error"
                else:
                    answer_text = (
                        f"💡 **Codebase Context Retrieved** (`GEMINI_API_KEY` is not configured in backend environment):\n\n"
                        f"Retrieved **{len(retrieved_chunks)}** matching code section(s) for your query: *\"{question}\"*\n\n"
                        + "\n\n".join([
                            f"**File**: `{c['file_path']}` (Lines {c['start_line']}–{c['end_line']})\n```\n{c['snippet']}\n```"
                            for c in citations
                        ]) +
                        "\n\n*Set `GEMINI_API_KEY` in `backend/.env` to enable full conversational GenAI analysis.*"
                    )
                    status = "unconfigured_key"

        # 4. Save to conversation history in database
        conv = None
        if conversation_id:
            candidate = db.session.get(Conversation, conversation_id)
            if candidate and (user_id is None or candidate.user_id == user_id) and candidate.project_id == project_id:
                conv = candidate
        if not conv:
            conv = Conversation(
                project_id=project_id,
                user_id=user_id,
                title=question[:60] + ("..." if len(question) > 60 else "")
            )
            db.session.add(conv)
            db.session.flush()

        user_msg = Message(conversation_id=conv.id, role="user", content=question)
        assistant_msg = Message(conversation_id=conv.id, role="assistant", content=answer_text)
        assistant_msg.set_metadata({
            "model": GeminiService.get_model_name() if GeminiService.is_configured() else "local-retrieval",
            "citation_count": len(citations),
            "retrieved_chunks_count": len(retrieved_chunks),
            "status": status
        })

        db.session.add(user_msg)
        db.session.add(assistant_msg)
        db.session.flush()

        for c in citations:
            mc = MessageCitation(
                message_id=assistant_msg.id,
                file_path=c["file_path"],
                start_line=c["start_line"],
                end_line=c["end_line"],
                snippet=c.get("snippet", "")
            )
            db.session.add(mc)

        db.session.commit()

        return {
            "conversation_id": conv.id,
            "message_id": assistant_msg.id,
            "answer": answer_text,
            "citations": citations,
            "retrieved_chunks_count": len(retrieved_chunks),
            "model": GeminiService.get_model_name() if GeminiService.is_configured() else "local-retrieval",
            "status": status
        }

    @classmethod
    def explain_code(cls, code_snippet: str, file_path: str = "", language: str = "") -> str:
        if not GeminiService.is_configured():
            return "Please configure `GEMINI_API_KEY` in `backend/.env` to use the Code Explanation feature."
        try:
            res = GeminiService.explain_code(code=code_snippet, language=language, file_path=file_path)
            return res.get("summary", "")
        except Exception as e:
            return f"Error invoking Gemini: {str(e)}"

    @classmethod
    def debug_code(cls, code_snippet: str, error_message: str = "", file_path: str = "") -> str:
        if not GeminiService.is_configured():
            return "Please configure `GEMINI_API_KEY` in `backend/.env` to use the Debugging Assistant."
        try:
            res = GeminiService.debug_code(code=code_snippet, error_message=error_message, file_path=file_path)
            summary = res.get("summary", "")
            code = res.get("code", "")
            return f"{summary}\n\n```\n{code}\n```" if code else summary
        except Exception as e:
            return f"Error invoking Gemini: {str(e)}"

    @classmethod
    def review_code(cls, code_snippet: str, file_path: str = "") -> str:
        if not GeminiService.is_configured():
            return "Please configure `GEMINI_API_KEY` in `backend/.env` to use the Code Review feature."
        try:
            res = GeminiService.improve_code(code=code_snippet, focus="all", file_path=file_path)
            return res.get("summary", "")
        except Exception as e:
            return f"Error invoking Gemini: {str(e)}"

    @classmethod
    def generate_tests(cls, code_snippet: str, file_path: str = "", language: str = "") -> str:
        if not GeminiService.is_configured():
            return "Please configure `GEMINI_API_KEY` in `backend/.env` to use Test Generation."
        try:
            prompt = f"Generate unit tests for this code snippet from `{file_path}`:\n```{language}\n{code_snippet}\n```"
            res = GeminiService.generate_code(prompt=prompt, language=language)
            return res.get("code", "") or res.get("summary", "")
        except Exception as e:
            return f"Error invoking Gemini: {str(e)}"
