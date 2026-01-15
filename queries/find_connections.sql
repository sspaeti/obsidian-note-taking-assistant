-- Find Connections: Notes connected within N hops via backlinks
-- Usage: Replace $source_slug and $max_hops

WITH RECURSIVE connected(slug, hop, path) AS (
    -- First hop: direct links from source
    SELECT target_slug, 1, ARRAY[source_slug, target_slug]
    FROM links WHERE source_slug = $source_slug

    UNION

    -- Subsequent hops: follow links from connected notes
    SELECT l.target_slug, c.hop + 1, c.path || l.target_slug
    FROM connected c
    JOIN links l ON l.source_slug = c.slug
    WHERE c.hop < $max_hops
      AND NOT list_contains(c.path, l.target_slug)  -- Prevent cycles
)
SELECT DISTINCT
    n.title,
    c.slug,
    c.hop
FROM connected c
JOIN notes n ON n.slug = c.slug
WHERE c.slug != $source_slug
ORDER BY c.hop, n.title;

-- Example: Find notes 2 hops from 'data-contracts'
-- $source_slug = 'data-contracts', $max_hops = 2
