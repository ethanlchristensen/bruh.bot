import asyncio
import json
import logging
import time
import traceback
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .types import FilterPreset

if TYPE_CHECKING:
    from bot.juno import Juno

logger = logging.getLogger(__name__)


class MusicWebSocketService:
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.app = FastAPI()
        self._setup_routes()

    def _setup_routes(self):
        @self.app.websocket("/ws/{guild_id}")
        async def websocket_endpoint(websocket: WebSocket, guild_id: str):
            try:
                await self.connect(websocket, guild_id)
                try:
                    while True:
                        data = await websocket.receive_text()
                        try:
                            message = json.loads(data)
                            await self.handle_incoming_message(guild_id, message)
                        except json.JSONDecodeError:
                            logger.error(f"Invalid JSON received from WS in guild {guild_id}")
                        except Exception as e:
                            logger.error(f"Error handling WS message in guild {guild_id}: {e}")
                            logger.error(traceback.format_exc())
                except WebSocketDisconnect:
                    self.disconnect(websocket, guild_id)
                    logger.info(f"WebSocket disconnected for guild {guild_id}")
            except Exception as e:
                logger.error(f"Error in websocket_endpoint for guild {guild_id}: {e}")
                logger.error(traceback.format_exc())
                self.disconnect(websocket, guild_id)

    async def connect(self, websocket: WebSocket, guild_id: str):
        await websocket.accept()
        str_guild_id = str(guild_id)
        if str_guild_id not in self.active_connections:
            self.active_connections[str_guild_id] = []
        self.active_connections[str_guild_id].append(websocket)
        logger.info(f"WebSocket connected for guild {str_guild_id}")

        # Send current state
        state = await self.get_guild_state(str_guild_id)
        await websocket.send_json({"type": "initial_state", "data": state})

    def disconnect(self, websocket: WebSocket, guild_id: str):
        str_guild_id = str(guild_id)
        if str_guild_id in self.active_connections:
            if websocket in self.active_connections[str_guild_id]:
                self.active_connections[str_guild_id].remove(websocket)
            if not self.active_connections[str_guild_id]:
                del self.active_connections[str_guild_id]

    async def broadcast(self, guild_id: str | int, message: dict[str, Any]):
        str_guild_id = str(guild_id)
        if str_guild_id in self.active_connections:
            # Create a list of tasks for sending messages
            tasks = [connection.send_json(message) for connection in self.active_connections[str_guild_id]]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def get_guild_state(self, guild_id: str | int) -> dict[str, Any]:
        str_guild_id = str(guild_id)
        try:
            try:
                gid = int(guild_id)
            except ValueError:
                return {
                    "guild_id": str_guild_id,
                    "is_playing": False,
                    "is_paused": False,
                    "current_song": None,
                    "queue": [],
                    "position": 0,
                    "error": f"Invalid Guild ID: {str_guild_id}",
                }

            guild = self.bot.get_guild(gid)
            if not guild:
                return {
                    "guild_id": str_guild_id,
                    "is_playing": False,
                    "is_paused": False,
                    "current_song": None,
                    "queue": [],
                    "position": 0,
                    "error": "Guild not found (bot may not be in this guild)",
                }

            player = self.bot.music_queue_service.get_player(guild)

            # Build queue list
            queue_list = []
            # Accessing private _queue of asyncio.Queue (PriorityMusicQueue)
            # This is a bit hacky but needed to see the queue without consuming it
            if player and hasattr(player, "queue") and player.queue:
                for i, item in enumerate(list(player.queue._queue)):
                    try:
                        # PriorityMusicQueue does not use tuples like PriorityQueue, it uses appendleft
                        item_dict = item.to_ui_dict()
                        item_dict["index"] = i
                        queue_list.append(item_dict)
                    except AttributeError as e:
                        logger.error(f"Error calling to_ui_dict on queue item {type(item)}: {e}")

            current_pos = 0
            is_playing = False
            is_paused = False
            current_song = None

            if player:
                is_playing = player.is_playing()
                is_paused = player.is_paused()
                current_song = player.current.to_ui_dict() if player.current else None

                if player.played_at:
                    if player.is_paused() and player.paused_at:
                        current_pos = int(player.paused_at - player.played_at)
                    else:
                        current_pos = int(time.time() - player.played_at)

            return {
                "guild_id": str_guild_id,
                "is_playing": is_playing,
                "is_paused": is_paused,
                "current_song": current_song,
                "queue": queue_list,
                "position": current_pos,
            }
        except Exception as e:
            logger.error(f"Error getting guild state for {str_guild_id}: {e}")
            logger.error(traceback.format_exc())
            return {
                "guild_id": str_guild_id,
                "is_playing": False,
                "is_paused": False,
                "current_song": None,
                "queue": [],
                "position": 0,
                "error": f"Internal Server Error: {str(e)}",
            }

    async def handle_incoming_message(self, guild_id: str | int, message: dict[str, Any]):
        str_guild_id = str(guild_id)
        msg_type = message.get("type")
        payload = message.get("data", {})

        try:
            gid = int(guild_id)
        except ValueError:
            return

        guild = self.bot.get_guild(gid)
        if not guild:
            return

        player = self.bot.music_queue_service.get_player(guild)

        if msg_type == "skip":
            await player.skip()
        elif msg_type == "pause":
            await player.pause()
        elif msg_type == "resume":
            await player.resume()
        elif msg_type == "seek":
            seconds = payload.get("seconds", 0)
            await player.seek(seconds=seconds)
        elif msg_type == "add":
            query = payload.get("query")
            if query:
                # Use run_in_executor for blocking yt-dlp call
                loop = asyncio.get_event_loop()
                try:
                    info = await loop.run_in_executor(None, self.bot.audio_service.extract_info, query)
                    metadata = self.bot.audio_service.get_metadata(info)
                    metadata.requested_by = payload.get("requested_by", "Web API")

                    # Handle filter preset
                    filter_val = payload.get("filter_preset")
                    if filter_val:
                        metadata.filter_preset = FilterPreset.from_value(filter_val)

                    # If we have a text channel from the player's last song, use it
                    if player.current and player.current.text_channel:
                        metadata.text_channel = player.current.text_channel

                    await player.add(metadata)
                except Exception as e:
                    logger.error(f"Error adding song via WS: {e}")
                    await self.broadcast(str_guild_id, {"type": "error", "message": f"Failed to add song: {str(e)}"})
        elif msg_type == "remove":
            index = payload.get("index")
            if index is not None and 0 <= index < player.queue.qsize():
                # Convert deque to list, remove, then back to deque
                queue_items = list(player.queue._queue)
                queue_items.pop(index)
                player.queue._queue.clear()
                player.queue._queue.extend(queue_items)
                # We need to manually adjust unfinished_tasks if we removed an item
                player.queue._unfinished_tasks -= 1
                await player._broadcast_state()

        # After any change, broadcast the new state (some methods already broadcast, but safe to do here too)
        new_state = await self.get_guild_state(str_guild_id)
        await self.broadcast(str_guild_id, {"type": "state_update", "data": new_state})

    async def start_server(self, host: str = "0.0.0.0", port: int = 8000):
        import uvicorn

        config = uvicorn.Config(self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        asyncio.create_task(server.serve())
        logger.info(f"Music WebSocket API started on {host}:{port}")
