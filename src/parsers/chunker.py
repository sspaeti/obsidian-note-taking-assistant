"""Markdown-aware content chunking for embedding generation."""
import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Chunk:
    """A content chunk with context metadata."""
    content: str
    heading_context: Optional[str]
    chunk_type: str  # 'paragraph', 'code_block', 'list', 'heading'
    start_line: int
    end_line: int


def chunk_markdown(content: str, max_chunk_size: int = 512) -> List[Chunk]:
    """
    Smart chunking that respects markdown structure.

    - Keeps headings with their immediate content
    - Preserves code blocks intact (unless very large)
    - Respects paragraph boundaries
    - Maintains heading context for each chunk
    """
    if not content or not content.strip():
        return []

    chunks = []
    lines = content.split('\n')
    current_heading = None

    # First pass: identify structural blocks
    blocks = []
    current_block_lines = []
    current_block_type = 'paragraph'
    in_code_block = False
    block_start = 0

    for i, line in enumerate(lines):
        # Track code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End of code block
                current_block_lines.append(line)
                blocks.append({
                    'lines': current_block_lines,
                    'type': 'code_block',
                    'start': block_start,
                    'end': i,
                    'heading': current_heading
                })
                current_block_lines = []
                in_code_block = False
                block_start = i + 1
                current_block_type = 'paragraph'
            else:
                # Start of code block - flush current content
                if current_block_lines and any(l.strip() for l in current_block_lines):
                    blocks.append({
                        'lines': current_block_lines,
                        'type': current_block_type,
                        'start': block_start,
                        'end': i - 1,
                        'heading': current_heading
                    })
                current_block_lines = [line]
                in_code_block = True
                block_start = i
                current_block_type = 'code_block'
        elif in_code_block:
            current_block_lines.append(line)
        elif line.strip().startswith('#'):
            # Heading - flush current and update context
            if current_block_lines and any(l.strip() for l in current_block_lines):
                blocks.append({
                    'lines': current_block_lines,
                    'type': current_block_type,
                    'start': block_start,
                    'end': i - 1,
                    'heading': current_heading
                })
            current_heading = line.strip()
            # Add heading as its own small block
            blocks.append({
                'lines': [line],
                'type': 'heading',
                'start': i,
                'end': i,
                'heading': current_heading
            })
            current_block_lines = []
            block_start = i + 1
            current_block_type = 'paragraph'
        elif line.strip() == '':
            # Empty line - potential paragraph break for larger blocks
            if current_block_lines and len('\n'.join(current_block_lines)) > 100:
                blocks.append({
                    'lines': current_block_lines,
                    'type': current_block_type,
                    'start': block_start,
                    'end': i - 1,
                    'heading': current_heading
                })
                current_block_lines = []
                block_start = i + 1
            elif current_block_lines:
                current_block_lines.append(line)
        else:
            # Detect list items
            if re.match(r'^[\-\*\+]\s', line.strip()) or re.match(r'^\d+\.\s', line.strip()):
                current_block_type = 'list'
            current_block_lines.append(line)

    # Flush remaining content
    if current_block_lines and any(l.strip() for l in current_block_lines):
        blocks.append({
            'lines': current_block_lines,
            'type': current_block_type,
            'start': block_start,
            'end': len(lines) - 1,
            'heading': current_heading
        })

    # Second pass: merge small blocks, split large ones
    merged_content = []
    merged_heading = None
    merged_start = 0
    merged_end = 0

    for block in blocks:
        if block['type'] == 'heading':
            # Headings don't get chunked separately, they provide context
            continue

        block_text = '\n'.join(block['lines']).strip()
        if not block_text:
            continue

        if len(block_text) > max_chunk_size * 2:
            # Very large block - flush merged first
            if merged_content:
                chunks.append(Chunk(
                    content='\n'.join(merged_content).strip(),
                    heading_context=merged_heading,
                    chunk_type='paragraph',
                    start_line=merged_start,
                    end_line=merged_end
                ))
                merged_content = []

            # Split large block by sentences/paragraphs
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', block_text)
            current_chunk_parts = []
            chunk_len = 0

            for sentence in sentences:
                if chunk_len + len(sentence) > max_chunk_size and current_chunk_parts:
                    chunks.append(Chunk(
                        content=' '.join(current_chunk_parts).strip(),
                        heading_context=block['heading'],
                        chunk_type=block['type'],
                        start_line=block['start'],
                        end_line=block['end']
                    ))
                    current_chunk_parts = [sentence]
                    chunk_len = len(sentence)
                else:
                    current_chunk_parts.append(sentence)
                    chunk_len += len(sentence)

            if current_chunk_parts:
                chunks.append(Chunk(
                    content=' '.join(current_chunk_parts).strip(),
                    heading_context=block['heading'],
                    chunk_type=block['type'],
                    start_line=block['start'],
                    end_line=block['end']
                ))
        elif len('\n'.join(merged_content)) + len(block_text) < max_chunk_size:
            # Merge small blocks together
            if not merged_content:
                merged_start = block['start']
                merged_heading = block['heading']
            merged_content.append(block_text)
            merged_end = block['end']
        else:
            # Flush merged and start new
            if merged_content:
                chunks.append(Chunk(
                    content='\n'.join(merged_content).strip(),
                    heading_context=merged_heading,
                    chunk_type='paragraph',
                    start_line=merged_start,
                    end_line=merged_end
                ))
            merged_content = [block_text]
            merged_heading = block['heading']
            merged_start = block['start']
            merged_end = block['end']

    # Final flush
    if merged_content:
        chunks.append(Chunk(
            content='\n'.join(merged_content).strip(),
            heading_context=merged_heading,
            chunk_type='paragraph',
            start_line=merged_start,
            end_line=merged_end
        ))

    return chunks
