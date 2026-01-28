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
    <div className="min-h-screen bg-[var(--bg-outer)]">
      <header className="border-b border-[var(--border)] bg-[var(--bg-header)]">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            Second Brain RAG
          </h1>
          <p className="text-sm text-[var(--text-secondary)]">
            Query your knowledge graph with semantic search
          </p>
        </div>
      </header>

      <nav className="border-b border-[var(--border)] bg-[var(--bg-header)]">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex gap-4">
            {(["browse", "semantic", "hidden"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`py-3 px-4 text-sm font-medium border-b-2 transition-colors ${
                  tab === t
                    ? "border-[var(--accent)] text-[var(--accent)]"
                    : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
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
          <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/30 border border-red-300 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300 text-sm">
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
                  className="w-full px-4 py-2 border border-[var(--border)] rounded-lg bg-[var(--bg-inner)] text-[var(--text-primary)] focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
                />
              </div>

              <div className="bg-[var(--bg-inner)] rounded-lg border border-[var(--border)] overflow-hidden">
                <div className="px-4 py-2 bg-[var(--tag-bg)] border-b border-[var(--border)]">
                  <h2 className="font-medium text-[var(--text-secondary)]">
                    Notes ({notes.length})
                  </h2>
                  <p className="text-xs text-[var(--text-secondary)] opacity-70">
                    Click row to select · Click title to open in Second Brain
                  </p>
                </div>
                <div className="divide-y divide-[var(--border-subtle)] max-h-[600px] overflow-y-auto">
                  {loading && notes.length === 0 ? (
                    <div className="p-4 text-[var(--text-secondary)]">Loading...</div>
                  ) : notes.length === 0 ? (
                    <div className="p-4 text-[var(--text-secondary)]">No notes found</div>
                  ) : (
                    notes.map((note) => (
                      <button
                        key={note.note_id}
                        onClick={() => selectNote(note)}
                        className={`w-full text-left px-4 py-3 hover:bg-[var(--tag-bg)] transition-colors ${
                          selectedNote?.note_id === note.note_id
                            ? "bg-[var(--selected-bg)]"
                            : ""
                        }`}
                      >
                        <div className="font-medium text-[var(--text-primary)]">
                          <NoteLink
                            slug={note.slug}
                            title={note.title}
                            className="text-[var(--text-primary)]"
                          />
                        </div>
                        {note.tags && note.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {note.tags.slice(0, 3).map((tag) => (
                              <span
                                key={tag}
                                className="text-xs px-2 py-0.5 bg-[var(--tag-bg)] rounded text-[var(--tag-text)]"
                              >
                                {tag}
                              </span>
                            ))}
                            {note.tags.length > 3 && (
                              <span className="text-xs text-[var(--text-secondary)]">
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
                  <div className="bg-[var(--bg-inner)] rounded-lg border border-[var(--border)] p-4">
                    <h2 className="text-xl font-bold text-[var(--text-primary)]">
                      <NoteLink
                        slug={selectedNote.slug}
                        title={selectedNote.title}
                        className="text-[var(--text-primary)]"
                      />
                    </h2>
                    <p className="text-sm text-[var(--text-secondary)] mt-1">
                      {selectedNote.word_count} words
                    </p>
                    {selectedNote.tags && selectedNote.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {selectedNote.tags.map((tag) => (
                          <span
                            key={tag}
                            className="text-xs px-2 py-1 bg-[var(--selected-bg)] rounded text-[var(--accent)]"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                    <button
                      onClick={() => {
                        setTab("hidden");
                        handleHiddenConnections();
                      }}
                      className="mt-3 text-sm px-3 py-1.5 bg-[var(--purple)] text-white rounded hover:opacity-90"
                    >
                      Find Hidden Connections →
                    </button>
                  </div>

                  {/* Backlinks */}
                  <div className="bg-[var(--bg-inner)] rounded-lg border border-[var(--border)]">
                    <div className="px-4 py-2 bg-[var(--tag-bg)] border-b border-[var(--border)]">
                      <h3 className="font-medium text-[var(--text-secondary)]">
                        Backlinks ({backlinks.length})
                      </h3>
                    </div>
                    <div className="p-4">
                      {backlinks.length === 0 ? (
                        <p className="text-sm text-[var(--text-secondary)]">No backlinks</p>
                      ) : (
                        <ul className="space-y-1">
                          {backlinks.map((bl) => (
                            <li key={bl.note_id}>
                              <NoteLink
                                slug={bl.slug}
                                title={bl.title}
                                className="text-sm text-[var(--link)] hover:text-[var(--link-hover)]"
                              />
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  {/* Forward Links */}
                  <div className="bg-[var(--bg-inner)] rounded-lg border border-[var(--border)]">
                    <div className="px-4 py-2 bg-[var(--tag-bg)] border-b border-[var(--border)]">
                      <h3 className="font-medium text-[var(--text-secondary)]">
                        Links To ({forwardLinks.length})
                      </h3>
                    </div>
                    <div className="p-4">
                      {forwardLinks.length === 0 ? (
                        <p className="text-sm text-[var(--text-secondary)]">No outgoing links</p>
                      ) : (
                        <ul className="space-y-1">
                          {forwardLinks.map((fl) => (
                            <li key={fl.note_id}>
                              <NoteLink
                                slug={fl.slug}
                                title={fl.title}
                                className="text-sm text-[var(--link)] hover:text-[var(--link-hover)]"
                              />
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  {/* Connections (N hops) */}
                  <div className="bg-[var(--bg-inner)] rounded-lg border border-[var(--border)]">
                    <div className="px-4 py-2 bg-[var(--tag-bg)] border-b border-[var(--border)]">
                      <h3 className="font-medium text-[var(--text-secondary)]">
                        Connections (2 hops) ({connections.length})
                      </h3>
                    </div>
                    <div className="p-4 max-h-48 overflow-y-auto">
                      {connections.length === 0 ? (
                        <p className="text-sm text-[var(--text-secondary)]">No connections</p>
                      ) : (
                        <ul className="space-y-2">
                          {connections.map((conn) => (
                            <li
                              key={conn.slug}
                              className="text-sm flex items-center gap-2"
                            >
                              <span className="text-xs px-1.5 py-0.5 bg-[var(--tag-bg)] rounded text-[var(--text-secondary)]">
                                {conn.depth}
                              </span>
                              <NoteLink
                                slug={conn.slug}
                                title={conn.title}
                                className="text-[var(--text-primary)]"
                              />
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  {/* Shared Tags */}
                  <div className="bg-[var(--bg-inner)] rounded-lg border border-[var(--border)]">
                    <div className="px-4 py-2 bg-[var(--tag-bg)] border-b border-[var(--border)]">
                      <h3 className="font-medium text-[var(--text-secondary)]">
                        Shared Tags ({sharedTags.length})
                      </h3>
                    </div>
                    <div className="p-4 max-h-48 overflow-y-auto">
                      {sharedTags.length === 0 ? (
                        <p className="text-sm text-[var(--text-secondary)]">
                          No notes sharing 2+ tags
                        </p>
                      ) : (
                        <ul className="space-y-2">
                          {sharedTags.map((st) => (
                            <li key={st.slug} className="text-sm">
                              <NoteLink
                                slug={st.slug}
                                title={st.title}
                                className="text-[var(--text-primary)]"
                              />
                              <div className="flex flex-wrap gap-1 mt-0.5">
                                {st.shared_tags.map((tag) => (
                                  <span
                                    key={tag}
                                    className="text-xs px-1.5 py-0.5 bg-[var(--purple)]/20 rounded text-[var(--purple)]"
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
                <div className="bg-[var(--bg-inner)] rounded-lg border border-[var(--border)] p-8 text-center text-[var(--text-secondary)]">
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
                className="flex-1 px-4 py-2 border border-[var(--border)] rounded-lg bg-[var(--bg-inner)] text-[var(--text-primary)] focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
              />
              <button
                onClick={handleSemanticSearch}
                disabled={loading || !semanticQuery.trim()}
                className="px-6 py-2 bg-[var(--accent)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Searching..." : "Search"}
              </button>
            </div>

            <p className="text-sm text-[var(--text-secondary)]">
              Uses BGE-M3 embeddings to find semantically similar content, even
              if the exact words don&apos;t match.
            </p>

            {semanticResults.length > 0 && (
              <div className="bg-[var(--bg-inner)] rounded-lg border border-[var(--border)]">
                <div className="px-4 py-2 bg-[var(--tag-bg)] border-b border-[var(--border)]">
                  <h3 className="font-medium text-[var(--text-secondary)]">
                    Results ({semanticResults.length})
                  </h3>
                </div>
                <div className="divide-y divide-[var(--border-subtle)]">
                  {semanticResults.map((result, idx) => (
                    <div key={idx} className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium text-[var(--text-primary)]">
                          <NoteLink
                            slug={result.slug}
                            title={result.title}
                            className="text-[var(--text-primary)]"
                          />
                        </h4>
                        <span className="text-xs px-2 py-1 bg-[var(--selected-bg)] rounded text-[var(--accent)]">
                          {(result.similarity * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="text-sm text-[var(--text-secondary)] line-clamp-3">
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
            <div className="bg-[var(--bg-inner)] rounded-lg border border-[var(--border)] p-4">
              <h3 className="font-medium text-[var(--text-primary)] mb-2">
                Find Hidden Connections
              </h3>
              <p className="text-sm text-[var(--text-secondary)] mb-4">
                Discover notes that are semantically similar to your selected
                note but aren&apos;t directly linked. These are potential
                connections you might have missed!
              </p>

              {selectedNote ? (
                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <p className="text-sm text-[var(--text-secondary)]">Selected note:</p>
                    <p className="font-medium text-[var(--text-primary)]">
                      <NoteLink
                        slug={selectedNote.slug}
                        title={selectedNote.title}
                        className="text-[var(--text-primary)]"
                      />
                    </p>
                  </div>
                  <button
                    onClick={handleHiddenConnections}
                    disabled={loading}
                    className="px-6 py-2 bg-[var(--purple)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
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
              <div className="bg-[var(--bg-inner)] rounded-lg border border-[var(--border)]">
                <div className="px-4 py-2 bg-[var(--tag-bg)] border-b border-[var(--border)]">
                  <h3 className="font-medium text-[var(--text-secondary)]">
                    Hidden Connections ({hiddenResults.length})
                  </h3>
                </div>
                <div className="divide-y divide-[var(--border-subtle)]">
                  {hiddenResults.map((result, idx) => (
                    <div key={idx} className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium text-[var(--text-primary)]">
                          <NoteLink
                            slug={result.slug}
                            title={result.title}
                            className="text-[var(--text-primary)]"
                          />
                        </h4>
                        <span className="text-xs px-2 py-1 bg-[var(--purple)]/20 rounded text-[var(--purple)]">
                          {(result.similarity * 100).toFixed(1)}% similar
                        </span>
                      </div>
                      <p className="text-sm text-[var(--text-secondary)] line-clamp-3">
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

      <footer className="border-t border-[var(--border)] mt-8">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="text-sm text-[var(--text-secondary)]">
            Powered by MotherDuck + DuckDB WASM + BGE-M3 embeddings |{" "}
            <a
              href="https://github.com/sspaeti/obsidian-note-taking-assistant"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--link)] hover:text-[var(--link-hover)] hover:underline"
            >
              <svg className="inline w-4 h-4" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
            </a>
            {" "}|{" "}
            <a
              href={BRAIN_BASE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--link)] hover:text-[var(--link-hover)] hover:underline"
            >
              All Notes
            </a>{" "}
          </div>
          <a
            href="https://ssp.sh"
            target="_blank"
            rel="noopener noreferrer"
            className="opacity-70 hover:opacity-100 transition-opacity"
          >
            <img
              src="/logo_ssp_quadrat.png"
              alt="ssp.sh"
              className="h-8 w-auto object-contain"
            />
          </a>
        </div>
      </footer>
    </div>
  );
}
