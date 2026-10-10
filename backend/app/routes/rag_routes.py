from flask import Blueprint, request, jsonify, g
from app.services.project_repository import ProjectRepository
from app.services.conversation_repository import ConversationRepository
from app.services.rag_service import RAGService
from app.services.vector_service import VectorService
from app.services.dev_tools_service import DevToolsService
from app.services.gemini_service import AIServiceError, AIValidationError
from app.utils.auth import jwt_required
from app.utils.logger import logger

rag_bp = Blueprint("rag", __name__)


@rag_bp.route("/<int:project_id>/query", methods=["POST"])
@jwt_required(optional=False)
def query_project(project_id):
    """
    RAG Query endpoint:
    Retrieves relevant code chunks from FAISS, calls Gemini, saves conversation & message citations,
    and returns grounded answer with traceable source citations.
    """
    user_id = getattr(g, "user_id", None)
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    conversation_id = data.get("conversation_id")
    top_k = int(data.get("top_k", 5))

    if not question:
        return jsonify({"error": "Question is required and cannot be empty.", "error_code": "validation_error"}), 400

    if conversation_id:
        conv, conv_err = ConversationRepository.get_conversation_secure(conversation_id, user_id)
        if conv_err == "not_found":
            return jsonify({"error": "Conversation not found", "error_code": "conversation_not_found"}), 404
        if conv_err == "forbidden":
            return jsonify({"error": "Forbidden: You do not have access to this conversation", "error_code": "forbidden"}), 403

    try:
        result = RAGService.ask_question(
            project_id=project_id,
            question=question,
            conversation_id=conversation_id,
            top_k=top_k,
            user_id=user_id
        )
        return jsonify(result), 200
    except Exception as e:
        logger.exception(f"Error executing RAG query on project {project_id}")
        return jsonify({"error": f"Failed to execute query: {str(e)}", "error_code": "rag_query_error"}), 500


@rag_bp.route("/<int:project_id>/search", methods=["POST"])
@jwt_required(optional=False)
def search_codebase(project_id):
    """
    Natural-language vector similarity search over indexed code chunks.
    Returns relevance percentages, grounded line ranges, and honest index state.
    """
    user_id = getattr(g, "user_id", None)
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    top_k = int(data.get("top_k", 8))

    if not query:
        return jsonify({"error": "Search query is required", "error_code": "validation_error"}), 400

    try:
        res = DevToolsService.semantic_search(project_id, user_id=user_id, query=query, top_k=top_k)
        return jsonify(res), 200
    except AIValidationError as e:
        return jsonify({"error": e.message, "error_code": e.error_code}), 400
    except Exception as e:
        logger.error(f"Error performing code search on project {project_id}: {e}")
        return jsonify({"error": f"Search failed: {str(e)}", "error_code": "search_error"}), 500


@rag_bp.route("/<int:project_id>/index", methods=["POST"])
@jwt_required(optional=False)
def reindex_project_rag(project_id):
    """
    RAG Blueprint alias to trigger code parsing, chunking, and FAISS indexing.
    """
    user_id = getattr(g, "user_id", None)
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    from pathlib import Path
    source_dir = Path(project.storage_path) / "source"
    if not source_dir.exists() or not any(source_dir.iterdir()):
        return jsonify({"error": "No source files found to index. Upload or import code first.", "error_code": "no_source_files"}), 400

    from app.services.ingestion_service import IngestionService
    from app.services.chunking_service import ChunkingService
    from app.models.base import db

    indexing_job = ProjectRepository.create_indexing_job(project.id)
    try:
        project.status = "indexing"
        project.error_message = None
        db.session.commit()

        file_count, _ = IngestionService.sync_project_files_to_db(project)
        chunks = ChunkingService.chunk_project(source_dir)
        chunk_count = len(chunks)

        if chunks:
            saved = VectorService.build_and_save_index(project.id, chunks)
            if not saved:
                raise RuntimeError("Failed to build and save FAISS index.")

        project.status = "ready"
        project.file_count = file_count
        project.chunk_count = chunk_count
        project.error_message = None
        db.session.commit()

        ProjectRepository.update_indexing_job(
            indexing_job.id,
            status="completed",
            progress=100,
            processed=file_count,
        )

        return jsonify({
            "message": "Project indexed successfully.",
            "file_count": file_count,
            "chunk_count": chunk_count,
            "status": "ready"
        }), 200
    except Exception as exc:
        project.status = "error"
        project.error_message = f"Indexing failed: {str(exc)}"
        db.session.commit()
        ProjectRepository.update_indexing_job(
            indexing_job.id,
            status="failed",
            error_message=str(exc)
        )
        logger.error(f"RAG reindex failed for project {project_id}: {exc}")
        return jsonify({"error": f"Indexing failed: {str(exc)}"}), 500


@rag_bp.route("/<int:project_id>/generate-docs", methods=["POST"])
@jwt_required(optional=False)
def generate_project_docs(project_id):
    """
    Generates a structured, evidence-grounded README.md from manifests & retrieved RAG code.
    Redacts secrets and marks unverified info as [Unknown: Not specified in repository files].
    """
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    custom_instructions = (data.get("custom_instructions") or "").strip()

    try:
        docs = DevToolsService.generate_project_readme(
            project_id=project_id,
            user_id=user_id,
            custom_instructions=custom_instructions
        )
        return jsonify(docs), 200
    except AIValidationError as e:
        return jsonify({"error": e.message, "error_code": e.error_code}), 400
    except AIServiceError as e:
        return jsonify({"error": e.message, "error_code": e.error_code}), e.status_code
    except Exception as e:
        logger.error(f"Error generating docs for project {project_id}: {e}")
        return jsonify({"error": f"Failed to generate documentation: {str(e)}", "error_code": "doc_gen_error"}), 500


@rag_bp.route("/<int:project_id>/save-docs", methods=["POST"])
@jwt_required(optional=False)
def save_project_docs(project_id):
    """
    Saves previewed documentation directly into project storage as a source file.
    """
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    filename = (data.get("filename") or "README.md").strip()
    content = data.get("content", "")

    if not content.strip():
        return jsonify({"error": "Content cannot be empty when saving documentation.", "error_code": "validation_error"}), 400

    try:
        res = DevToolsService.save_generated_readme(
            project_id=project_id,
            filename=filename,
            content=content,
            user_id=user_id
        )
        return jsonify(res), 200
    except AIValidationError as e:
        return jsonify({"error": e.message, "error_code": e.error_code}), 400
    except Exception as e:
        logger.error(f"Error saving docs for project {project_id}: {e}")
        return jsonify({"error": f"Failed to save documentation: {str(e)}", "error_code": "save_docs_error"}), 500


@rag_bp.route("/<int:project_id>/generate-tests", methods=["POST"])
@jwt_required(optional=False)
def generate_tests(project_id):
    """
    Generates unit/integration tests matching detected framework,
    covering happy path, edge cases, invalid inputs, and failure scenarios.
    """
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or data.get("code_snippet") or "").strip()
    file_path = (data.get("file_path") or "").strip()
    function_name = (data.get("function_name") or "").strip()
    framework = (data.get("framework") or "").strip()

    if not code and not file_path:
        return jsonify({"error": "Either 'file_path' or 'code' is required.", "error_code": "validation_error"}), 400

    try:
        result = DevToolsService.generate_test_cases(
            project_id=project_id,
            user_id=user_id,
            file_path=file_path,
            code_snippet=code,
            function_name=function_name,
            framework=framework
        )
        # Keep both 'tests' string and structured fields for complete backward compatibility
        result["tests"] = result.get("test_code", "")
        return jsonify(result), 200
    except AIValidationError as e:
        return jsonify({"error": e.message, "error_code": e.error_code}), 400
    except AIServiceError as e:
        return jsonify({"error": e.message, "error_code": e.error_code}), e.status_code
    except Exception as e:
        logger.error(f"Error generating tests for project {project_id}: {e}")
        return jsonify({"error": f"Failed to generate tests: {str(e)}", "error_code": "test_gen_error"}), 500


@rag_bp.route("/<int:project_id>/review", methods=["POST"])
@jwt_required(optional=False)
def review_code(project_id):
    """
    Performs AI code review returning structured findings (severity, category,
    verified line ranges, explanation, and remediation).
    """
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or data.get("code_snippet") or "").strip()
    file_path = (data.get("file_path") or "").strip()
    review_type = (data.get("review_type") or "comprehensive").strip()

    if not code and not file_path:
        return jsonify({"error": "Either 'file_path' or 'code' is required.", "error_code": "validation_error"}), 400

    try:
        result = DevToolsService.review_code(
            project_id=project_id,
            user_id=user_id,
            file_path=file_path,
            code_snippet=code,
            review_type=review_type
        )
        result["review"] = result.get("summary", "")
        return jsonify(result), 200
    except AIValidationError as e:
        return jsonify({"error": e.message, "error_code": e.error_code}), 400
    except AIServiceError as e:
        return jsonify({"error": e.message, "error_code": e.error_code}), e.status_code
    except Exception as e:
        logger.error(f"Error reviewing code for project {project_id}: {e}")
        return jsonify({"error": f"Failed to review code: {str(e)}", "error_code": "code_review_error"}), 500


@rag_bp.route("/<int:project_id>/explain", methods=["POST"])
@jwt_required(optional=False)
def explain_code(project_id):
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    file_path = data.get("file_path", "")
    language = data.get("language", "")

    if not code:
        return jsonify({"error": "Code snippet is required", "error_code": "validation_error"}), 400

    explanation = RAGService.explain_code(code, file_path=file_path, language=language)
    return jsonify({"explanation": explanation}), 200


@rag_bp.route("/<int:project_id>/debug", methods=["POST"])
@jwt_required(optional=False)
def debug_code(project_id):
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    error_message = data.get("error_message", "")
    file_path = data.get("file_path", "")

    if not code:
        return jsonify({"error": "Code snippet is required", "error_code": "validation_error"}), 400

    debugging_report = RAGService.debug_code(code, error_message=error_message, file_path=file_path)
    return jsonify({"debug_analysis": debugging_report}), 200


# ── Conversation Management Endpoints ──────────────────────────────────────────

@rag_bp.route("/<int:project_id>/conversations", methods=["GET"])
@jwt_required(optional=False)
def list_conversations(project_id):
    """
    Lists all saved conversations for the specified project.
    """
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    conversations = ConversationRepository.list_conversations_secure(project_id, user_id)
    return jsonify({"conversations": [c.to_dict() for c in conversations]}), 200


@rag_bp.route("/<int:project_id>/conversations", methods=["POST"])
@jwt_required(optional=False)
def create_conversation(project_id):
    """
    Explicitly creates a new conversation thread for the project.
    """
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "Codebase Discussion").strip()

    conv = ConversationRepository.create_conversation(
        project_id=project_id,
        user_id=user_id,
        title=title
    )
    return jsonify({"message": "Conversation created successfully", "conversation": conv.to_dict()}), 201


@rag_bp.route("/<int:project_id>/conversations/<int:conv_id>", methods=["GET"])
@jwt_required(optional=False)
def get_conversation_history(project_id, conv_id):
    """
    Fetches full message history and citations for a conversation.
    """
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    conv, conv_err = ConversationRepository.get_conversation_secure(conv_id, user_id)
    if conv_err == "not_found" or not conv or conv.project_id != project_id:
        return jsonify({"error": "Conversation not found", "error_code": "conversation_not_found"}), 404
    if conv_err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this conversation", "error_code": "forbidden"}), 403

    messages = [m.to_dict() for m in conv.messages]
    return jsonify({"conversation": conv.to_dict(), "messages": messages}), 200


@rag_bp.route("/<int:project_id>/conversations/<int:conv_id>", methods=["PATCH", "PUT"])
@jwt_required(optional=False)
def rename_conversation(project_id, conv_id):
    """
    Renames a conversation thread.
    """
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    new_title = (data.get("title") or "").strip()
    if not new_title:
        return jsonify({"error": "Title cannot be empty", "error_code": "validation_error"}), 400

    conv, conv_err = ConversationRepository.rename_conversation(conv_id, new_title, user_id)
    if conv_err == "not_found" or not conv or conv.project_id != project_id:
        return jsonify({"error": "Conversation not found", "error_code": "conversation_not_found"}), 404
    if conv_err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this conversation", "error_code": "forbidden"}), 403

    return jsonify({"message": "Conversation renamed successfully", "conversation": conv.to_dict()}), 200


@rag_bp.route("/<int:project_id>/conversations/<int:conv_id>", methods=["DELETE"])
@jwt_required(optional=False)
def delete_conversation(project_id, conv_id):
    """
    Deletes a conversation and its messages.
    """
    user_id = getattr(g, "user_id", None)
    _, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project", "error_code": "forbidden"}), 403

    conv, conv_err = ConversationRepository.get_conversation_secure(conv_id, user_id)
    if conv_err == "not_found" or not conv or conv.project_id != project_id:
        return jsonify({"error": "Conversation not found", "error_code": "conversation_not_found"}), 404
    if conv_err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this conversation", "error_code": "forbidden"}), 403

    success, del_err = ConversationRepository.delete_conversation(conv_id, user_id)
    if del_err:
        return jsonify({"error": f"Failed to delete conversation: {del_err}", "error_code": "deletion_error"}), 400

    return jsonify({"message": "Conversation deleted successfully", "id": conv_id}), 200
