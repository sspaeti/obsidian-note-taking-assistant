-- Useful DuckDB queries for exploring the Second Brain

-- Count records in all tables
SELECT 'notes' as table_name, COUNT(*) as count FROM notes
UNION ALL
SELECT 'links', COUNT(*) FROM links
UNION ALL
SELECT 'chunks', COUNT(*) FROM chunks
UNION ALL
SELECT 'embeddings', COUNT(*) FROM embeddings;

-- Most connected notes (hub notes)
SELECT
    n.title,
    n.slug,
    COUNT(DISTINCT lo.target_slug) as outgoing_links,
    COUNT(DISTINCT li.source_slug) as incoming_links,
    COUNT(DISTINCT lo.target_slug) + COUNT(DISTINCT li.source_slug) as total_connections
FROM notes n
LEFT JOIN links lo ON lo.source_slug = n.slug
LEFT JOIN links li ON li.target_slug = n.slug
GROUP BY n.title, n.slug
ORDER BY total_connections DESC
LIMIT 20;

-- Most referenced notes (most backlinks)
SELECT
    l.target_slug,
    n.title,
    COUNT(*) as backlink_count
FROM links l
LEFT JOIN notes n ON n.slug = l.target_slug
GROUP BY l.target_slug, n.title
ORDER BY backlink_count DESC
LIMIT 20;

-- Notes with most outgoing links
SELECT
    n.title,
    n.slug,
    COUNT(*) as link_count
FROM notes n
JOIN links l ON l.source_slug = n.slug
GROUP BY n.title, n.slug
ORDER BY link_count DESC
LIMIT 20;

-- Find orphan notes (no incoming or outgoing links)
SELECT n.title, n.slug, n.file_path
FROM notes n
LEFT JOIN links lo ON lo.source_slug = n.slug
LEFT JOIN links li ON li.target_slug = n.slug
WHERE lo.link_id IS NULL AND li.link_id IS NULL
LIMIT 50;

-- Search by title (case-insensitive)
SELECT title, slug, file_path
FROM notes
WHERE lower(title) LIKE '%semantic%'
ORDER BY title;

-- Search by tag
SELECT title, slug, tags
FROM notes
WHERE list_contains(tags, 'data-engineering')
OR list_contains(tags, 'publish')
LIMIT 20;

-- Notes created in a date range
SELECT title, slug, created_date
FROM notes
WHERE created_date BETWEEN '2024-01-01' AND '2024-12-31'
ORDER BY created_date DESC;

-- Average chunks per note
SELECT
    AVG(chunk_count) as avg_chunks,
    MIN(chunk_count) as min_chunks,
    MAX(chunk_count) as max_chunks
FROM (
    SELECT note_id, COUNT(*) as chunk_count
    FROM chunks
    GROUP BY note_id
);

-- Links that point to non-existent notes (broken links)
SELECT DISTINCT l.target_slug, l.source_slug, l.link_text
FROM links l
LEFT JOIN notes n ON n.slug = l.target_slug
WHERE n.note_id IS NULL
LIMIT 50;
