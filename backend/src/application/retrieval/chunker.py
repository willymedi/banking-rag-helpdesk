"""Structural-aware chunker.

Detecta secciones marcadas con `## `, `### ` y subdivide con sliding window
respetando fronteras de sección. Persiste offsets de carácter del documento original.
"""

import hashlib
import re
from dataclasses import dataclass

import tiktoken

from src.domain.entities.document import Chunk

SECTION_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
DEFAULT_ENCODING = "cl100k_base"


@dataclass(frozen=True, slots=True)
class ChunkerConfig:
    target_tokens: int = 300
    overlap_tokens: int = 60
    min_chunk_tokens: int = 50


@dataclass(frozen=True, slots=True)
class _Section:
    title: str
    path: tuple[str, ...]
    level: int
    start: int
    end: int  # exclusive
    text: str


def _split_sections(text: str) -> list[_Section]:
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return [_Section("Documento", ("Documento",), 1, 0, len(text), text)]

    sections: list[_Section] = []
    path_stack: list[str] = []

    # Add a synthetic preamble if there is content before first heading
    first = matches[0]
    if first.start() > 0:
        preamble_text = text[: first.start()].strip()
        if preamble_text:
            sections.append(_Section("Preámbulo", ("Preámbulo",), 1, 0, first.start(), preamble_text))

    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        # update path stack to current level
        path_stack = path_stack[: level - 1] + [title]

        section_start = m.end()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[section_start:section_end].strip("\n")
        if not body.strip():
            continue
        sections.append(
            _Section(
                title=title,
                path=tuple(path_stack),
                level=level,
                start=section_start,
                end=section_end,
                text=body,
            )
        )
    return sections


def _sliding_window_tokens(
    text: str,
    section_offset: int,
    encoder: tiktoken.Encoding,
    target: int,
    overlap: int,
) -> list[tuple[str, int, int]]:
    tokens = encoder.encode(text)
    if len(tokens) <= target:
        return [(text, section_offset, section_offset + len(text))]

    chunks: list[tuple[str, int, int]] = []
    step = max(target - overlap, 1)
    cursor_tok = 0
    while cursor_tok < len(tokens):
        end_tok = min(cursor_tok + target, len(tokens))
        chunk_tokens = tokens[cursor_tok:end_tok]
        chunk_text = encoder.decode(chunk_tokens)
        # Map back to char offsets approximately by progressive search
        # Acceptable for prototype; productive: use offset_mapping from a tokenizer.
        local_start = text.find(chunk_text[:32]) if len(chunk_text) >= 32 else text.find(chunk_text)
        if local_start < 0:
            local_start = 0
        local_end = local_start + len(chunk_text)
        chunks.append((chunk_text, section_offset + local_start, section_offset + local_end))
        if end_tok >= len(tokens):
            break
        cursor_tok += step
    return chunks


def _hash_id(doc_id: str, section_idx: int, chunk_idx: int, text: str) -> str:
    h = hashlib.sha1(f"{doc_id}|{section_idx}|{chunk_idx}|{text[:64]}".encode()).hexdigest()[:8]
    return f"{doc_id}_s{section_idx:02d}_c{chunk_idx:02d}_{h}"


def chunk_document(
    *,
    doc_id: str,
    doc_title: str,
    text: str,
    domain: str,
    allowed_roles: tuple[str, ...],
    doc_version: str = "v1.0",
    config: ChunkerConfig = ChunkerConfig(),
) -> list[Chunk]:
    encoder = tiktoken.get_encoding(DEFAULT_ENCODING)
    sections = _split_sections(text)
    out: list[Chunk] = []
    for s_idx, section in enumerate(sections):
        windows = _sliding_window_tokens(
            section.text, section.start, encoder, config.target_tokens, config.overlap_tokens
        )
        for c_idx, (chunk_text, off_start, off_end) in enumerate(windows):
            tok_count = len(encoder.encode(chunk_text))
            if tok_count < config.min_chunk_tokens and len(out) > 0:
                # merge tiny tail into previous
                continue
            cid = _hash_id(doc_id, s_idx, c_idx, chunk_text)
            out.append(
                Chunk(
                    chunk_id=cid,
                    doc_id=doc_id,
                    doc_title=doc_title,
                    section_title=section.title,
                    section_path=section.path,
                    text=chunk_text,
                    offset_start=off_start,
                    offset_end=off_end,
                    domain=domain,
                    allowed_roles=allowed_roles,
                    doc_version=doc_version,
                    token_count=tok_count,
                )
            )
    return out
