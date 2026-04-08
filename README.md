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
