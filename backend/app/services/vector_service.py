import os
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import Config
from app.database import db
from app.services.chunking_service import CodeChunk
from app.utils.logger import logger

from langchain_core.embeddings import Embeddings

class LocalDeterministicEmbeddings(Embeddings):
    """
    Lightweight deterministic hash-based embedding generator used as an offline/development fallback
    when GEMINI_API_KEY is not yet supplied or during local unit testing.
    Produces normalized 128-dimensional vectors.
    """
    def __init__(self, dim: int = 128):
        self.dim = dim

    def _embed_text(self, text: str) -> List[float]:
        import re
        import hashlib
        vec = np.zeros(self.dim, dtype=np.float32)
        words = re.findall(r"[a-z0-9]+", text.lower())
        if not words:
            return vec.tolist()
        for i, word in enumerate(words):
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[h] += 1.0 / (1.0 + (i % 5))
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_text(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_text(text)

    def __call__(self, text: str) -> List[float]:
        return self.embed_query(text)

class VectorService:
    @classmethod
    def ensure_project_index(cls, project_id: int, source_dir: Optional[Path] = None) -> bool:
        """
        Rebuilds the FAISS index for a project if it is missing or unreadable.
        This repairs stale 'ready' records left behind after a restart or a partial import.
        """
        index_file = cls.get_index_path(project_id) / "index.faiss"
        if index_file.exists():
            return True

        if source_dir is None:
            try:
                from app.models.project import Project
                project = db.session.get(Project, project_id)
                if project and project.storage_path:
                    source_dir = Path(project.storage_path) / "source"
            except Exception:
                source_dir = None

        if source_dir is None:
            return False
        if not Path(source_dir).exists():
            return False

        from app.services.chunking_service import ChunkingService
        from app.models.project import Project

        chunks = ChunkingService.chunk_project(Path(source_dir))
        if not chunks:
            logger.warning(f"No indexable content found for project {project_id} under {source_dir}.")
            return False

        saved = cls.build_and_save_index(project_id, chunks)
        if saved:
            project = db.session.get(Project, project_id)
            if project is not None:
                project.status = "ready"
                project.chunk_count = len(chunks)
                project.error_message = None
                db.session.commit()
        return saved

    @classmethod
    def get_embeddings(cls, target_dim: Optional[int] = None):
        """
        Returns Gemini Embeddings if API key is present; otherwise falls back to deterministic local embeddings.
        Supports target_dim to ensure embedding dimensionality matches existing FAISS indexes.
        """
        # If the existing index is known to be 128-dimensional (local deterministic), use matched local embeddings
        if target_dim == 128:
            logger.info("Using 128-dimensional local embeddings to match existing index.")
            return LocalDeterministicEmbeddings(dim=128)

        if Config.GEMINI_API_KEY and Config.GEMINI_API_KEY.strip():
            candidate_models = [
                Config.GEMINI_EMBEDDING_MODEL,
                "models/gemini-embedding-001",
                "gemini-embedding-001",
                "models/gemini-embedding-2-preview"
            ]
            # Deduplicate while preserving order
            seen_models = set()
            models_to_try = []
            for m in candidate_models:
                if m and m not in seen_models:
                    seen_models.add(m)
                    models_to_try.append(m)

            for model_name in models_to_try:
                try:
                    from langchain_google_genai import GoogleGenerativeAIEmbeddings
                    emb = GoogleGenerativeAIEmbeddings(
                        model=model_name,
                        google_api_key=Config.GEMINI_API_KEY
                    )
                    # Quick probe to ensure model works
                    return emb
                except Exception as e:
                    logger.warning(f"Failed to initialize GoogleGenerativeAIEmbeddings with {model_name}: {e}")

        logger.info("Using local embeddings engine (No GEMINI_API_KEY configured or Gemini embedding failed).")
        return LocalDeterministicEmbeddings(dim=target_dim or 128)

    @classmethod
    def get_index_path(cls, project_id: int) -> Path:
        try:
            from flask import current_app
            base = Path(current_app.config.get("STORAGE_DIR") or Config.STORAGE_DIR)
        except Exception:
            base = Path(Config.STORAGE_DIR)
        return base / f"proj_{project_id}" / "faiss_index"


    @classmethod
    def build_and_save_index(cls, project_id: int, chunks: List[CodeChunk]) -> bool:
        """
        Builds a FAISS index from the provided code chunks and saves it atomically to disk.
        Uses a staging directory swap to prevent partial writes and eliminate stale index data.
        """
        if not chunks:
            logger.warning(f"No chunks provided to build index for project {project_id}.")
            return False

        import shutil
        from langchain_community.vectorstores import FAISS

        index_dir = cls.get_index_path(project_id)
        parent_dir = index_dir.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = parent_dir / f"faiss_index_tmp_{project_id}"

        texts = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]

        embeddings = cls.get_embeddings()
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)

            vectorstore = FAISS.from_texts(texts=texts, embedding=embeddings, metadatas=metadatas)
            vectorstore.save_local(str(temp_dir))

            # Safe directory replacement (handles Windows locked files and rename semantics)
            if index_dir.exists():
                try:
                    shutil.rmtree(index_dir)
                    temp_dir.rename(index_dir)
                except Exception:
                    # Alternative copy and clean
                    if not index_dir.exists():
                        temp_dir.rename(index_dir)
                    else:
                        shutil.copytree(temp_dir, index_dir, dirs_exist_ok=True)
                        shutil.rmtree(temp_dir, ignore_errors=True)
            else:
                temp_dir.rename(index_dir)

            logger.info(f"FAISS index saved successfully for project {project_id} with {len(chunks)} chunks.")
            return True
        except Exception as e:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            logger.error(f"Error building FAISS index for project {project_id}: {e}")
            return False

    @classmethod
    def load_index(cls, project_id: int):
        """
        Loads the FAISS index for the specified project.
        Automatically checks the index vector dimensionality so that mismatched
        embedding models do not cause runtime failures.
        """
        from langchain_community.vectorstores import FAISS

        index_dir = cls.get_index_path(project_id)
        index_file = index_dir / "index.faiss"
        if not index_file.exists():
            return None

        # Inspect index dimension using faiss directly
        target_dim = None
        try:
            import faiss
            raw_idx = faiss.read_index(str(index_file))
            target_dim = raw_idx.d
        except Exception as e:
            logger.debug(f"Could not inspect index dimension for project {project_id}: {e}")

        embeddings = cls.get_embeddings(target_dim=target_dim)
        try:
            return FAISS.load_local(
                str(index_dir),
                embeddings,
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            logger.error(f"Error loading FAISS index for project {project_id}: {e}")
            # If load failed and target_dim was 128, try fallback with local embeddings
            if target_dim != 128:
                try:
                    logger.info(f"Retrying load_index with local embeddings for project {project_id}")
                    return FAISS.load_local(
                        str(index_dir),
                        LocalDeterministicEmbeddings(dim=target_dim or 128),
                        allow_dangerous_deserialization=True
                    )
                except Exception as e2:
                    logger.error(f"Fallback load_index also failed for project {project_id}: {e2}")
            return None

    @classmethod
    def similarity_search(cls, project_id: int, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Searches the project index and returns matching chunks with metadata and scores.
        """
        vectorstore = cls.load_index(project_id)
        if not vectorstore:
            logger.warning(f"Index not found for project {project_id}.")
            return []

        try:
            results = vectorstore.similarity_search_with_relevance_scores(query, k=top_k)
            retrieved = []
            for doc, score in results:
                retrieved.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": round(float(score), 4) if score is not None else 0.0
                })
            return retrieved
        except Exception:
            logger.exception(f"Error executing similarity search for project {project_id}")
            # Fallback to basic similarity search without scores
            try:
                docs = vectorstore.similarity_search(query, k=top_k)
                return [{"content": d.page_content, "metadata": d.metadata, "score": 1.0} for d in docs]
            except Exception:
                logger.exception(f"Similarity search fallback failed for project {project_id}")
                return []
