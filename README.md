
# Obsidian Note-Taking Assistant

The goal is to ask question to my local second brain (7000+ markdown files) like:
- Show me my notes on "X"
- Notes that are relevant from my vault.
- Which note is most relevant to "Note X or Term"
- Highlight any disagreements between the notes


## Workflow

1. Convert Markdown notes, formatted like below into Vectors (Embeddings)

```md
# Second Brain Assistant with Obsidian

my content

## title 1
## title 2

## title 3

[[link to another note]] asdf


### title 3


---
Origin: heard from [[Person B]]
References: [[Integrate OpenAI into Obsidian]]
Tags: #🗃/🌻 
Created [[2023-07-18]]
```

Use DuckDB with HNSW Index for the similarity search. 


## Futher Reading or related notes
- https://blog.brunk.io/posts/similarity-search-with-duckdb/
- https://www.ssp.sh/brain/second-brain-assistant-with-obsidian-notegpt

