-- Find Backlinks: Notes that link TO a given note
-- Usage: Replace $target_slug with the note slug you want to find backlinks for

SELECT DISTINCT
    n.title,
    n.slug,
    l.link_text,
    l.link_type
FROM links l
JOIN notes n ON n.slug = l.source_slug
WHERE l.target_slug = $target_slug
ORDER BY n.title;

-- Example: Find all notes linking to 'semantic-layer'
-- WHERE l.target_slug = 'semantic-layer'
