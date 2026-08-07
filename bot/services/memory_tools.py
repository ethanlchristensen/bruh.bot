import logging
from typing import TYPE_CHECKING

from bot.services.mongo_memory_service import VALID_CATEGORIES

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

MEMORY_TOOL_SCHEMAS = [
    {
        "name": "search_memories",
        "description": "Search existing user memories semantically. Always call this BEFORE adding new memories to check for duplicates or existing knowledge about the user. Provide a natural language query describing what you want to find.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query to find semantically similar memories.",
                },
                "user_id": {
                    "type": "number",
                    "description": "Optional: filter to this user's memories only. Omit to search across all users in the conversation.",
                },
                "category": {
                    "type": "string",
                    "enum": VALID_CATEGORIES,
                    "description": "Optional: filter to a specific memory category.",
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum results to return (default 10, max 20).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_user_memories",
        "description": "Get ALL current memories for a specific user. Use this to get a complete picture of what you already know about someone before making changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "number",
                    "description": "Discord user ID of the person whose memories to retrieve.",
                },
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "add_memory",
        "description": "Add a new memory about a user. Call search_memories first to check if a similar memory already exists — if it does, use update_memory instead.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "number",
                    "description": "Discord user ID of the person this memory is about.",
                },
                "memory": {
                    "type": "string",
                    "description": "The memory text. Should be a concise, specific statement in third person (e.g. 'loves pineapple on pizza', 'is a software engineer').",
                },
                "category": {
                    "type": "string",
                    "enum": VALID_CATEGORIES,
                    "description": "Memory category. identity/trait/relationship are permanent; preference/fact expire in 90 days; opinion 30 days; mood 7 days.",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "How confident you are in this memory (0.0-1.0). Explicit statements = 0.9+, implied = 0.5-0.7.",
                },
                "target_username": {
                    "type": "string",
                    "description": "For relationship memories: the display name of the person this memory references. Must match a name from the KNOWN USERS list.",
                },
                "source_message_id": {
                    "type": "number",
                    "description": "Optional: the msg: ID from the transcript where this memory was derived.",
                },
            },
            "required": ["user_id", "memory", "category", "confidence"],
        },
    },
    {
        "name": "update_memory",
        "description": "Update an existing memory. Use this when a fact has changed or you want to refine/strengthen an existing observation.",
        "parameters": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "The ID of the existing memory to update (from search/get results).",
                },
                "new_memory": {
                    "type": "string",
                    "description": "The new/updated memory text. Omit to keep the existing text and only update other fields.",
                },
                "category": {
                    "type": "string",
                    "enum": VALID_CATEGORIES,
                    "description": "Optional: change the category.",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Optional: update confidence score.",
                },
            },
            "required": ["memory_id"],
        },
    },
    {
        "name": "remove_memory",
        "description": "Delete a memory that is contradicted by recent messages or clearly no longer true.",
        "parameters": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "The ID of the memory to delete (from search/get results).",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief reason why this memory is being removed (e.g. 'contradicted by: user said they now hate Python').",
                },
            },
            "required": ["memory_id", "reason"],
        },
    },
]


class MemoryToolExecutor:
    def __init__(
        self,
        bot: "BruhBot",
        guild_id: int,
        valid_user_ids: set[int],
        id_to_users: dict[str, str],
        users_to_id: dict[str, str],
        mem_cfg,
    ):
        self.bot = bot
        self.guild_id = guild_id
        self.valid_user_ids = valid_user_ids
        self.id_to_users = id_to_users
        self.users_to_id = users_to_id
        self.mem_cfg = mem_cfg
        self.logger = logging.getLogger(__name__)
        self._stats = {
            "total_calls": 0,
            "search_calls": 0,
            "get_calls": 0,
            "add_calls": 0,
            "update_calls": 0,
            "remove_calls": 0,
            "errors": 0,
            "deduped_adds": 0,
        }

    def reset_stats(self):
        self._stats = dict.fromkeys(self._stats, 0)

    def _is_bot_user(self, user_id: int) -> bool:
        return bool(self.bot.user and user_id == self.bot.user.id)

    async def execute(self, name: str, arguments: dict) -> dict:
        self._stats["total_calls"] += 1
        handler = getattr(self, f"_handle_{name}", None)
        if not handler:
            self._stats["errors"] += 1
            return {"error": f"Unknown tool: {name}"}

        try:
            return await handler(arguments)
        except Exception as e:
            self._stats["errors"] += 1
            self.logger.exception(f"Error executing tool {name}")
            return {"error": str(e)}

    async def _handle_search_memories(self, args: dict) -> dict:
        self._stats["search_calls"] += 1
        query = args.get("query", "").strip()
        if not query:
            return {"error": "query is required"}

        user_id = args.get("user_id")
        user_ids = None
        if user_id is not None:
            uid = int(user_id)
            if self._is_bot_user(uid):
                return {"error": "Bot memories cannot be accessed"}
            if uid not in self.valid_user_ids:
                return {"error": f"user_id {uid} is not in the current conversation"}
            user_ids = [uid]

        category = args.get("category")
        categories = None
        if category is not None:
            if category not in VALID_CATEGORIES:
                return {"error": f"Invalid category: {category}. Valid: {VALID_CATEGORIES}"}
            categories = [category]

        limit = min(int(args.get("limit", 10)), 20)

        embedding = await self.bot.embedding_service.embed_one(query, self.guild_id)
        if embedding is None:
            return {"error": "Failed to generate query embedding"}

        results = await self.bot.memory_service.search_memories_semantic(
            guild_id=self.guild_id,
            query_embedding=embedding,
            user_ids=user_ids,
            categories=categories,
            limit=limit,
            min_score=self.mem_cfg.dedupeThreshold * 0.4,
        )

        return {
            "count": len(results),
            "memories": [
                {
                    "memory_id": m["_id"],
                    "user_id": m["user_id"],
                    "memory": m["memory"],
                    "category": m["category"],
                    "confidence": m["confidence"],
                    "relevance_score": round(m.get("score", 0), 3),
                }
                for m in results
            ],
        }

    async def _handle_get_user_memories(self, args: dict) -> dict:
        self._stats["get_calls"] += 1
        user_id = int(args.get("user_id", 0))
        if not user_id:
            return {"error": "user_id is required"}
        if self._is_bot_user(user_id):
            return {"error": "Bot memories cannot be accessed"}
        if user_id not in self.valid_user_ids:
            return {"error": f"user_id {user_id} is not in the current conversation"}

        memories = await self.bot.memory_service.get_memories_for_user(
            guild_id=self.guild_id,
            user_id=user_id,
            limit=200,
        )

        return {
            "user_id": user_id,
            "count": len(memories),
            "memories": [
                {
                    "memory_id": m["_id"],
                    "memory": m["memory"],
                    "category": m["category"],
                    "confidence": m["confidence"],
                }
                for m in memories
            ],
        }

    async def _handle_add_memory(self, args: dict) -> dict:
        self._stats["add_calls"] += 1
        user_id = int(args.get("user_id", 0))
        memory_text = args.get("memory", "").strip()
        category = args.get("category", "fact")
        confidence = float(args.get("confidence", 0.5))

        if not user_id:
            return {"error": "user_id is required"}
        if self._is_bot_user(user_id):
            return {"error": "Bot memories cannot be created"}
        if user_id not in self.valid_user_ids:
            return {"error": f"user_id {user_id} is not in the current conversation"}
        if not memory_text:
            return {"error": "memory text is required"}
        if category not in VALID_CATEGORIES:
            return {"error": f"Invalid category: {category}"}
        if category == "admin":
            return {"error": "AI cannot create admin-category memories"}
        confidence = max(0.0, min(1.0, confidence))

        target_user_id = None
        if category == "relationship":
            target_username = args.get("target_username", "").strip()
            if target_username:
                resolved = self.users_to_id.get(target_username)
                if resolved:
                    target_user_id = int(resolved)

        source_msg_id = args.get("source_message_id")
        if source_msg_id is not None:
            try:
                source_msg_id = int(source_msg_id)
            except (ValueError, TypeError):
                source_msg_id = None

        embedding = await self.bot.embedding_service.embed_one(memory_text, self.guild_id)
        model = self.mem_cfg.embeddingModel

        if embedding is not None and self.mem_cfg.dedupeThreshold > 0:
            existing = await self.bot.memory_service.search_memories_semantic(
                guild_id=self.guild_id,
                query_embedding=embedding,
                user_ids=[user_id],
                limit=3,
                min_score=self.mem_cfg.dedupeThreshold,
            )
            if existing:
                best = existing[0]
                self._stats["deduped_adds"] += 1
                await self.bot.memory_service.update_memory(
                    memory_id=best["_id"],
                    guild_id=self.guild_id,
                    new_memory=memory_text,
                    category=category,
                    confidence=confidence,
                    embedding=embedding,
                    embedding_model=model,
                )
                self.logger.info(f"Deduped add → updated memory '{memory_text[:50]}...' (was: '{best['memory'][:50]}...', score={best.get('score', 0):.3f})")
                return {
                    "ok": True,
                    "deduped": True,
                    "updated_memory_id": best["_id"],
                    "original_memory": best["memory"],
                }

        source_msg_id = source_msg_id or args.get("source_message_id")
        if source_msg_id is not None:
            try:
                source_msg_id = int(source_msg_id)
            except (ValueError, TypeError):
                source_msg_id = None

        memory_id = await self.bot.memory_service.save_memory(
            guild_id=self.guild_id,
            user_id=user_id,
            memory=memory_text,
            category=category,
            confidence=confidence,
            created_by="ai",
            target_user_id=target_user_id,
            source_message_id=source_msg_id,
            embedding=embedding,
            embedding_model=model,
        )

        return {"ok": True, "memory_id": memory_id}

    async def _handle_update_memory(self, args: dict) -> dict:
        self._stats["update_calls"] += 1
        memory_id = args.get("memory_id", "").strip()
        if not memory_id:
            return {"error": "memory_id is required"}

        existing = await self.bot.memory_service.get_memory_by_id(memory_id, self.guild_id)
        if not existing:
            return {"error": f"Memory {memory_id} not found"}

        user_id = existing.get("user_id")
        if user_id and self._is_bot_user(int(user_id)):
            return {"error": "Bot memories cannot be updated"}
        if user_id and user_id not in self.valid_user_ids:
            return {"error": f"Memory belongs to user {user_id} who is not in the current conversation"}

        new_memory = args.get("new_memory")
        category = args.get("category")
        confidence = args.get("confidence")

        if category and category not in VALID_CATEGORIES:
            return {"error": f"Invalid category: {category}"}

        embedding = None
        model = None
        if new_memory:
            new_memory = str(new_memory).strip()
            if new_memory:
                embedding = await self.bot.embedding_service.embed_one(new_memory, self.guild_id)
                model = self.mem_cfg.embeddingModel

        success = await self.bot.memory_service.update_memory(
            memory_id=memory_id,
            guild_id=self.guild_id,
            new_memory=new_memory or None,
            category=category,
            confidence=float(confidence) if confidence else None,
            embedding=embedding,
            embedding_model=model,
        )

        return {"ok": success}

    async def _handle_remove_memory(self, args: dict) -> dict:
        self._stats["remove_calls"] += 1
        memory_id = args.get("memory_id", "").strip()
        reason = args.get("reason", "").strip()

        if not memory_id:
            return {"error": "memory_id is required"}

        existing = await self.bot.memory_service.get_memory_by_id(memory_id, self.guild_id)
        if not existing:
            return {"error": f"Memory {memory_id} not found"}

        user_id = existing.get("user_id")
        if user_id and self._is_bot_user(int(user_id)):
            return {"error": "Bot memories cannot be removed"}
        if user_id and user_id not in self.valid_user_ids:
            return {"error": f"Memory belongs to user {user_id} who is not in the current conversation"}

        success = await self.bot.memory_service.delete_memory(
            memory_id=memory_id,
            guild_id=self.guild_id,
        )

        if success:
            self.logger.info(f"Tool removed memory {memory_id}: {reason}")

        return {"ok": success}
