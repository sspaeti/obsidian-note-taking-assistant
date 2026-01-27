"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listNotes,
  searchNotesByTitle,
  getBacklinks,
  getForwardLinks,
  getConnections,
  getSharedTags,
  semanticSearch,
  findHiddenConnections,
  Note,
  SearchResult,
  Connection,
} from "../lib/motherduck";

type Tab = "browse" | "semantic" | "hidden";

// Base URL for the public second brain
const BRAIN_BASE_URL = "https://www.ssp.sh/brain";

// Generate public URL from slug
// Extract the note name (last part of path) and replace spaces with dashes
function getBrainUrl(slug: string): string {
  const noteName = slug.split("/").pop() || slug;
  const urlSlug = noteName.replace(/\s+/g, "-").toLowerCase();
  return `${BRAIN_BASE_URL}/${urlSlug}`;
}

// External link icon component
function ExternalLinkIcon({ className = "w-3 h-3" }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
      />
    </svg>
  );
}

// Clickable note link component
function NoteLink({
  slug,
  title,
  className = "",
}: {
  slug: string;
  title: string;
  className?: string;
}) {
  return (
    <a
      href={getBrainUrl(slug)}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1 hover:underline ${className}`}
      onClick={(e) => e.stopPropagation()}
    >
      {title}
      <ExternalLinkIcon className="w-3 h-3 opacity-50" />
    </a>
  );
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("browse");
  const [notes, setNotes] = useState<Note[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNote, setSelectedNote] = useState<Note | null>(null);
  const [backlinks, setBacklinks] = useState<Note[]>([]);
  const [forwardLinks, setForwardLinks] = useState<Note[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [sharedTags, setSharedTags] = useState<
    { slug: string; title: string; shared_tags: string[] }[]
  >([]);
  const [semanticQuery, setSemanticQuery] = useState("");
  const [semanticResults, setSemanticResults] = useState<SearchResult[]>([]);
  const [hiddenResults, setHiddenResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load notes on mount
  useEffect(() => {
    loadNotes();
  }, []);

  const loadNotes = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listNotes();
      setNotes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notes");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      loadNotes();
      return;
    }
    setLoading(true);
    try {
      const data = await searchNotesByTitle(query);
      setNotes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const selectNote = useCallback(async (note: Note) => {
    setSelectedNote(note);
    setLoading(true);
    try {
      const [bl, fl, conn, tags] = await Promise.all([
        getBacklinks(note.slug),
        getForwardLinks(note.slug),
        getConnections(note.slug, 2),
        getSharedTags(note.slug, 2),
      ]);
      setBacklinks(bl);
      setForwardLinks(fl);
      setConnections(conn);
      setSharedTags(tags);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load note data");
    } finally {
      setLoading(false);
    }
  }, []);

  const getEmbedding = async (text: string): Promise<number[]> => {
    const res = await fetch("/api/embed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || "Failed to get embedding");
    }
    const data = await res.json();
    return data.embedding;
  };

  const handleSemanticSearch = async () => {
    if (!semanticQuery.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const embedding = await getEmbedding(semanticQuery);
      const results = await semanticSearch(embedding, 10);
      setSemanticResults(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Semantic search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleHiddenConnections = async () => {
    if (!selectedNote) {
      setError("Please select a note first in the Browse tab");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // Use the note's title as the query for finding similar content
      const embedding = await getEmbedding(selectedNote.title);
      const results = await findHiddenConnections(
        selectedNote.slug,
        embedding,
        10
      );
      setHiddenResults(results);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Hidden connections search failed"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            Second Brain RAG
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Query your knowledge graph with semantic search
          </p>
        </div>
      </header>

      <nav className="border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex gap-4">
            {(["browse", "semantic", "hidden"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`py-3 px-4 text-sm font-medium border-b-2 transition-colors ${
                  tab === t
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                }`}
              >
                {t === "browse" && "Browse & Links"}
                {t === "semantic" && "Semantic Search"}
                {t === "hidden" && "Hidden Connections"}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-4 py-6">
        {error && (
          <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded-lg text-red-700 dark:text-red-300 text-sm">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-2 underline hover:no-underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {tab === "browse" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Note List */}
            <div className="space-y-4">
              <div>
                <input
                  type="text"
                  placeholder="Search notes by title..."
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  className="w-full px-4 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden">
                <div className="px-4 py-2 bg-zinc-50 dark:bg-zinc-700/50 border-b border-zinc-200 dark:border-zinc-700">
                  <h2 className="font-medium text-zinc-700 dark:text-zinc-300">
                    Notes ({notes.length})
                  </h2>
                </div>
                <div className="divide-y divide-zinc-100 dark:divide-zinc-700 max-h-[600px] overflow-y-auto">
                  {loading && notes.length === 0 ? (
                    <div className="p-4 text-zinc-500">Loading...</div>
                  ) : notes.length === 0 ? (
                    <div className="p-4 text-zinc-500">No notes found</div>
                  ) : (
                    notes.map((note) => (
                      <button
                        key={note.note_id}
                        onClick={() => selectNote(note)}
                        className={`w-full text-left px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-700/50 transition-colors ${
                          selectedNote?.note_id === note.note_id
                            ? "bg-blue-50 dark:bg-blue-900/20"
                            : ""
                        }`}
                      >
                        <div className="font-medium text-zinc-900 dark:text-zinc-100">
                          <NoteLink
                            slug={note.slug}
                            title={note.title}
                            className="text-zinc-900 dark:text-zinc-100"
                          />
                        </div>
                        {note.tags && note.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {note.tags.slice(0, 3).map((tag) => (
                              <span
                                key={tag}
                                className="text-xs px-2 py-0.5 bg-zinc-100 dark:bg-zinc-700 rounded text-zinc-600 dark:text-zinc-400"
                              >
                                {tag}
                              </span>
                            ))}
                            {note.tags.length > 3 && (
                              <span className="text-xs text-zinc-400">
                                +{note.tags.length - 3}
                              </span>
                            )}
                          </div>
                        )}
                      </button>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Note Details */}
            <div className="space-y-4">
              {selectedNote ? (
                <>
                  <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4">
                    <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
                      <NoteLink
                        slug={selectedNote.slug}
                        title={selectedNote.title}
                        className="text-zinc-900 dark:text-zinc-100"
                      />
                    </h2>
                    <p className="text-sm text-zinc-500 mt-1">
                      {selectedNote.word_count} words
                    </p>
                    {selectedNote.tags && selectedNote.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {selectedNote.tags.map((tag) => (
                          <span
                            key={tag}
                            className="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900/30 rounded text-blue-700 dark:text-blue-300"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Backlinks */}
                  <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700">
                    <div className="px-4 py-2 bg-zinc-50 dark:bg-zinc-700/50 border-b border-zinc-200 dark:border-zinc-700">
                      <h3 className="font-medium text-zinc-700 dark:text-zinc-300">
                        Backlinks ({backlinks.length})
                      </h3>
                    </div>
                    <div className="p-4">
                      {backlinks.length === 0 ? (
                        <p className="text-sm text-zinc-500">No backlinks</p>
                      ) : (
                        <ul className="space-y-1">
                          {backlinks.map((bl) => (
                            <li key={bl.note_id}>
                              <NoteLink
                                slug={bl.slug}
                                title={bl.title}
                                className="text-sm text-blue-600 dark:text-blue-400"
                              />
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  {/* Forward Links */}
                  <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700">
                    <div className="px-4 py-2 bg-zinc-50 dark:bg-zinc-700/50 border-b border-zinc-200 dark:border-zinc-700">
                      <h3 className="font-medium text-zinc-700 dark:text-zinc-300">
                        Links To ({forwardLinks.length})
                      </h3>
                    </div>
                    <div className="p-4">
                      {forwardLinks.length === 0 ? (
                        <p className="text-sm text-zinc-500">No outgoing links</p>
                      ) : (
                        <ul className="space-y-1">
                          {forwardLinks.map((fl) => (
                            <li key={fl.note_id}>
                              <NoteLink
                                slug={fl.slug}
                                title={fl.title}
                                className="text-sm text-blue-600 dark:text-blue-400"
                              />
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  {/* Connections (N hops) */}
                  <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700">
                    <div className="px-4 py-2 bg-zinc-50 dark:bg-zinc-700/50 border-b border-zinc-200 dark:border-zinc-700">
                      <h3 className="font-medium text-zinc-700 dark:text-zinc-300">
                        Connections (2 hops) ({connections.length})
                      </h3>
                    </div>
                    <div className="p-4 max-h-48 overflow-y-auto">
                      {connections.length === 0 ? (
                        <p className="text-sm text-zinc-500">No connections</p>
                      ) : (
                        <ul className="space-y-2">
                          {connections.map((conn) => (
                            <li
                              key={conn.slug}
                              className="text-sm flex items-center gap-2"
                            >
                              <span className="text-xs px-1.5 py-0.5 bg-zinc-200 dark:bg-zinc-700 rounded">
                                {conn.depth}
                              </span>
                              <NoteLink
                                slug={conn.slug}
                                title={conn.title}
                                className="text-zinc-900 dark:text-zinc-100"
                              />
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  {/* Shared Tags */}
                  <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700">
                    <div className="px-4 py-2 bg-zinc-50 dark:bg-zinc-700/50 border-b border-zinc-200 dark:border-zinc-700">
                      <h3 className="font-medium text-zinc-700 dark:text-zinc-300">
                        Shared Tags ({sharedTags.length})
                      </h3>
                    </div>
                    <div className="p-4 max-h-48 overflow-y-auto">
                      {sharedTags.length === 0 ? (
                        <p className="text-sm text-zinc-500">
                          No notes sharing 2+ tags
                        </p>
                      ) : (
                        <ul className="space-y-2">
                          {sharedTags.map((st) => (
                            <li key={st.slug} className="text-sm">
                              <NoteLink
                                slug={st.slug}
                                title={st.title}
                                className="text-zinc-900 dark:text-zinc-100"
                              />
                              <div className="flex flex-wrap gap-1 mt-0.5">
                                {st.shared_tags.map((tag) => (
                                  <span
                                    key={tag}
                                    className="text-xs px-1.5 py-0.5 bg-green-100 dark:bg-green-900/30 rounded text-green-700 dark:text-green-300"
                                  >
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 p-8 text-center text-zinc-500">
                  Select a note to see its connections
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "semantic" && (
          <div className="space-y-4 max-w-2xl">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Search by meaning... e.g. 'data modeling best practices'"
                value={semanticQuery}
                onChange={(e) => setSemanticQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSemanticSearch()}
                className="flex-1 px-4 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <button
                onClick={handleSemanticSearch}
                disabled={loading || !semanticQuery.trim()}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Searching..." : "Search"}
              </button>
            </div>

            <p className="text-sm text-zinc-500">
              Uses BGE-M3 embeddings to find semantically similar content, even
              if the exact words don&apos;t match.
            </p>

            {semanticResults.length > 0 && (
              <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700">
                <div className="px-4 py-2 bg-zinc-50 dark:bg-zinc-700/50 border-b border-zinc-200 dark:border-zinc-700">
                  <h3 className="font-medium text-zinc-700 dark:text-zinc-300">
                    Results ({semanticResults.length})
                  </h3>
                </div>
                <div className="divide-y divide-zinc-100 dark:divide-zinc-700">
                  {semanticResults.map((result, idx) => (
                    <div key={idx} className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium text-zinc-900 dark:text-zinc-100">
                          <NoteLink
                            slug={result.slug}
                            title={result.title}
                            className="text-zinc-900 dark:text-zinc-100"
                          />
                        </h4>
                        <span className="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900/30 rounded text-blue-700 dark:text-blue-300">
                          {(result.similarity * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="text-sm text-zinc-600 dark:text-zinc-400 line-clamp-3">
                        {result.chunk_content}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === "hidden" && (
          <div className="space-y-4 max-w-2xl">
            <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4">
              <h3 className="font-medium text-zinc-900 dark:text-zinc-100 mb-2">
                Find Hidden Connections
              </h3>
              <p className="text-sm text-zinc-500 mb-4">
                Discover notes that are semantically similar to your selected
                note but aren&apos;t directly linked. These are potential
                connections you might have missed!
              </p>

              {selectedNote ? (
                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <p className="text-sm text-zinc-500">Selected note:</p>
                    <p className="font-medium text-zinc-900 dark:text-zinc-100">
                      <NoteLink
                        slug={selectedNote.slug}
                        title={selectedNote.title}
                        className="text-zinc-900 dark:text-zinc-100"
                      />
                    </p>
                  </div>
                  <button
                    onClick={handleHiddenConnections}
                    disabled={loading}
                    className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? "Searching..." : "Find Hidden"}
                  </button>
                </div>
              ) : (
                <p className="text-sm text-amber-600 dark:text-amber-400">
                  Go to Browse tab and select a note first
                </p>
              )}
            </div>

            {hiddenResults.length > 0 && (
              <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700">
                <div className="px-4 py-2 bg-zinc-50 dark:bg-zinc-700/50 border-b border-zinc-200 dark:border-zinc-700">
                  <h3 className="font-medium text-zinc-700 dark:text-zinc-300">
                    Hidden Connections ({hiddenResults.length})
                  </h3>
                </div>
                <div className="divide-y divide-zinc-100 dark:divide-zinc-700">
                  {hiddenResults.map((result, idx) => (
                    <div key={idx} className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium text-zinc-900 dark:text-zinc-100">
                          <NoteLink
                            slug={result.slug}
                            title={result.title}
                            className="text-zinc-900 dark:text-zinc-100"
                          />
                        </h4>
                        <span className="text-xs px-2 py-1 bg-purple-100 dark:bg-purple-900/30 rounded text-purple-700 dark:text-purple-300">
                          {(result.similarity * 100).toFixed(1)}% similar
                        </span>
                      </div>
                      <p className="text-sm text-zinc-600 dark:text-zinc-400 line-clamp-3">
                        {result.chunk_content}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="border-t border-zinc-200 dark:border-zinc-700 mt-8">
        <div className="max-w-6xl mx-auto px-4 py-4 text-center text-sm text-zinc-500">
          Powered by MotherDuck + DuckDB WASM + BGE-M3 embeddings |{" "}
          <a
            href={BRAIN_BASE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-500 hover:underline"
          >
            Browse full Second Brain
          </a>
        </div>
      </footer>
    </div>
  );
}
