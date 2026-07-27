# Memory System

The memory system observes user messages and uses an LLM with tool-calling to search, add, update, and remove structured memories about each user. Memories are embedded as vectors and stored in MongoDB Atlas with a vector search index, enabling semantic similarity queries. These memories are injected into the bot's system prompt during conversations for personalized responses.

## Architecture

```
every message → enqueue_message() → per-guild in-memory buffer
                                        │
  background task (interval: N min) ─────┘
                                        │
                                        ▼
                  Agentic Extraction Loop (tool-calling):
                    LLM (extractionModel) receives:
                      • transcript + known users
                      • tools: search_memories, get_user_memories,
                               add_memory, update_memory, remove_memory
                      │
                      ▼ (loop up to maxToolRounds)
                    LLM calls search_memories → vector search (Atlas $vectorSearch)
                    LLM calls get_user_memories → MongoDB find
                    LLM calls add_memory → embed text → dedupe check → store
                    LLM calls update_memory → re-embed if text changed → store
                    LLM calls remove_memory → delete by ID
                      │
                      ▼
                    LLM stops calling tools (finished)
                      │
                      ▼
                    enforce max memories per user

when bot is @mentioned → build_message_context()
  → embed incoming message → $vectorSearch for semantically relevant memories
  → blend with permanent-category memories (identity, trait, admin, relationship)
  → inject top-k into system prompt → LLM personalizes responses
```

## Memory Categories & Retention

| Category       | Retention | Description                          |
|----------------|-----------|--------------------------------------|
| `identity`     | Permanent | Immutable facts (name, age, role)    |
| `trait`        | Permanent | Personality, skills, profession      |
| `admin`        | Permanent | Manually added by server admins      |
| `relationship` | Permanent | How they feel about other users      |
| `preference`   | 90 days   | Likes, dislikes, favorites           |
| `fact`         | 90 days   | General facts about the user         |
| `opinion`      | 30 days   | Opinions on topics, beliefs          |
| `mood`         | 7 days    | Current emotional state, feelings    |

Categories with a TTL auto-expire via MongoDB's TTL index on the `expires_at` field.

## How Extraction Works

### Message Buffering

Every non-bot message above `minMessageLength` (default 10) characters is buffered per-guild in memory. No messages leave the server — the buffer is ephemeral and resets on restart (MongoDB persists existing memories).

### Agentic Tool-Calling Extraction (v2)

The extraction loop is now an **agentic LLM loop** using native tool-calling instead of a single JSON action list:

1. **Trigger**: Timer fires at the configured interval (default 20 min for main, 5 min for mood). The last `maxMessagesPerExtraction` messages form a transcript.

2. **Tool provisioning**: The LLM receives five tools:
   - `search_memories(query, user_id?, category?, limit?)` — semantic vector search against Atlas to find what it already knows
   - `get_user_memories(user_id)` — full memory list for one user
   - `add_memory(user_id, memory, category, confidence, target_username?, source_message_id?)` — create a new memory
   - `update_memory(memory_id, new_memory?, category?, confidence?)` — modify an existing memory
   - `remove_memory(memory_id, reason)` — delete a contradicted memory

3. **Agentic loop** (up to `maxToolRounds` rounds, default 8):
   ```
   while round < maxToolRounds:
       response = LLM.complete(messages + tools)
       if no tool_calls: break          # LLM is done
       for each tool_call:
           result = execute_tool(tool_call)
           append result to messages
   ```

4. **Semantic deduplication**: When the LLM calls `add_memory`, the `MemoryToolExecutor` first embeds the text and searches for semantically similar existing memories. If cosine similarity ≥ `dedupeThreshold` (default 0.92), the add is **auto-converted to an update** of the existing memory. The LLM is informed of this in the tool result.

5. **Guardrails**:
   - `user_id` must be in the current conversation batch
   - `admin` category rejected for AI-generated memories
   - `memory_id` verified to exist and belong to the correct guild/user
   - `maxToolCallsPerBatch` hard cap (default 40) prevents runaway costs
   - `maxAddsPerUserPerBatch` prevents over-adding for one user

6. **After extraction**: `enforce_max_memories` prunes lowest-confidence non-permanent memories if a user exceeds `maxMemoriesPerUser`.

### LLM Prompt & Workflow

The system prompt instructs the LLM to:
1. **Search before adding** — always check what you already know
2. **Get the full picture** — use `get_user_memories` for users you haven't seen before
3. **Add new insights** — confidence 0.9+ for explicit statements, 0.5-0.7 for implied
4. **Update when facts change** — contradicted opinions get updated not duplicated
5. **Remove contradictions** — explicitly disavowed facts get deleted
6. **Be conservative** — "Does this tell me something meaningful about WHO this person IS, not just what they casually DID?"
7. **Multi-user awareness** — if two people agree on something, record it for both
8. **Never extract for the bot itself**

## Embedding & Semantic Search

### Embedding Generation

Every memory added or updated is embedded using OpenRouter's embeddings API (default model: `openai/text-embedding-3-small`, 1536 dimensions). Embeddings are stored directly on the memory document:

```json
{
  "memory": "loves pineapple on pizza",
  "embedding": [0.0123, -0.0456, ...],
  "embedding_model": "openai/text-embedding-3-small"
}
```

### Atlas Vector Index

A MongoDB Atlas vector search index is auto-created on first boot (on the `embedding` field):
- **Name**: `memory_vector_index`
- **Type**: `knnVector` with cosine similarity, 1536 dimensions
- **Filter fields**: `guild_id`, `user_id`, `category`
- Requires Atlas M10+ tier

If creation fails, the bot logs a warning with manual setup instructions and continues (memories are saved without embeddings, graceful degradation).

### Semantic Queries

**At extraction time**: `search_memories` embeds the query text and runs `$vectorSearch` against the index, filtered to the current guild and optionally specific users/categories.

**At chat time**: `build_message_context()` embeds the incoming user message and retrieves semantically relevant memories for conversation participants, blended with all permanent-category memories for that user.

## Context Injection

When a user mentions the bot, `build_message_context`:

### If `semanticRetrieval` is enabled (default):

1. Embeds the incoming message text via OpenRouter
2. Runs `$vectorSearch` filtered to conversation participants, `min_score ≥ retrievalMinScore`
3. Separates results into permanent (identity/trait/admin/relationship) and non-permanent categories
4. Fetches any additional permanent memories not returned by the semantic search
5. De-duplicates and takes top `maxInjectionCount` results
6. Appends to the system prompt as:

```
## GROUNDING MEMORIES:
These are known facts and observations about users in this conversation.
Use them to personalize responses naturally.

- [Ethan]: software engineer, passionate about Python (trait)
- [Ethan]: dislikes Klim with a passion → @Klim (relationship)
```

### Fallback (semantic retrieval disabled or embedding fails):

Identifies all unique users in the conversation thread, queries MongoDB for their memories, selects a mix of **all permanent** + **recent non-permanent** up to `maxInjectionCount`.

## Slash Commands

### User Commands

| Command | Description |
|---------|-------------|
| `/memories view [page]` | View your own memories, grouped by category |

### Admin Commands

All admin commands require `adminIds` permission.

| Command | Description |
|---------|-------------|
| `/memories admin add <user> <text> [category]` | Manually add a memory about a user |
| `/memories admin remove <memory_id>` | Remove a memory by its ID |
| `/memories admin list <user> [category] [page]` | List all memories for a user |
| `/memories admin clear <user>` | Remove all memories for a user |
| `/memories admin toggle <enabled>` | Enable or disable auto-extraction |
| `/memories admin extract_now` | Force immediate extraction for all users |
| `/memories admin extract_user <user>` | Force immediate extraction for a user |

## Configuration

All settings are per-guild, stored in MongoDB under `DynamicConfig.memoryConfig`:

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Enable or disable memory extraction |
| `extractionIntervalMinutes` | `20` | Minutes between main extraction runs |
| `moodExtractionIntervalMinutes` | `5` | Minutes between mood extraction runs |
| `extractionProvider` | `openrouter` | AI provider for extraction |
| `extractionModel` | `deepseek/deepseek-v4-flash` | Model for extraction (must support tool-calling) |
| `maxMessagesPerExtraction` | `50` | Max messages sent per extraction call |
| `minMessagesForExtraction` | `5` | Minimum messages before triggering |
| `minMessageLength` | `10` | Minimum characters to buffer a message |
| `maxMemoriesPerUser` | `50` | Max memories stored per user |
| `maxInjectionCount` | `10` | Max memories injected into context |

### Embedding Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `embeddingModel` | `openai/text-embedding-3-small` | OpenRouter model ID for memory embeddings |
| `embeddingDimensions` | `1536` | Vector dimensions (must match the model) |
| `semanticRetrieval` | `true` | Use vector search at chat time for relevant memories |
| `retrievalMinScore` | `0.35` | Minimum cosine similarity for chat-time retrieval |
| `dedupeThreshold` | `0.92` | Auto-update existing memory if similarity ≥ threshold |

### Tool Agent Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `maxToolRounds` | `8` | Maximum LLM→tool→result loops per extraction |
| `maxToolCallsPerBatch` | `40` | Hard cap on total tool calls to prevent runaway costs |
| `maxAddsPerUserPerBatch` | `10` | Max new memories added per user in one extraction |

## MongoDB Collection Schema

**Collection**: `UserMemories` (environment-suffixed: `UserMemories_dev` / `UserMemories_prod`)

```json
{
  "_id": ObjectId,
  "guild_id": Int64,
  "user_id": Int64,
  "memory": "likes pineapple on pizza",
  "category": "preference",
  "confidence": 0.85,
  "source_message_id": Int64,
  "target_user_id": Int64 or null,
  "created_at": ISODate,
  "updated_at": ISODate,
  "created_by": "ai",
  "expires_at": ISODate or null,
  "embedding": [0.0123, -0.0456, ...] or null,
  "embedding_model": "openai/text-embedding-3-small" or null
}
```

**Indexes**:
- `(guild_id, user_id)` — fast per-user lookups
- `expires_at` (TTL) — auto-deletes decayed memories
- `source_message_id` — deduplication
- `embedding_model` — filter by model version for re-embedding
- `memory_vector_index` (Atlas Search) — knnVector cosine similarity on `embedding` field

## Backfill Existing Memories

When upgrading from the v1 (JSON extraction) to v2 (tool-calling + embeddings), existing memories won't have embeddings. Run the backfill script:

```bash
# Dry run to see how many memories need embedding
python tools/backfill_memory_embeddings.py --guild <GUILD_ID> --env prod --dry-run

# Generate embeddings for all existing memories
python tools/backfill_memory_embeddings.py --guild <GUILD_ID> --env prod
```

The script reads the OpenRouter API key from the guild's config (decrypting the Fernet-encrypted value), batches memories in groups of 50, calls OpenRouter's embeddings endpoint, and writes embeddings back to MongoDB.

## Key Design Decisions

- **All messages, not just mentions**: Memory extraction runs on all user messages in the server, building a richer understanding of each user over time.
- **Agentic tool-calling**: The extraction LLM is given tools and searches/reads/modifies memories in an interactive loop rather than generating a single JSON action list. This dramatically improves accuracy — the LLM can find existing memories before adding, verify IDs before updating, and self-correct errors.
- **Semantic deduplication at insert time**: Before storing a new memory, the executor embeds it and checks for near-duplicates. High-similarity matches auto-convert to updates, preventing duplicate or near-duplicate memories.
- **Vector search for retrieval**: At chat time, the incoming message is embedded and used to find semantically relevant memories, not just the most recent or most permanent ones.
- **LLM-driven mutation**: The extraction LLM reads current memories and decides what to add, update, or delete. The system self-corrects as opinions and preferences change.
- **Category-based decay**: Different retention periods per category. MongoDB TTL indexes handle cleanup automatically.
- **In-memory buffering**: Messages are buffered in process memory between extraction runs. If the bot restarts, buffers reset but MongoDB persists existing memories.
- **Hybrid retrieval strategy**: At chat time, permanent memories (identity, traits, admin, relationships) are always included, while semantically relevant non-permanent memories fill remaining slots. This provides both grounding and current context.
- **Relationship target tracking**: Relationship memories store a `target_user_id` (resolved from the Discord display name) so the bot can @mention the target user in responses when relevant.
- **Cost controls**: Multi-round agentic loops are bounded by `maxToolRounds` and `maxToolCallsPerBatch`. The extraction model should be a cheap, fast model with tool-calling support (e.g., `deepseek/deepseek-v4-flash`). Embeddings only cost ~$0.02 per 1M tokens on OpenRouter.

## Files

| File | Purpose |
|------|---------|
| `bot/services/memory_extraction_service.py` | Agentic extraction loop, message buffering, scheduling |
| `bot/services/memory_tools.py` | Tool schemas + `MemoryToolExecutor` (search/get/add/update/remove + dedupe) |
| `bot/services/mongo_memory_service.py` | MongoDB CRUD, vector index creation, `search_memories_semantic()` |
| `bot/services/ai/embedding_service.py` | OpenRouter embeddings API client |
| `bot/services/message_service.py` | Semantic retrieval at chat time with fallback |
| `bot/services/config_service.py` | `MemoryConfig` model with all settings |
| `bot/commands/memory_command.py` | `/memories` slash command |
| `tools/backfill_memory_embeddings.py` | One-shot script to embed existing memories |
| `frontend/src/app/routes/_main/config/memory.tsx` | Dashboard memory config UI |
| `docs/memory-system.md` | This document |