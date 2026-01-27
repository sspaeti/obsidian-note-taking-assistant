import { NextRequest, NextResponse } from "next/server";

// Embedding server URL - local dev or Railway deployment
const EMBED_API_URL = process.env.EMBED_API_URL || "http://localhost:8001/embed";

async function getEmbedding(text: string): Promise<number[]> {
  const response = await fetch(EMBED_API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Embedding server error: ${response.status} - ${errorText}`);
  }

  const data = await response.json();
  return data.embedding;
}

export async function POST(request: NextRequest) {
  try {
    const { text } = await request.json();

    if (!text || typeof text !== "string") {
      return NextResponse.json(
        { error: "Text is required and must be a string" },
        { status: 400 }
      );
    }

    const embedding = await getEmbedding(text);
    return NextResponse.json({ embedding });

  } catch (error) {
    console.error("Embedding error:", error);

    const message = error instanceof Error ? error.message : "Unknown error";

    // Check if it's a connection error (server not running)
    if (message.includes("ECONNREFUSED") || message.includes("fetch failed")) {
      return NextResponse.json(
        {
          error: "Embedding server not available. For local dev run: make embed-server",
        },
        { status: 503 }
      );
    }

    return NextResponse.json(
      { error: `Failed to generate embedding: ${message}` },
      { status: 500 }
    );
  }
}
