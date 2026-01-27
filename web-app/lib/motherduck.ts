// Types for our data
export interface Note {
  note_id: number;
  slug: string;
  title: string;
  content: string;
  tags: string[];
  word_count: number;
}

export interface Link {
  source_slug: string;
  target_slug: string;
  link_text: string;
}

export interface SearchResult {
  note_id: number;
  slug: string;
  title: string;
  chunk_content: string;
  similarity: number;
}

export interface Connection {
  slug: string;
  title: string;
  depth: number;
  path: string[];
}


// eslint-disable-next-line @typescript-eslint/no-explicit-any
type MDConnectionType = any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type MDConnectionClass = any;

// Singleton connection
let connection: MDConnectionType | null = null;
let MDConnectionCls: MDConnectionClass | null = null;

async function getMDConnection(): Promise<MDConnectionClass> {
  if (!MDConnectionCls) {
    const module = await import("@motherduck/wasm-client");
    MDConnectionCls = module.MDConnection;
  }
  return MDConnectionCls;
}

export async function getConnection(): Promise<MDConnectionType> {
  if (connection) return connection;

  const token = process.env.NEXT_PUBLIC_MOTHERDUCK_TOKEN;
  if (!token) {
    throw new Error("NEXT_PUBLIC_MOTHERDUCK_TOKEN is not set");
  }

  const MD = await getMDConnection();
  connection = await MD.create({
    mdToken: token,
  });

  // Use the obsidian_rag database
  await connection.evaluateQuery("USE obsidian_rag;");

  return connection;
}

// List all notes
export async function listNotes(limit = 50): Promise<Note[]> {
  const conn = await getConnection();
  const result = await conn.evaluateQuery(`
    SELECT note_id, slug, title, content, tags, word_count
    FROM notes
    ORDER BY title
    LIMIT ${limit}
  `);
  return result.data.toRows() as unknown as Note[];
}

// Search notes by title
export async function searchNotesByTitle(query: string): Promise<Note[]> {
  const conn = await getConnection();
  const escapedQuery = query.replace(/'/g, "''");
  const result = await conn.evaluateQuery(`
    SELECT note_id, slug, title, content, tags, word_count
    FROM notes
    WHERE title ILIKE '%${escapedQuery}%' OR slug ILIKE '%${escapedQuery}%'
    ORDER BY title
    LIMIT 20
  `);
  return result.data.toRows() as unknown as Note[];
}

// Get backlinks (notes that link TO a given note)
export async function getBacklinks(slug: string): Promise<Note[]> {
  const conn = await getConnection();
  const escapedSlug = slug.replace(/'/g, "''");
  const result = await conn.evaluateQuery(`
    SELECT DISTINCT n.note_id, n.slug, n.title, n.content, n.tags, n.word_count
    FROM links l
    JOIN notes n ON l.source_slug = n.slug
    WHERE l.target_slug = '${escapedSlug}'
    ORDER BY n.title
  `);
  return result.data.toRows() as unknown as Note[];
}

// Get forward links (notes that a given note links TO)
export async function getForwardLinks(slug: string): Promise<Note[]> {
  const conn = await getConnection();
  const escapedSlug = slug.replace(/'/g, "''");
  const result = await conn.evaluateQuery(`
    SELECT DISTINCT n.note_id, n.slug, n.title, n.content, n.tags, n.word_count
    FROM links l
    JOIN notes n ON l.target_slug = n.slug
    WHERE l.source_slug = '${escapedSlug}'
    ORDER BY n.title
  `);
  return result.data.toRows() as unknown as Note[];
}

// Get connections via graph traversal (N hops)
export async function getConnections(
  slug: string,
  hops = 2
): Promise<Connection[]> {
  const conn = await getConnection();
  const escapedSlug = slug.replace(/'/g, "''");

  const result = await conn.evaluateQuery(`
    WITH RECURSIVE connections AS (
      -- Base case: direct links from start note
      SELECT
        CASE WHEN l.source_slug = '${escapedSlug}' THEN l.target_slug ELSE l.source_slug END as slug,
        1 as depth,
        ['${escapedSlug}', CASE WHEN l.source_slug = '${escapedSlug}' THEN l.target_slug ELSE l.source_slug END] as path
      FROM links l
      WHERE l.source_slug = '${escapedSlug}' OR l.target_slug = '${escapedSlug}'

      UNION

      -- Recursive case: follow links from connected notes
      SELECT
        CASE WHEN l.source_slug = c.slug THEN l.target_slug ELSE l.source_slug END as slug,
        c.depth + 1 as depth,
        list_append(c.path, CASE WHEN l.source_slug = c.slug THEN l.target_slug ELSE l.source_slug END) as path
      FROM connections c
      JOIN links l ON (l.source_slug = c.slug OR l.target_slug = c.slug)
      WHERE c.depth < ${hops}
        AND NOT list_contains(c.path, CASE WHEN l.source_slug = c.slug THEN l.target_slug ELSE l.source_slug END)
    )
    SELECT DISTINCT ON (c.slug)
      c.slug,
      n.title,
      c.depth,
      c.path
    FROM connections c
    JOIN notes n ON c.slug = n.slug
    WHERE c.slug != '${escapedSlug}'
    ORDER BY c.slug, c.depth
    LIMIT 50
  `);

  return result.data.toRows() as unknown as Connection[];
}

// Get notes sharing tags via hyperedges
export async function getSharedTags(
  slug: string,
  minShared = 2
): Promise<{ slug: string; title: string; shared_tags: string[] }[]> {
  const conn = await getConnection();
  const escapedSlug = slug.replace(/'/g, "''");

  const result = await conn.evaluateQuery(`
    WITH target_tags AS (
      SELECT hm.hyperedge_id, h.edge_value as tag
      FROM hyperedge_members hm
      JOIN hyperedges h ON hm.hyperedge_id = h.hyperedge_id
      JOIN notes n ON hm.note_id = n.note_id
      WHERE n.slug = '${escapedSlug}' AND h.edge_type = 'tag'
    ),
    shared AS (
      SELECT
        n2.slug,
        n2.title,
        list(DISTINCT tt.tag ORDER BY tt.tag) as shared_tags
      FROM target_tags tt
      JOIN hyperedge_members hm2 ON tt.hyperedge_id = hm2.hyperedge_id
      JOIN notes n2 ON hm2.note_id = n2.note_id
      WHERE n2.slug != '${escapedSlug}'
      GROUP BY n2.slug, n2.title
      HAVING COUNT(DISTINCT tt.tag) >= ${minShared}
    )
    SELECT * FROM shared
    ORDER BY len(shared_tags) DESC, title
    LIMIT 20
  `);

  return result.data.toRows() as unknown as {
    slug: string;
    title: string;
    shared_tags: string[];
  }[];
}

// Semantic search using manual cosine similarity
export async function semanticSearch(
  queryEmbedding: number[],
  limit = 10
): Promise<SearchResult[]> {
  const conn = await getConnection();

  // Convert embedding to DuckDB array format
  const embeddingStr = `[${queryEmbedding.join(",")}]::FLOAT[1024]`;

  const result = await conn.evaluateQuery(`
    WITH query_vec AS (
      SELECT ${embeddingStr} as qvec
    ),
    similarities AS (
      SELECT
        c.chunk_id,
        c.note_id,
        c.content as chunk_content,
        -- Manual cosine similarity
        list_dot_product(e.embedding, q.qvec) /
        (sqrt(list_sum(list_transform(e.embedding, x -> x*x))) *
         sqrt(list_sum(list_transform(q.qvec, x -> x*x)))) as similarity
      FROM chunks c
      JOIN embeddings e ON c.chunk_id = e.chunk_id
      CROSS JOIN query_vec q
    )
    SELECT
      s.note_id,
      n.slug,
      n.title,
      s.chunk_content,
      s.similarity
    FROM similarities s
    JOIN notes n ON s.note_id = n.note_id
    ORDER BY s.similarity DESC
    LIMIT ${limit}
  `);

  return result.data.toRows() as unknown as SearchResult[];
}

// Find hidden connections (semantically similar but not linked)
export async function findHiddenConnections(
  slug: string,
  queryEmbedding: number[],
  limit = 10
): Promise<SearchResult[]> {
  const conn = await getConnection();
  const escapedSlug = slug.replace(/'/g, "''");
  const embeddingStr = `[${queryEmbedding.join(",")}]::FLOAT[1024]`;

  const result = await conn.evaluateQuery(`
    WITH query_vec AS (
      SELECT ${embeddingStr} as qvec
    ),
    linked_notes AS (
      SELECT DISTINCT target_slug as slug FROM links WHERE source_slug = '${escapedSlug}'
      UNION
      SELECT DISTINCT source_slug as slug FROM links WHERE target_slug = '${escapedSlug}'
    ),
    similarities AS (
      SELECT
        c.chunk_id,
        c.note_id,
        c.content as chunk_content,
        list_dot_product(e.embedding, q.qvec) /
        (sqrt(list_sum(list_transform(e.embedding, x -> x*x))) *
         sqrt(list_sum(list_transform(q.qvec, x -> x*x)))) as similarity
      FROM chunks c
      JOIN embeddings e ON c.chunk_id = e.chunk_id
      JOIN notes n ON c.note_id = n.note_id
      CROSS JOIN query_vec q
      WHERE n.slug != '${escapedSlug}'
        AND n.slug NOT IN (SELECT slug FROM linked_notes)
    )
    SELECT
      s.note_id,
      n.slug,
      n.title,
      s.chunk_content,
      s.similarity
    FROM similarities s
    JOIN notes n ON s.note_id = n.note_id
    ORDER BY s.similarity DESC
    LIMIT ${limit}
  `);

  return result.data.toRows() as unknown as SearchResult[];
}
