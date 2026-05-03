# Gemma Web CLI

A search-enabled local CLI assistant for Ollama models like Gemma.

It keeps normal chat behavior, but automatically searches the web and reads pages when a question needs current information. It also stores useful page content locally for follow-up questions through memory and embeddings.

## Features

- Normal local chat through Ollama
- Automatic web search using DDGS
- Page reading and text extraction
- Local memory with embeddings
- Streaming responses
- Cross-platform support for Windows, macOS, and Linux
- Configurable chat and embedding models

## Why this exists

Local models like Gemma are great for private, offline-style workflows, but they do not know live web information by default. This project adds a lightweight retrieval layer around Ollama so the assistant can:

- answer normal questions naturally
- search current information when needed
- read and extract text from pages
- remember useful sources for follow-up questions

## Requirements

- Python 3.10 or newer
- [Ollama](https://ollama.com/) installed and running
- A pulled chat model, such as `gemma4:26b`
- A pulled embedding model, such as `embeddinggemma`

## Install

### Option 1: Clone the repo

```bash
git clone https://github.com/ghostmountain3/gemma_web_cli.git
cd gemma_web_cli
```

### Option 2: Install with pipx

This is the cleanest way to install the CLI as a command.

```bash
pipx install git+https://github.com/ghostmountain3/gemma_web_cli.git
```

Then run:

```bash
gemma-web
```

## Developer Setup

### Windows

Create and activate a virtual environment:

```powershell
py -m venv .venv
.venv\Scripts\activate
```

Install the project:

```powershell
pip install -e .
```

Run the CLI:

```powershell
gemma-web
```

### macOS / Linux

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project:

```bash
pip install -e .
```

Run the CLI:

```bash
gemma-web
```

## Pull the Ollama models

Before running the app, make sure you have a chat model and an embedding model.

Example:

```bash
ollama pull gemma4:26b
ollama pull embeddinggemma
```

## Quick Start

Once Ollama is running and the models are pulled, launch the app:

```bash
gemma-web
```

Then type naturally, for example:

```text
what is recursion
what is the current price of bitcoin
what changed in ollama recently
based on what you read earlier, summarize the main point
```

## Web Research Commands

`gemma-web` also has non-interactive commands for local research pipelines. These use free/local Python libraries only: DDGS for search, `requests` for fetch, `trafilatura` when available for extraction, and BeautifulSoup as fallback. No paid APIs are required.

Search returns structured search candidates:

```powershell
gemma-web search "local LLM agents" --json
```

Fetch downloads a text/html-style page with timeout, size limit, user-agent, binary-content rejection, and structured errors:

```powershell
gemma-web fetch "https://example.com" --json
```

Extract fetches and extracts readable page content:

```powershell
gemma-web extract "https://example.com" --json
```

Research runs search, dedupe/ranking, topic relevance filtering, fetch, extraction, deterministic source summaries, and a browsing-style synthesized answer:

```powershell
gemma-web research "what is trending in local LLM agents" --json
gemma-web research "latest Ollama settings" --json --fetch-top 3 --no-cache
gemma-web research "show top results for Ollama settings" --json --mode search_results
```

Research JSON includes:

- `searches`: structured DDGS search results
- `response_mode`: `research_answer` or `search_results`
- `query_variants`: focused query expansions used for answer-style research
- `sources`: fetched/extracted sources with summaries, key points, source type, relevance, credibility, snippet-only status, and errors
- `answer_outline`: main findings, consensus, uncertainty, and implications
- `synthesized_answer`: concise answer with key findings, interpretation, limitations, and sources
- `limitations`: freshness, blocked-page, or extraction caveats

Use `--mode research_answer` for a synthesized answer and `--mode search_results` for raw ranked candidates. `--mode auto` chooses from intent: natural questions, "research", "explain", "latest/current", and trend/news queries become answer-style research; explicit "links only", "top results", or "raw search" requests stay as search results.

Trending/current queries such as "trending", "latest", "current", "popular", "viral", and "news" expand into a small number of focused variants and label forum/community sources clearly. Relevance filtering uses the full query, domain clues such as software/finance/health/government/entertainment, source type, and keyword overlap to downrank unrelated meanings.

## Cache

Research results and fetched/extracted artifacts are cached under `data/cache` by default. Configure with:

```powershell
$env:GEMMA_WEB_CACHE_DIR="data/cache"
$env:GEMMA_WEB_CACHE_TTL_SECONDS="3600"
```

Cache commands:

```powershell
gemma-web cache status
gemma-web cache clear
```

Use `--no-cache` on research to bypass cached research results.

## Changing the model

The chat and embedding models can be changed with environment variables.

### Windows PowerShell

```powershell
$env:GEMMA_WEB_MODEL="gemma4:26b"
$env:GEMMA_WEB_EMBED_MODEL="embeddinggemma"
gemma-web
```

### macOS / Linux

```bash
export GEMMA_WEB_MODEL="gemma4:26b"
export GEMMA_WEB_EMBED_MODEL="embeddinggemma"
gemma-web
```

You can replace `gemma4:26b` with another Ollama chat model if you want to test a different setup.

Examples:

### Windows PowerShell

```powershell
$env:GEMMA_WEB_MODEL="gemma3"
gemma-web
```

### macOS / Linux

```bash
export GEMMA_WEB_MODEL="gemma3"
gemma-web
```

## How it works

At a high level, the app does this:

1. Accepts a normal user message
2. Routes the request as local-only, memory-only, web search, or web search plus memory
3. Uses DDGS to search when fresh information is needed
4. Reads and extracts text from selected pages
5. Chunks and embeds useful content for local memory
6. Sends the strongest evidence to the Ollama chat model
7. Streams the final answer back in the terminal

## Notes

- Ollama must be running locally
- Web lookups use DDGS
- The tool stores local memory in the `data/` folder
- Saved memory is not meant to be committed to Git
- Streaming may fall back to non-streaming if the connection is interrupted
- Search results are candidates, not guaranteed facts
- Topic filtering is heuristic and can miss subtle ambiguity
- Some sites block scraping or return limited text
- JavaScript-heavy pages may not extract well
- Snippet-only answers are less reliable than fetched/extracted page content
- PDFs and binary downloads are skipped by the lightweight fetcher

## Troubleshooting

### Ollama is not responding

Make sure Ollama is installed and running, then test a model manually:

```bash
ollama run gemma4:26b
```

### The embedding model is missing

Pull it manually:

```bash
ollama pull embeddinggemma
```

### The command is not found after install

If you used `pipx`, make sure `pipx` is on your PATH.

If you used developer mode, make sure you ran:

```bash
pip install -e .
```

### Web answers are slow

That is normal for larger chat models and multi-page retrieval. You can reduce the number of pages read or lower the amount of page text kept per request in `config.py`.

## Roadmap

- Better router confidence handling
- Improved page deduplication and refresh logic
- Similarity thresholds for memory filtering
- Source inspection commands
- Better support for dynamic pages
- Cleaner packaging and release workflow

## Contributing

Issues and pull requests are welcome.

If you want to contribute:

- keep changes focused
- include a clear description of what changed
- test on at least one platform before opening a PR

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
