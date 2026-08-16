"""
Semantic code chunker for CodeForge AI repository intelligence (Step 6).

Chunks code at natural boundaries (class, function, module) rather than
fixed character counts. Supports Python, TypeScript, JavaScript, Go.

Chunk schema (dataclass):
  content       : str
  start_line    : int
  end_line      : int
  language      : str
  file_path     : str
  symbol_name   : Optional[str]
  token_count   : int
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.code_parser import ParsedSymbol, ParseResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CHUNK_LINES: int = 120
OVERLAP_LINES: int = 20

# Languages that support symbol-level chunking
SYMBOL_LANGUAGES = {"python", "typescript", "javascript", "go"}

# Languages treated as plain text (chunked by line count)
TEXT_LANGUAGES = {"markdown", "json", "yaml", "toml", "text", "plaintext"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ChunkResult:
    """Represents a single semantic chunk of source code."""

    content: str
    start_line: int
    end_line: int
    language: str
    file_path: str
    symbol_name: Optional[str]
    token_count: int = field(default=0)

    def __post_init__(self) -> None:
        if self.token_count == 0:
            self.token_count = estimate_tokens(self.content)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Estimate token count as word count * 1.3 (simple approximation)."""
    return int(len(text.split()) * 1.3)


def _make_chunk(
    lines: List[str],
    start_line: int,
    language: str,
    path: str,
    symbol_name: Optional[str],
) -> ChunkResult:
    """Build a ChunkResult from a list of source lines."""
    content = "\n".join(lines)
    end_line = start_line + len(lines) - 1
    return ChunkResult(
        content=content,
        start_line=start_line,
        end_line=end_line,
        language=language,
        file_path=path,
        symbol_name=symbol_name,
        token_count=estimate_tokens(content),
    )


def _split_large_chunk(
    lines: List[str],
    start_line: int,
    language: str,
    path: str,
    symbol_name: Optional[str],
    max_lines: int = MAX_CHUNK_LINES,
    overlap: int = OVERLAP_LINES,
) -> List[ChunkResult]:
    """
    Split a large block of lines into overlapping sub-chunks.

    Each sub-chunk is at most *max_lines* long. Consecutive chunks share
    *overlap* lines so that context is not lost at boundaries.

    Args:
        lines:       All source lines for the symbol / region.
        start_line:  1-based line number of the first line.
        language:    Language identifier string.
        path:        Source file path.
        symbol_name: Optional symbol name (prefixed with index for sub-chunks).
        max_lines:   Maximum number of lines per sub-chunk.
        overlap:     Number of lines shared between consecutive sub-chunks.

    Returns:
        List of ChunkResult objects.
    """
    chunks: List[ChunkResult] = []
    total = len(lines)
    step = max(1, max_lines - overlap)
    sub_index = 0
    offset = 0

    while offset < total:
        slice_end = min(offset + max_lines, total)
        chunk_lines = lines[offset:slice_end]
        sub_name = (
            f"{symbol_name}[{sub_index}]" if symbol_name else f"chunk[{sub_index}]"
        )
        chunks.append(
            _make_chunk(
                chunk_lines,
                start_line + offset,
                language,
                path,
                sub_name,
            )
        )
        if slice_end == total:
            break
        offset += step
        sub_index += 1

    return chunks


# ---------------------------------------------------------------------------
# Core chunking
# ---------------------------------------------------------------------------


def _chunk_symbol_language(
    path: str,
    all_lines: List[str],
    language: str,
    parse_result: ParseResult,
) -> List[ChunkResult]:
    """
    Produce symbol-level chunks for languages with structural parse results.

    Strategy
    --------
    1. Sort symbols by start line.
    2. For each symbol, determine its line range using its ``end_line_number``
       or (if absent) the start of the next symbol.
    3. If the range exceeds MAX_CHUNK_LINES, delegate to ``_split_large_chunk``.
    4. Collect all lines that are *not* covered by any symbol and emit them
       as "module" chunks.
    """
    chunks: List[ChunkResult] = []

    # Sort symbols by their starting line (1-based)
    symbols: List[ParsedSymbol] = sorted(
        parse_result.symbols or [], key=lambda s: s.line_number
    )

    total_lines = len(all_lines)

    # Build coverage map: covered[i] == True means line i+1 is inside a symbol
    covered = [False] * total_lines

    for idx, sym in enumerate(symbols):
        sym_start = sym.line_number  # 1-based
        # Determine end line: prefer the parsed end, fall back to next symbol start - 1
        if hasattr(sym, "end_line_number") and sym.end_line_number:
            sym_end = sym.end_line_number
        elif idx + 1 < len(symbols):
            sym_end = symbols[idx + 1].line_number - 1
        else:
            sym_end = total_lines

        # Clamp to valid range
        sym_start = max(1, min(sym_start, total_lines))
        sym_end = max(sym_start, min(sym_end, total_lines))

        # Mark lines as covered (0-indexed)
        for li in range(sym_start - 1, sym_end):
            if li < total_lines:
                covered[li] = True

        # Extract the relevant lines (0-indexed slice)
        sym_lines = all_lines[sym_start - 1 : sym_end]
        num_lines = len(sym_lines)

        if num_lines == 0:
            continue

        if num_lines > MAX_CHUNK_LINES:
            sub_chunks = _split_large_chunk(
                sym_lines,
                sym_start,
                language,
                path,
                sym.name,
                MAX_CHUNK_LINES,
                OVERLAP_LINES,
            )
            chunks.extend(sub_chunks)
        else:
            chunks.append(_make_chunk(sym_lines, sym_start, language, path, sym.name))

    # Collect uncovered lines → module-level chunks
    uncovered_lines: List[str] = []
    uncovered_start: Optional[int] = None

    def _flush_uncovered() -> None:
        nonlocal uncovered_lines, uncovered_start
        non_blank = [l for l in uncovered_lines if l.strip()]
        if not non_blank or uncovered_start is None:
            uncovered_lines = []
            uncovered_start = None
            return
        if len(uncovered_lines) > MAX_CHUNK_LINES:
            sub_chunks = _split_large_chunk(
                uncovered_lines,
                uncovered_start,
                language,
                path,
                "module",
                MAX_CHUNK_LINES,
                OVERLAP_LINES,
            )
            chunks.extend(sub_chunks)
        else:
            chunks.append(
                _make_chunk(uncovered_lines, uncovered_start, language, path, "module")
            )
        uncovered_lines = []
        uncovered_start = None

    for li, is_covered in enumerate(covered):
        if not is_covered:
            if uncovered_start is None:
                uncovered_start = li + 1  # 1-based
            uncovered_lines.append(all_lines[li])
        else:
            _flush_uncovered()

    _flush_uncovered()

    return chunks


def _chunk_text_language(
    path: str,
    all_lines: List[str],
    language: str,
) -> List[ChunkResult]:
    """
    Chunk plain-text / non-structural files by MAX_CHUNK_LINES with OVERLAP_LINES.
    """
    if not all_lines:
        return []

    return _split_large_chunk(
        all_lines,
        start_line=1,
        language=language,
        path=path,
        symbol_name=None,
        max_lines=MAX_CHUNK_LINES,
        overlap=OVERLAP_LINES,
    )


def chunk_file(
    path: str,
    source: str,
    language: str,
    parse_result: ParseResult,
) -> List[ChunkResult]:
    """
    Chunk a source file into semantic ChunkResult objects.

    For structured languages (Python, TypeScript, JavaScript, Go) the chunker
    splits at natural symbol boundaries using the provided ``parse_result``.
    For text-based formats (Markdown, JSON, YAML, …) it falls back to a
    sliding-window approach with overlap.

    Args:
        path:         Absolute or relative file path (used as metadata).
        source:       Full source text of the file.
        language:     Normalised language identifier (lowercase).
        parse_result: Output of ``code_parser.parse_code``; may have an empty
                      ``.symbols`` list for unsupported languages.

    Returns:
        Ordered list of ChunkResult objects covering the file.
    """
    if not source or not source.strip():
        logger.debug("chunk_file: empty source for %s, skipping.", path)
        return []

    lang_lower = (language or "").lower().strip()
    all_lines: List[str] = source.splitlines()

    try:
        if lang_lower in SYMBOL_LANGUAGES and parse_result is not None:
            return _chunk_symbol_language(path, all_lines, language, parse_result)
        else:
            return _chunk_text_language(path, all_lines, language)
    except Exception:  # pragma: no cover
        logger.exception(
            "chunk_file: unexpected error chunking %s; falling back to text chunker.",
            path,
        )
        return _chunk_text_language(path, all_lines, language)
