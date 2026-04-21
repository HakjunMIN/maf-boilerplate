---
name: azure-ai
description: "Use for Azure AI in Python: Search, Speech, OpenAI, and Document Intelligence. Helps with search, vector or hybrid search, speech-to-text, text-to-speech, transcription, and OCR using Python-first guidance."
license: MIT
metadata:
  author: Microsoft
  version: "1.0.1"
---

# Azure AI Services

This skill is Python-only.

- Use this skill for Python implementations and Python SDK usage.
- Do not use this skill as a source of non-Python guidance.

## Services

| Service | Use When | MCP Tools | CLI |
|---------|----------|-----------|-----|
| AI Search | Full-text, vector, hybrid search | `azure__search` | `az search` |
| Speech | Speech-to-text, text-to-speech | `azure__speech` | - |
| OpenAI | GPT models, embeddings, DALL-E | - | `az cognitiveservices` |
| Document Intelligence | Form extraction, OCR | - | - |

## MCP Server (Preferred)

When Azure MCP is enabled:

### AI Search
- `azure__search` with command `search_index_list` - List search indexes
- `azure__search` with command `search_index_get` - Get index details
- `azure__search` with command `search_query` - Query search index

### Speech
- `azure__speech` with command `speech_transcribe` - Speech to text
- `azure__speech` with command `speech_synthesize` - Text to speech

**If Azure MCP is not enabled:** Run `/azure:setup` or enable via `/mcp`.

## AI Search Capabilities

| Feature | Description |
|---------|-------------|
| Full-text search | Linguistic analysis, stemming |
| Vector search | Semantic similarity with embeddings |
| Hybrid search | Combined keyword + vector |
| AI enrichment | Entity extraction, OCR, sentiment |

## Speech Capabilities

| Feature | Description |
|---------|-------------|
| Speech-to-text | Real-time and batch transcription |
| Text-to-speech | Neural voices, SSML support |
| Speaker diarization | Identify who spoke when |
| Custom models | Domain-specific vocabulary |

## SDK Quick References

For programmatic access to these services, see the condensed SDK guides:

- **AI Search**: [Python](references/sdk/azure-search-documents-py.md)
- **Vision**: [Python](references/sdk/azure-ai-vision-imageanalysis-py.md)
- **Transcription**: [Python](references/sdk/azure-ai-transcription-py.md)
- **Translation**: [Python](references/sdk/azure-ai-translation-text-py.md)
- **Content Safety**: [Python](references/sdk/azure-ai-contentsafety-py.md)

## Service Details

For deep documentation on specific services:

- AI Search indexing and queries -> [Azure AI Search documentation](https://learn.microsoft.com/azure/search/search-what-is-azure-search)
- Speech transcription patterns -> [Azure AI Speech documentation](https://learn.microsoft.com/azure/ai-services/speech-service/overview)
