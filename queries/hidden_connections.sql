-- Hidden Connections: Semantically similar notes NOT directly linked
-- These represent potentially valuable non-obvious connections
-- Usage: Replace $query_embedding, $seed_slug, and $limit

WITH semantic_similar AS (
    -- Find semantically similar notes
    SELECT DISTINCT
        n.slug,
        n.title,
        c.content,
        MIN(1 - array_cosine_distance(e.embedding, $query_embedding::FLOAT[384])) as similarity
    FROM embeddings e
    JOIN chunks c ON c.chunk_id = e.chunk_id
    JOIN notes n ON n.note_id = c.note_id
    GROUP BY n.slug, n.title, c.content
    HAVING MIN(array_cosine_distance(e.embedding, $query_embedding::FLOAT[384])) < 0.6
),
direct_links AS (
    -- Notes directly linked to or from seed
    SELECT DISTINCT target_slug as slug FROM links WHERE source_slug = $seed_slug
    UNION
    SELECT DISTINCT source_slug as slug FROM links WHERE target_slug = $seed_slug
)
SELECT
    ss.title,
    ss.slug,
    ss.content,
    ss.similarity
FROM semantic_similar ss
LEFT JOIN direct_links dl ON ss.slug = dl.slug
WHERE dl.slug IS NULL  -- Exclude directly linked notes
  AND ss.slug != $seed_slug
ORDER BY ss.similarity DESC
LIMIT $limit;
