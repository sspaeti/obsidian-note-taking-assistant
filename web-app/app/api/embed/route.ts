import { NextRequest, NextResponse } from "next/server";

// Local embedding server URL (default for local dev)
const LOCAL_EMBED_URL = process.env.EMBED_API_URL || "http://localhost:8001/embed";

// Check if we're in production (Vercel)
const isProduction = process.env.VERCEL === "1";

async function getEmbeddingFromLocal(text: string): Promise<number[]> {
  const response = await fetch(LOCAL_EMBED_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    throw new Error(`Local embedding server error: ${response.statusText}`);
  }

  const data = await response.json();
  return data.embedding;
}

async function getEmbeddingFromHuggingFace(text: string): Promise<number[]> {
  const apiKey = process.env.HUGGINGFACE_API_KEY;
  if (!apiKey) {
    throw new Error("HUGGINGFACE_API_KEY not set");
  }

  // Use the HuggingFace Inference library for proper routing
  const { HfInference } = await import("@huggingface/inference");
  const hf = new HfInference(apiKey);

  const embedding = await hf.featureExtraction({
    model: "BAAI/bge-m3",
    inputs: text,
  });

  // HuggingFace returns nested array for single input
  return Array.isArray(embedding[0])
    ? (embedding[0] as number[])
    : (embedding as unknown as number[]);
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

    let embedding: number[];

    // In production, go straight to HuggingFace (no local server)
    if (isProduction) {
      if (!process.env.HUGGINGFACE_API_KEY) {
        return NextResponse.json(
          { error: "HUGGINGFACE_API_KEY is not configured" },
          { status: 500 }
        );
      }

      try {
        embedding = await getEmbeddingFromHuggingFace(text);
      } catch (hfError) {
        console.error("HuggingFace embedding failed:", hfError);
        return NextResponse.json(
          {
            error: `HuggingFace API failed: ${hfError instanceof Error ? hfError.message : "Unknown error"}. The BGE-M3 model may be loading - try again in 30 seconds.`,
          },
          { status: 503 }
        );
      }
    } else {
      // Local development: try local server first
      try {
        embedding = await getEmbeddingFromLocal(text);
      } catch (localError) {
        console.warn("Local embedding server unavailable:", localError);

        if (!process.env.HUGGINGFACE_API_KEY) {
          return NextResponse.json(
            {
              error:
                "Local embedding server not running and HUGGINGFACE_API_KEY not set. Run: make embed-server",
            },
            { status: 500 }
          );
        }

        try {
          embedding = await getEmbeddingFromHuggingFace(text);
        } catch (hfError) {
          console.error("HuggingFace fallback failed:", hfError);
          return NextResponse.json(
            {
              error: `Both local and HuggingFace failed. Run: make embed-server`,
            },
            { status: 500 }
          );
        }
      }
    }

    return NextResponse.json({ embedding });
  } catch (error) {
    console.error("Embedding error:", error);
    return NextResponse.json(
      { error: `Failed to generate embedding: ${error instanceof Error ? error.message : "Unknown error"}` },
      { status: 500 }
    );
  }
}
