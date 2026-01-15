-- Semantic Search: Find notes by embedding similarity
-- Usage: Replace $query_embedding with actual embedding vector and $limit with number
-- Note: This query is for reference; use query.py for actual searches

SELECT DISTINCT
    n.title,
    n.slug,
    n.file_path,
    c.content,
    c.heading_context,
    1 - array_cosine_distance(e.embedding, $query_embedding::FLOAT[384]) as similarity
FROM embeddings e
JOIN chunks c ON c.chunk_id = e.chunk_id
JOIN notes n ON n.note_id = c.note_id
ORDER BY similarity DESC
LIMIT $limit;

-- With tag filter:
-- WHERE list_contains(n.tags, 'data-engineering')
