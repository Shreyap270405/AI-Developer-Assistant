import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any
from app.utils.file_filters import is_ignored_path, is_binary_file, detect_language
from app.utils.logger import logger

@dataclass
class CodeChunk:
    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    language: str
    content: str
    metadata: Dict[str, Any]

class ChunkingService:
    DEFAULT_CHUNK_LINES = 60
    DEFAULT_OVERLAP_LINES = 12

    @staticmethod
    def _chunk_notebook(file_path: Path, rel_path: str) -> List[CodeChunk]:
        try:
            notebook = json.loads(file_path.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            logger.warning(f"Failed to parse notebook {rel_path}: {exc}")
            return []

        chunks: List[CodeChunk] = []
        cells = notebook.get("cells") or []
        for index, cell in enumerate(cells, start=1):
            if (cell or {}).get("cell_type") != "code":
                continue
            source = cell.get("source", [])
            if isinstance(source, str):
                source_lines = source.splitlines(keepends=True)
            else:
                source_lines = []
                for part in source:
                    if isinstance(part, str):
                        source_lines.extend(part.splitlines(keepends=True))
            if not source_lines:
                continue

            content = "".join(source_lines).strip()
            if not content:
                continue
            header = f"# File: {rel_path} | Code cell {index} | Language: python\n"
            chunk_id = f"{rel_path.replace('/', '_')}_cell_{index}"
            chunks.append(CodeChunk(
                chunk_id=chunk_id,
                file_path=rel_path,
                start_line=1,
                end_line=len(content.splitlines()),
                language="python",
                content=header + content,
                metadata={
                    "file_path": rel_path,
                    "start_line": 1,
                    "end_line": len(content.splitlines()),
                    "language": "python",
                    "chunk_id": chunk_id,
                    "cell_index": index,
                    "is_notebook_cell": True,
                }
            ))
        return chunks

    @staticmethod
    def _chunk_csv_preview(file_path: Path, rel_path: str) -> List[CodeChunk]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as handle:
                reader = csv.reader(handle)
                rows = list(reader)
        except Exception as exc:
            logger.warning(f"Failed to parse CSV preview for {rel_path}: {exc}")
            return []

        if not rows:
            return []

        header = rows[0]
        preview_rows = rows[1:6]
        lines = [
            f"# File: {rel_path} | Dataset preview | Columns: {', '.join(header)}",
            f"# Rows sampled: {len(preview_rows)}",
            "# Dataset metadata: preview only; full dataset is not embedded as a single source chunk.",
        ]
        for idx, row in enumerate(preview_rows, start=1):
            lines.append(f"Row {idx}: {', '.join(row)}")

        content = "\n".join(lines)
        chunk_id = f"{rel_path.replace('/', '_')}_dataset_preview"
        return [CodeChunk(
            chunk_id=chunk_id,
            file_path=rel_path,
            start_line=1,
            end_line=len(lines),
            language="csv",
            content=content,
            metadata={
                "file_path": rel_path,
                "start_line": 1,
                "end_line": len(lines),
                "language": "csv",
                "chunk_id": chunk_id,
                "is_dataset_preview": True,
                "columns": header,
            }
        )]

    @classmethod
    def chunk_file(
        cls,
        file_path: Path,
        rel_path: str,
        chunk_lines: int = DEFAULT_CHUNK_LINES,
        overlap_lines: int = DEFAULT_OVERLAP_LINES
    ) -> List[CodeChunk]:
        """
        Splits a source file into overlapping chunks while calculating exact 1-indexed line numbers.
        """
        lower_path = rel_path.lower()
        if lower_path.endswith(".ipynb"):
            return cls._chunk_notebook(file_path, rel_path)
        if lower_path.endswith(".csv"):
            return cls._chunk_csv_preview(file_path, rel_path)

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Failed to read file {file_path} for chunking: {e}")
            return []

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)
        if total_lines == 0:
            return []

        language = detect_language(rel_path)
        chunks: List[CodeChunk] = []

        # If file is short enough, keep it as a single chunk
        if total_lines <= chunk_lines:
            chunk_content = "".join(lines)
            header = f"# File: {rel_path} | Lines: 1-{total_lines} | Language: {language}\n"
            chunk_id = f"{rel_path.replace('/', '_')}_1_{total_lines}"
            chunks.append(CodeChunk(
                chunk_id=chunk_id,
                file_path=rel_path,
                start_line=1,
                end_line=total_lines,
                language=language,
                content=header + chunk_content,
                metadata={
                    "file_path": rel_path,
                    "start_line": 1,
                    "end_line": total_lines,
                    "language": language,
                    "total_lines": total_lines,
                    "chunk_id": chunk_id
                }
            ))
            return chunks

        step = max(1, chunk_lines - overlap_lines)
        start_idx = 0

        while start_idx < total_lines:
            end_idx = min(start_idx + chunk_lines, total_lines)
            chunk_lines_slice = lines[start_idx:end_idx]
            start_line_num = start_idx + 1
            end_line_num = end_idx

            chunk_text = "".join(chunk_lines_slice)
            header = f"# File: {rel_path} | Lines: {start_line_num}-{end_line_num} | Language: {language}\n"
            chunk_id = f"{rel_path.replace('/', '_')}_{start_line_num}_{end_line_num}"

            chunks.append(CodeChunk(
                chunk_id=chunk_id,
                file_path=rel_path,
                start_line=start_line_num,
                end_line=end_line_num,
                language=language,
                content=header + chunk_text,
                metadata={
                    "file_path": rel_path,
                    "start_line": start_line_num,
                    "end_line": end_line_num,
                    "language": language,
                    "total_lines": total_lines,
                    "chunk_id": chunk_id
                }
            ))

            if end_idx >= total_lines:
                break
            start_idx += step

        return chunks

    @classmethod
    def chunk_project(cls, source_dir: Path) -> List[CodeChunk]:
        """
        Walks a project's source directory and chunks all eligible source files.
        """
        all_chunks: List[CodeChunk] = []
        if not source_dir.exists():
            return all_chunks

        for file_path in source_dir.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(source_dir).as_posix()
            if is_ignored_path(rel_path) or is_binary_file(file_path):
                continue

            file_chunks = cls.chunk_file(file_path, rel_path)
            all_chunks.extend(file_chunks)

        logger.info(f"Generated {len(all_chunks)} chunks for codebase at {source_dir}")
        return all_chunks
