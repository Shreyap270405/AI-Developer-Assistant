import pytest
from pathlib import Path
from app.services.chunking_service import ChunkingService

def test_chunk_file_single_chunk(tmp_path):
    sample_code = """def hello():
    print("world")
    return True
"""
    file_path = tmp_path / "hello.py"
    file_path.write_text(sample_code, encoding="utf-8")

    chunks = ChunkingService.chunk_file(file_path, "src/hello.py", chunk_lines=10, overlap_lines=2)
    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 3
    assert chunks[0].language == "python"
    assert "def hello():" in chunks[0].content

def test_chunk_file_multiple_chunks_line_accuracy(tmp_path):
    # Create a 100-line file
    lines = [f"line_{i} = {i}\n" for i in range(1, 101)]
    file_path = tmp_path / "large.py"
    file_path.write_text("".join(lines), encoding="utf-8")

    chunks = ChunkingService.chunk_file(file_path, "large.py", chunk_lines=30, overlap_lines=5)
    assert len(chunks) > 1

    # First chunk should start at line 1 and end at line 30
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 30

    # Second chunk should start at line 26 (30 - 5 + 1)
    assert chunks[1].start_line == 26

    # Last chunk should end at line 100
    assert chunks[-1].end_line == 100
