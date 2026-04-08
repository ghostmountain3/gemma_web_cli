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
git clone https://github.com/YOUR_USERNAME/gemma-web-cli.git
cd gemma-web-cli