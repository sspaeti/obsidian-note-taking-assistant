import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Second Brain RAG | ssp.sh",
  description:
    "Explore and query a personal knowledge graph with semantic search. Discover hidden connections between notes using BGE-M3 embeddings, MotherDuck, and DuckDB.",
  keywords: [
    "second brain",
    "RAG",
    "semantic search",
    "knowledge graph",
    "DuckDB",
    "MotherDuck",
    "embeddings",
    "personal knowledge management",
  ],
  authors: [{ name: "Simon Späti", url: "https://ssp.sh" }],
  creator: "Simon Späti",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_BASE_URL || "https://explore.ssp.sh"
  ),
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "Second Brain RAG",
    title: "Second Brain RAG | Semantic Search for Your Knowledge",
    description:
      "Explore and query a personal knowledge graph with semantic search. Discover hidden connections between notes using embeddings and graph traversal.",
    images: [
      {
        url: "/og-image-explore2.png",
        width: 1501,
        height: 1186,
        alt: "Second Brain RAG - Semantic Search Interface",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Second Brain RAG | Semantic Search for Your Knowledge",
    description:
      "Explore and query a personal knowledge graph with semantic search. Discover hidden connections using embeddings.",
    images: ["/og-image-explore2.png"],
    creator: "@sspaeti",
  },
  icons: {
    icon: [
      { url: "/favicon/favicon.ico", sizes: "any" },
      { url: "/favicon/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon/favicon-96x96.png", sizes: "96x96", type: "image/png" },
    ],
    apple: [
      { url: "/favicon/apple-icon-180x180.png", sizes: "180x180", type: "image/png" },
    ],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="shortcut icon" type="image/x-icon" href="/favicon/favicon.ico" />
        <link rel="apple-touch-icon" sizes="57x57" href="/favicon/apple-icon-57x57.png" />
        <link rel="apple-touch-icon" sizes="60x60" href="/favicon/apple-icon-60x60.png" />
        <link rel="apple-touch-icon" sizes="72x72" href="/favicon/apple-icon-72x72.png" />
        <link rel="apple-touch-icon" sizes="76x76" href="/favicon/apple-icon-76x76.png" />
        <link rel="apple-touch-icon" sizes="114x114" href="/favicon/apple-icon-114x114.png" />
        <link rel="apple-touch-icon" sizes="120x120" href="/favicon/apple-icon-120x120.png" />
        <link rel="apple-touch-icon" sizes="144x144" href="/favicon/apple-icon-144x144.png" />
        <link rel="apple-touch-icon" sizes="152x152" href="/favicon/apple-icon-152x152.png" />
        <link rel="apple-touch-icon" sizes="180x180" href="/favicon/apple-icon-180x180.png" />
        <link rel="icon" type="image/png" sizes="192x192" href="/favicon/android-icon-192x192.png" />
        <link rel="icon" type="image/png" sizes="32x32" href="/favicon/favicon-32x32.png" />
        <link rel="icon" type="image/png" sizes="96x96" href="/favicon/favicon-96x96.png" />
        <link rel="icon" type="image/png" sizes="16x16" href="/favicon/favicon-16x16.png" />
        <link rel="manifest" href="/favicon/manifest.json" />
        <meta name="msapplication-TileColor" content="#ffffff" />
        <meta name="msapplication-TileImage" content="/favicon/ms-icon-144x144.png" />
        <meta name="theme-color" content="#ffffff" />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
