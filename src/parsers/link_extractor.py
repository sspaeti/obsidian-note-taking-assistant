"""Extract Obsidian wikilinks from markdown content."""
import re
from dataclasses import dataclass
from typing import List


@dataclass
class WikiLink:
    """Represents a single wikilink connection."""
    source_slug: str
    target_slug: str
    link_text: str
    link_type: str = 'wikilink'


def normalize_slug(target: str) -> str:
    """Normalize a wikilink target to a URL-friendly slug."""
    # Remove heading anchors (e.g., Note#Section -> Note)
    target = target.split('#')[0]
    # Lowercase and strip
    slug = target.lower().strip()
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^\w\-]', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


def extract_wikilinks(content: str, source_slug: str) -> List[WikiLink]:
    """
    Extract all [[wikilinks]] from markdown content.

    Handles formats:
    - [[target]]
    - [[target|display text]]
    - [[target#heading]]
    - [[target#heading|display]]

    Also extracts Origin and References metadata links.
    """
    links = []
    seen = set()  # Track unique (source, target, text) tuples

    # Pattern for [[target]] and [[target|display text]]
    # Handles nested brackets and special characters
    wikilink_pattern = r'\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]'

    for match in re.finditer(wikilink_pattern, content):
        target = match.group(1).strip()
        display_text = (match.group(2) or target).strip()

        # Skip empty targets
        if not target:
            continue

        # Skip pure date links like [[2024-01-01]] (they're just date references)
        if re.match(r'^\d{4}-\d{2}-\d{2}$', target):
            continue

        # Skip embedded content links (![[image.png]])
        if match.start() > 0 and content[match.start() - 1] == '!':
            continue

        target_slug = normalize_slug(target)
        key = (source_slug, target_slug, display_text)

        if key not in seen and target_slug:
            seen.add(key)
            links.append(WikiLink(
                source_slug=source_slug,
                target_slug=target_slug,
                link_text=display_text,
                link_type='wikilink'
            ))

    # Extract Origin links (special metadata at end of notes)
    origin_pattern = r'Origin:?\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]'
    for match in re.finditer(origin_pattern, content):
        target = match.group(1).strip()
        target_slug = normalize_slug(target)
        key = (source_slug, target_slug, target)

        if key not in seen and target_slug:
            seen.add(key)
            links.append(WikiLink(
                source_slug=source_slug,
                target_slug=target_slug,
                link_text=target,
                link_type='origin'
            ))

    # Extract References links (can be comma-separated)
    ref_pattern = r'References:?\s*(.+?)(?:\n|$)'
    for match in re.finditer(ref_pattern, content):
        refs_text = match.group(1)
        for ref_match in re.finditer(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', refs_text):
            target = ref_match.group(1).strip()
            target_slug = normalize_slug(target)
            key = (source_slug, target_slug, target)

            if key not in seen and target_slug:
                seen.add(key)
                links.append(WikiLink(
                    source_slug=source_slug,
                    target_slug=target_slug,
                    link_text=target,
                    link_type='reference'
                ))

    return links
