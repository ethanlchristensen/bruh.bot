# Memory System

The memory system observes user messages across the server and uses an LLM to extract structured memories about each user. These memories are then injected into the AI's system prompt during conversations, allowing the bot to personalize responses based on what it knows about each user.

## Architecture

```
every message → enqueue_message() → per-user in-memory buffer
                                        │
    background task (main: 20min) ───────┘
    background task (mood: 5min)  ───────┘
                                        │
                                        ▼
        for each user with ≥5 new messages:
          send current memories + recent messages to LLM
          LLM returns {actions: [add/update/delete]}
          apply actions → MongoDB

when bot is @mentioned → build_message_context()
  → queries memories for conversation users
  → injects into system prompt → LLM personalizes responses
```

## Memory Categories & Retention

Each memory is assigned a category that determines how long it persists. Categories with a TTL auto-expire via MongoDB's built-in TTL index.

| Category      | Retention | Description                          |
|---------------|-----------|--------------------------------------|
| `identity`    | Permanent | Immutable facts (name, age, role)    |
| `trait`       | Permanent | Personality, skills, profession      |
| `admin`       | Permanent | Manually added by server admins      |
| `preference`  | 90 days   | Likes, dislikes, favorites           |
| `fact`        | 90 days   | General facts about the user         |
| `relationship`| Permanent| How they feel about other users      |
| `opinion`     | 30 days   | Opinions on topics, beliefs          |
| `mood`        | 7 days    | Current emotional state, feelings    |

## How Extraction Works

1. **Message buffering**: Every non-bot message above 10 characters is buffered per-user in memory. No messages leave the server — the buffer is ephemeral.

2. **Extraction loops**: Two background tasks run continuously:

   | Loop | Interval | Focus | Min Messages |
   |------|----------|-------|-------------|
   | Main | 20 minutes | All categories | 5 |
   | Mood | 5 minutes | `mood` category only | 3 |

3. **LLM extraction**: For each eligible user, the service sends:
   - All **current memories** for that user (from MongoDB)
   - Up to 50 **recent messages** (from the in-memory buffer)
   
   The LLM analyzes these together and returns a JSON list of actions:
   - **add** — new fact, trait, or observation
   - **update** — changed opinion or preference
   - **delete** — contradicted or outdated memory

4. **Cost controls**:
   - Messages shorter than 10 characters are skipped (emojis, "lol", "ok")
   - Minimum 5 messages required before extraction (prevents spam)
   - Max 50 messages sent per extraction call
   - Extraction only triggers at the configured interval
   - Cheap model used by default (`deepseek/deepseek-v4-flash`)

## Context Injection

When a user mentions the bot, `build_message_context`:

1. Identifies all unique users in the conversation thread
2. Queries MongoDB for memories about those users
3. Selects a mix: **all permanent memories** (identity, trait, admin, relationship) + **recent memories** (preference, opinion, mood, etc.) up to the injection limit (default 10)
4. Appends to the system prompt as:

```
## GROUNDING MEMORIES:
These are known facts and observations about users in this conversation.
Use them to personalize responses naturally.

- [Ethan]: software engineer, passionate about Python (trait)
- [Ethan]: dislikes Klim with a passion → @Klim (relationship)
```

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
| `extractionModel` | `deepseek/deepseek-v4-flash` | Model for extraction (should be cheap) |
| `maxMessagesPerExtraction` | `50` | Max messages sent per extraction call |
| `minMessagesForExtraction` | `5` | Minimum messages before triggering |
| `minMessageLength` | `10` | Minimum characters to buffer a message |
| `maxMemoriesPerUser` | `50` | Max memories stored per user |
| `maxInjectionCount` | `10` | Max memories injected into context |
| `enabledCategories` | All except admin | Which categories the LLM can auto-extract |

## MongoDB Collection Schema

**Collection**: `UserMemories`

```json
{
  "_id": ObjectId,
  "guild_id": Int64,
  "user_id": Int64,
  "memory": "likes pineapple on pizza",
  "category": "preference",
  "confidence": 0.85,
  "source_message_id": Int64,
  "created_at": ISODate,
  "updated_at": ISODate,
  "created_by": "ai",
  "expires_at": ISODate or null,
  "target_user_id": Int64 or null
}
```

**Indexes**:
- `(guild_id, user_id)` — fast per-user lookups
- `expires_at` (TTL) — auto-deletes decayed memories
- `source_message_id` — deduplication

## Key Design Decisions

- **All messages, not just mentions**: Memory extraction runs on all user messages in the server, not just those directed at the bot. This builds a richer understanding of each user over time.
- **Per-user extraction**: Each user gets their own LLM call with their own context, rather than batching multiple users together. This improves accuracy.
- **LLM-driven mutation**: The extraction LLM receives current memories alongside new messages and decides what to add, update, or delete. This means the system self-corrects as opinions and preferences change.
- **Category-based decay**: Different types of memories have different retention periods. Mood decays in 7 days; identity, trait, admin, and relationship facts are permanent. MongoDB TTL indexes handle cleanup automatically.
- **In-memory buffering**: Messages are buffered in process memory between extraction runs. If the bot restarts, buffers reset but MongoDB persists existing memories.
- **Permanent + recent mix**: When injecting into context, permanent memories (identity, traits, admin, relationships) always appear, while recent memories fill remaining slots. This provides both grounding and current context.
- **Relationship target tracking**: Relationship memories store a `target_user_id` (resolved from the Discord display name) so the bot can @mention the target user in responses when relevant.