# Juno Discord Bot — Architecture & Feature Reference

## Overview

Juno is a multi-featured Discord bot written in Python (`discord.py`), with a dashboard frontend in React/TanStack. It supports AI chat via multiple LLM providers, real-time voice conversation, image generation, music playback, and a user memory system — all with per-guild configuration stored in MongoDB.

**Stack:**
- **Bot:** Python 3.13, `discord.py` (GitHub), `openai`, `anthropic`, `ollama`, `google-genai`
- **API:** FastAPI (`bot/api/api.py`) — config CRUD, model listing
- **Frontend:** React 19, TanStack Router + Query, Tailwind CSS, Vite
- **Database:** MongoDB (via `motor` / `pymongo`)
- **Containerization:** Docker Compose with separate services for bot, API, and frontend

---

## File Structure

```
bruh.bot/
├── main.py                          # Entry point — creates Juno client and runs it
├── pyproject.toml                   # Python dependencies (Poetry)
├── Makefile                         # Shortcuts: install, bot, api, frontend
├── config.sample.yaml               # Template for secrets (tokens, MongoDB URI, encryption key)
├── docker-compose.yaml              # 6 services: bot-dev, bot-prod, api-dev, api-prod, frontend-dev, frontend-prod
├── Dockerfile                       # Bot container
├── Dockerfile.api                   # API container
│
├── bot/
│   ├── juno.py                      # Main bot class (Juno) — extends commands.Bot
│   ├── settings.py                  # Startup banner, logging config
│   │
│   ├── api/
│   │   └── api.py                   # FastAPI app — /config CRUD, /health, /guilds, /config/models
│   │
│   ├── cogs/
│   │   ├── music.py                 # Music commands (/play, /skip, /pause, /resume, /seek, /filter, /queue, etc.)
│   │   ├── real_time_voice_cog.py   # Real-time voice conversation (/voice_join, /voice_start, /voice_stop, /voice_leave)
│   │   └── scheduler.py            # Scheduled morning messages (/set_morning_channel, /set_morning_time)
│   │
│   ├── commands/
│   │   ├── chat_command.py          # /chat — direct LLM query
│   │   ├── describe_command.py      # /describe — Midjourney-style prompt from image
│   │   ├── echo_command.py          # /echo — admin: send message as bot
│   │   ├── image_admin_command.py   # /image_admin — subcommands for image limit management
│   │   ├── image_stats_command.py   # /image_stats — user's daily image generation usage
│   │   ├── memory_command.py        # /memories — user & admin memory management
│   │   ├── ping_command.py          # /ping — latency check
│   │   ├── reply_command.py         # /reply — admin: reply to message as bot
│   │   └── sync_command.py          # /sync — admin: sync slash commands to guild
│   │
│   ├── services/
│   │   ├── config_service.py        # ConfigService — YAML secrets + MongoDB dynamic config, file watcher
│   │   ├── cooldown_service.py      # Per-user mention cooldown enforcement
│   │   ├── discord_messages_service.py  # For scraping other bots' messages (DiscordScrapeBot integration)
│   │   ├── embed_service.py         # Standardized embed creation (success, error, now-playing, morning)
│   │   ├── memory_extraction_service.py # Background LLM-driven memory extraction from messages
│   │   ├── message_service.py       # Message context building, image attachment detection
│   │   ├── mongo_chat_service.py    # MongoChatService — persist chat threads
│   │   ├── mongo_image_limit_service.py  # Daily image generation quotas
│   │   ├── mongo_memory_service.py  # CRUD for user memories in MongoDB
│   │   ├── mongo_morning_config_service.py  # Per-guild morning message scheduling
│   │   └── response_service.py      # Send responses (text + optional file), reply/followup logic
│   │
│   ├── services/ai/
│   │   ├── ai_orchestrator.py       # Intent detection (chat vs image_generation) via LLM
│   │   ├── image_generation_service.py  # Generate/edit images via OpenRouter (Gemini Imagen)
│   │   ├── real_time_audio_service.py   # RealTimeAudioService — OpenAI Realtime API voice
│   │   ├── types.py                 # UserIntent dataclass, ImageGenerationResponse
│   │   │
│   │   └── gateway/                 # Provider-agnostic AI gateway (SDK-style, no HTTP concepts)
│   │       ├── gateway.py           # MeshGateway — complete(), stream(), get_models()
│   │       ├── exceptions.py        # ProviderAuthError, ProviderNotFoundError
│   │       ├── utils.py             # parse_data_url helper
│   │       │
│   │       ├── providers/
│   │       │   ├── base.py          # BaseProviderAdapter abstract class
│   │       │   ├── ollama_provider.py    # Ollama (local) provider adapter
│   │       │   ├── openrouter_provider.py # OpenRouter provider adapter
│   │       │   └── registry.py      # ProviderRegistry — register/lookup adapters
│   │       │
│   │       └── schemas/
│   │           ├── models.py        # ModelInfo, ModelCapabilities
│   │           ├── request.py       # NormalizedRequest, Message, MessagePart
│   │           ├── response.py      # NormalizedResponse, ResponsePart
│   │           └── chunks.py        # NormalizedChunk (streaming)
│   │
│   ├── services/music/
│   │   ├── audio_service.py         # AudioService — yt-dlp extraction, FFmpeg audio source creation
│   │   ├── music_player.py          # MusicPlayer — play, queue, skip, pause, seek, filter
│   │   ├── music_queue_service.py   # MusicQueueService — guild → player map, manages lifecycle
│   │   ├── music_websocket_service.py # WebSocket server for frontend music dashboard
│   │   ├── priority_music_queue.py  # Priority queue with put_front support
│   │   └── types.py                 # AudioMetaData, FilterPreset, MusicPlayerActionResponse, etc.
│   │
│   └── utils/
│       ├── juno_slash.py            # JunoSlash — loads all slash commands at startup
│       └── decarators/
│           ├── admin_check.py       # @is_admin() — restricts to configured admin IDs
│           ├── command_logging.py   # @log_command_usage() — logs who ran what command
│           ├── global_block_check.py # @is_globally_blocked() — blocks users in globalBlockList
│           └── voice_check.py       # @require_voice_channel() — ensures user is in VC
│
├── frontend/
│   └── src/
│       ├── main.tsx                 # React entry point
│       ├── app/
│       │   ├── index.tsx            # App root — providers wrapping
│       │   ├── provider.tsx         # Main provider composition (theme, auth, query, etc.)
│       │   ├── routeTree.gen.ts     # Auto-generated route tree (TanStack Router)
│       │   └── routes/
│       │       ├── __root.tsx       # Root layout
│       │       ├── index.tsx        # Landing / redirect
│       │       ├── login.tsx        # Discord OAuth2 login
│       │       ├── auth.callback.tsx # OAuth2 callback handler
│       │       ├── _main.tsx        # Authenticated layout (sidebar + content)
│       │       └── _main/
│       │           ├── config.tsx   # Guild configuration dashboard
│       │           ├── music.tsx    # Music player dashboard
│       │           └── profile.tsx  # User profile page
│       │
│       ├── components/
│       │   ├── sidebar/             # AppSidebar, NavUser
│       │   ├── theme/               # ThemeProvider, theme toggles (base, color, dark/light)
│       │   ├── markdown/            # Markdown rendering
│       │   ├── layouts/             # ContentLayout
│       │   ├── errors/              # Error boundary component
│       │   ├── guild-selector.tsx   # Guild dropdown selector
│       │   ├── provider-icon-renderer.tsx # AI provider icon
│       │   └── ui/                  # shadcn/ui components (button, card, dialog, sidebar, etc.)
│       │
│       ├── config/env.ts            # Environment variable types
│       ├── contexts/
│       │   ├── auth-context.tsx     # Discord OAuth2 auth state
│       │   ├── config-changes-context.tsx # Dirty config tracking
│       │   ├── guild-context.tsx    # Selected guild state
│       │   └── music-context.tsx    # Music WebSocket state + controls
│       │
│       ├── hooks/
│       │   ├── use-auth.ts          # Auth hook re-export
│       │   ├── use-config.ts        # Config query/mutation hooks (TanStack Query)
│       │   └── use-mobile.ts        # Mobile breakpoint detection
│       │
│       ├── lib/
│       │   ├── api-client.ts        # ConfigAPIClient — typed API client for config endpoints
│       │   ├── auth.ts              # Discord OAuth2 auth functions (getAvatarUrl, etc.)
│       │   ├── default-config.ts    # Default config values
│       │   ├── react-query.ts       # TanStack Query setup
│       │   ├── types.ts             # Shared TypeScript types
│       │   └── utils.ts             # cn() utility
│       │
│       └── integrations/tanstack-query/  # Query devtools + provider
│
├── tools/
│   └── music_cli.py                 # CLI for testing music service offline
│
└── emojis/                          # Emoji images for morning messages and now-playing embeds
```

---

## Architecture & Data Flow

### Startup Sequence (`main.py`)

```
main.py:
  1. Load YAML config → ConfigService.initialize()
  2. Start config file watcher (reloads on YAML changes)
  3. Create Juno(client) with all intents
  4. Juno.setup_hook():
     a. Initialize MongoDB services (image limits, morning configs, chat, memory)
     b. Start memory extraction background loops
     c. JunoSlash.load_commands() → registers all slash commands
     d. load_cogs() → auto-discovers and loads bot/cogs/*.py
     e. Start WebSocket server for music dashboard (port 8001)
  5. client.start(token)
```

### Message Processing Flow (`bot/juno.py:144 on_message`)

```
User sends message
  → Skip if from self
  → Load guild config from MongoDB
  → Skip if blocked bot or global block list
  → Enqueue for memory extraction (background)
  → Check auto-delete rules (e.g., filtered words → "L + RATIO")
  → Check if bot is @mentioned or replied to bot
  → Cooldown check (20s default, configurable)
  → AiOrchestrator.detect_intent()
     → chat intent → build context → gateway.complete() → respond + save to chat DB
     → image_generation intent → check limits → generate/edit image → respond
```

### AI Gateway (`bot/services/ai/gateway/`)

A provider-agnostic abstraction layer. All LLM calls route through `MeshGateway`:

| Method | Purpose |
|--------|---------|
| `complete(request, credentials)` | Non-streaming completion |
| `stream(request, credentials)` | Streaming completion (yields chunks) |
| `get_models(provider, credentials)` | List available models |
| `get_all_models(credentials_map)` | Concurrent model listing across providers |

**Providers:**
- **OpenRouter** — `openrouter_provider.py` — proxies to 200+ models (OpenAI, Anthropic, Google, etc.)
- **Ollama** — `ollama_provider.py` — local models via Ollama API

**Key pattern:** Credentials are never stored in the gateway. Callers fetch API keys from config/Database and pass them in. The gateway only resolves and forwards.

---

## Features

### 1. AI Chat (`bot/juno.py:219 _handle_chat_intent`)

- Triggered by @mentioning the bot or replying to its messages
- Intent detection via `AiOrchestrator` classifies message as `chat` or `image_generation`
- Builds conversation context from Discord message thread (reply chain + recent messages)
- Supports image attachments in chat — auto-detects vision-capable models, falls back to Gemini if needed
- Memories about conversation participants are injected into system prompt
- Responses saved to MongoDB chat thread for future context
- `/chat` slash command for explicit LLM queries

### 2. Image Generation (`bot/services/ai/image_generation_service.py`)

- "Mention + prompt" triggers image generation (via intent detection)
- Uses OpenRouter to call model configured in `aiConfig.imageGeneration.preferredModel`
- **Editing:** If the user attaches images alongside the mention, the bot edits/combines them
- **Prompt boosting:** Optional — enhances user prompts with detail before generation
- **Quota system:** Daily per-user limits tracked in MongoDB (`MongoImageLimitService`)
- `/image_stats` — check remaining daily quota
- `/image_admin` — admin subcommands: reset limits, set per-user/guild limits

### 3. Real-Time Voice (`bot/cogs/real_time_voice_cog.py`)

- Uses OpenAI Realtime API for bidirectional audio
- Four-step flow: `/voice_join` → `/voice_start` → conversation → `/voice_stop` → `/voice_leave`
- Audio pipeline: Discord 48kHz stereo → OpenAI 24kHz mono (sending), reverse (receiving)
- Uses `discord-ext-voice-recv` for voice receive
- `AudioProcessor` handles sample rate and channel conversion via numpy
- Per-guild session management with background playback + listen tasks
- Auto-cleanup on bot disconnect or empty channel

### 4. Music Player (`bot/cogs/music.py`, `bot/services/music/`)

- YouTube audio via yt-dlp + FFmpeg
- Priority queue with `put_front` for instant plays
- Audio filters: nightcore, bass boost, vaporwave, 8D, karaoke, etc.
- Seek to position, pause/resume, skip
- Now-playing embeds with progress bar
- **WebSocket dashboard** (`music_websocket_service.py`) — real-time state broadcast to frontend
- CLI testing tool at `tools/music_cli.py`

### 5. User Memory System (`docs/memory-system.md` for full details)

- LLM-driven extraction from all server messages (not just @mentions)
- Two background loops: main (20min, all categories) + mood (5min, mood only)
- Per-user in-memory message buffering → LLM extraction → MongoDB storage
- Category-based TTL retention (identity=permanent, mood=7 days)
- Memories injected into system prompt during chat for personalization
- `/memories` command: view own, admin add/remove/list/clear/extract

### 6. Scheduled Morning Messages (`bot/cogs/scheduler.py`)

- Per-guild configurable time and channel
- AI-generated motivational message via LLM at scheduled time
- Randomized emoji for visual flair
- Timezone-aware scheduling with 30-second check loop

### 7. Web Dashboard (`frontend/`)

- Discord OAuth2 login
- Guild selector (lists bot's guilds)
- **Config page** (`_main/config.tsx`): full guild configuration — AI provider, models, cooldowns, block lists, image settings, memory settings, etc.
- **Music page** (`_main/music.tsx`): real-time WebSocket-powered music player with queue, controls, filters
- Theme system: dark/light, 4 base themes, 18 accent colors

### 8. Configuration API (`bot/api/api.py`)

- FastAPI server, auto-started via Docker (separate container)
- Endpoints:
  - `GET /health` — health check
  - `GET /config` — get guild config
  - `PATCH /config` — update guild config
  - `POST /config/reload` — reload from MongoDB
  - `PATCH /config/ai-provider` — change AI provider
  - `POST /config/admins`, `DELETE /config/admins/{id}` — admin management
  - `GET /config/models` — list available models from provider
  - `GET /config/version` — config version
  - `GET /guilds` — list bot guilds
- Auth via `X-Admin-Key` header + `X-Guild-ID` header

---

## Configuration

### Secrets (`config/base_config.yaml` — matching `config.sample.yaml`)

```yaml
devDiscordToken: ""
prodDiscordToken: ""
mongoUri: ""
mongoDbName: ""
mongoConfigCollectionName: ""
encryptionKey: ""
environment: "dev"
```

### Dynamic Config (`bot/services/config_service.py` — `DynamicConfig` model)

Stored per-guild in MongoDB. Key fields:

| Field | Type | Description |
|-------|------|-------------|
| `guildId` | str | Discord guild ID |
| `adminIds` | list[str] | User IDs with admin access |
| `invisible` | bool | Bot disappears when true |
| `aiConfig` | AIConfig | All AI provider/model settings |
| `mentionCooldown` | int | Seconds between @mention responses (default 20) |
| `cooldownBypassList` | list[str] | Users exempt from cooldown |
| `globalBlockList` | list[str] | Globally blocked user IDs |
| `allowedBotsToRespondTo` | list[str] | Bot IDs the bot will reply to |
| `deleteUserMessages` | object | Auto-delete rules (regex + response) |
| `memoryConfig` | MemoryConfig | Memory extraction settings |
| `imageGeneration` | object | Image model and prompt boosting |

---

## Decorators

All slash commands use standardized decorators from `bot/utils/decarators/`:

| Decorator | File | Purpose |
|-----------|------|---------|
| `@log_command_usage()` | `command_logging.py` | Logs command name, user, guild, and args |
| `@is_admin()` | `admin_check.py` | Only users in `adminIds` can run |
| `@is_globally_blocked()` | `global_block_check.py` | Blocks users in `globalBlockList` |
| `@require_voice_channel()` | `voice_check.py` | Ensures user is in a voice channel |

---

## Running Locally

```bash
# Install dependencies
make install
# OR: poetry install && cd frontend && npm install

# Run bot
make bot
# OR: poetry run python main.py

# Run config API
make api
# OR: poetry run uvicorn bot.api.api:app --host 0.0.0.0 --port 5001 --reload

# Run frontend
make frontend
# OR: cd frontend && npm run dev
```

### Docker Compose

```bash
docker compose up -d
# Services: bruh-bot-dev, bruh-bot-prod, config-api-dev, config-api-prod,
#            bruh-bot-frontend-dev, bruh-bot-frontend-prod
```

---

## Key Design Patterns

1. **Per-guild config** — all behavior is configurable per Discord guild via MongoDB, with the ConfigService abstracting YAML secrets vs. dynamic data.

2. **Service dependency injection** — Instantiated in `Juno.__init__()`, keyed by bot object. Every service is a dedicated class within `bot/services/`.

3. **Provider abstraction** — The AI Gateway normalizes all LLM calls across providers into a single `NormalizedRequest`/`NormalizedResponse` interface.

4. **Thread-safe async** — The bot uses `on_message` for passive responses and slash commands for explicit ones. Cooldowns prevent spam, global block list prevents abuse.

5. **MongoDB as dynamic store** — Config, chat history, memories, image limits, and morning schedules are all in MongoDB. This enables the web dashboard and cross-restart persistence.

6. **WebSocket for real-time state** — Music player state is broadcast via WebSocket to the frontend dashboard for live updates.