"""Parse Obsidian markdown files with frontmatter extraction."""
import re
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class ParsedNote:
    """Structured representation of a parsed Obsidian note."""
    file_path: str
    slug: str
    title: str
    content: str
    frontmatter: Dict[str, Any]
    tags: List[str]
    aliases: List[str]
    created_date: Optional[datetime]
    modified_date: Optional[datetime]


def extract_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Extract YAML frontmatter and return (metadata, remaining_content)."""
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n?'
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if match:
        try:
            metadata = yaml.safe_load(match.group(1)) or {}
            remaining = content[match.end():]
            return metadata, remaining
        except yaml.YAMLError:
            return {}, content
    return {}, content


def extract_title(content: str, file_path: Path) -> str:
    """Extract title from first H1 heading or filename."""
    h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()
    return file_path.stem


def path_to_slug(file_path: Path, vault_root: Path) -> str:
    """Convert file path to URL-friendly slug."""
    relative = file_path.relative_to(vault_root)
    # Remove .md extension and create slug
    slug = str(relative.with_suffix('')).lower()
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^\w\-/]', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


def extract_tags(content: str, frontmatter: Dict) -> List[str]:
    """Extract tags from frontmatter and inline #tags."""
    tags = set()

    # From frontmatter
    if 'tags' in frontmatter:
        fm_tags = frontmatter['tags']
        if isinstance(fm_tags, list):
            tags.update(str(t) for t in fm_tags)
        elif isinstance(fm_tags, str):
            tags.add(fm_tags)

    # Inline tags (excluding code blocks and URLs)
    # Match #tag but not inside backticks or URLs
    inline_tags = re.findall(r'(?<![`\w/])#([\w/\-]+)(?![`\w])', content)
    tags.update(inline_tags)

    return list(tags)


def parse_date(value: Any) -> Optional[datetime]:
    """Parse various date formats to datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Handle [[YYYY-MM-DD]] format
        match = re.match(r'\[\[(\d{4}-\d{2}-\d{2})\]\]', value)
        if match:
            value = match.group(1)
        try:
            return datetime.strptime(value[:10], '%Y-%m-%d')
        except (ValueError, TypeError):
            return None
    return None


def extract_created_date(content: str, frontmatter: Dict) -> Optional[datetime]:
    """Extract created date from 'Created [[YYYY-MM-DD]]' pattern or frontmatter."""
    # Check frontmatter first
    if 'created' in frontmatter:
        return parse_date(frontmatter['created'])

    # Look for Created [[YYYY-MM-DD]] pattern in footer
    created_match = re.search(r'Created:?\s*\[\[(\d{4}-\d{2}-\d{2})\]\]', content)
    if created_match:
        return datetime.strptime(created_match.group(1), '%Y-%m-%d')

    return None


def parse_note(file_path: Path, vault_root: Path) -> ParsedNote:
    """Parse a markdown note into structured data."""
    content = file_path.read_text(encoding='utf-8', errors='replace')
    frontmatter, body = extract_frontmatter(content)

    # Get aliases from frontmatter
    aliases = frontmatter.get('aliases', [])
    if isinstance(aliases, str):
        aliases = [aliases]
    elif not isinstance(aliases, list):
        aliases = []

    return ParsedNote(
        file_path=str(file_path),
        slug=path_to_slug(file_path, vault_root),
        title=extract_title(body, file_path),
        content=body,
        frontmatter=frontmatter,
        tags=extract_tags(content, frontmatter),
        aliases=[str(a) for a in aliases],
        created_date=extract_created_date(content, frontmatter),
        modified_date=datetime.fromtimestamp(file_path.stat().st_mtime)
    )
