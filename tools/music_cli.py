import asyncio
import json
import msvcrt  # Built-in on Windows
import sys
import time

import websockets
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


class MusicCLI:
    def __init__(self, guild_id: str, host: str = "localhost", port: int = 8001):
        self.guild_id = guild_id
        self.uri = f"ws://{host}:{port}/ws/{guild_id}"
        self.state = {}
        self.running = True
        self.input_buffer = ""
        self.last_msg = ""
        self.last_update_time = 0

    def create_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="input", size=3),
            Layout(name="header", size=3),
            Layout(name="body"),
        )
        layout["body"].split_row(
            Layout(name="now_playing", ratio=1),
            Layout(name="queue", ratio=2),
        )
        return layout

    def get_input_panel(self) -> Panel:
        return Panel(Text(f"Action > {self.input_buffer}█", style="bold cyan"), title="Command Input (Type and press Enter)", border_style="bright_blue")

    def get_header(self) -> Panel:
        return Panel(Text(f"Bruh Bot Music CLI - Guild: {self.guild_id} | {self.last_msg}", justify="center", style="bold magenta"), style="white on blue")

    def get_now_playing(self) -> Panel:
        if not self.state or not self.state.get("current_song"):
            return Panel(Text("Nothing is currently playing.", style="italic grey50"), title="Now Playing")

        song = self.state["current_song"]
        status = "PAUSED" if self.state.get("is_paused") else "PLAYING"

        content = Text()
        content.append(f"{song['title']}\n", style="bold yellow")
        content.append(f"By: {song['author']}\n", style="cyan")

        duration = int(song.get("duration", 0))
        pos = int(self.state.get("position", 0))

        # Interpolate position if playing
        if not self.state.get("is_paused") and self.state.get("is_playing") and self.last_update_time > 0:
            elapsed = time.time() - self.last_update_time
            pos += int(elapsed)
            if duration > 0:
                pos = min(pos, duration)

        content.append(f"\nStatus: {status}\n")
        content.append(f"Position: {pos // 60}:{pos % 60:02d} / {duration // 60}:{duration % 60:02d}\n")
        content.append(f"Requested by: {song.get('requested_by', 'Unknown')}")

        return Panel(content, title="Now Playing", border_style="green")

    def get_queue_table(self) -> Table:
        table = Table(title="Music Queue", expand=True)
        table.add_column("Idx", justify="right", style="dim", width=4)
        table.add_column("Title", style="white")
        table.add_column("Author", style="cyan")
        table.add_column("Duration", justify="right", style="magenta")

        if not self.state or not self.state.get("queue"):
            table.add_row("-", "Queue is empty.", "-", "-")
        else:
            for item in self.state["queue"][:10]:  # Limit to 10 for space
                d = int(item.get("duration", 0))
                duration_str = f"{d // 60}:{d % 60:02d}"
                table.add_row(str(item.get("index", "?")), item["title"][:40], item["author"][:20], duration_str)
        return table

    async def run(self):
        try:
            async with websockets.connect(self.uri) as websocket:
                layout = self.create_layout()
                with Live(layout, refresh_per_second=10, screen=True) as live:
                    while self.running:
                        # 1. Handle WebSocket Messages (Non-blocking)
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                            data = json.loads(message)
                            if data["type"] in ["initial_state", "state_update"]:
                                self.state = data["data"]
                                self.last_update_time = time.time()
                            elif data["type"] == "error":
                                self.last_msg = f"Error: {data['message']}"
                        except TimeoutError:
                            pass

                        # 2. Handle Keyboard Input (Non-blocking using msvcrt)
                        if msvcrt.kbhit():
                            char = msvcrt.getch()
                            if char == b"\r":  # Enter
                                cmd_line = self.input_buffer.strip()
                                if cmd_line:
                                    await self.execute_command(websocket, cmd_line)
                                self.input_buffer = ""
                            elif char == b"\x08":  # Backspace
                                self.input_buffer = self.input_buffer[:-1]
                            elif char == b"\x03":  # Ctrl+C
                                self.running = False
                            else:
                                try:
                                    self.input_buffer += char.decode("utf-8")
                                except:
                                    pass

                        # 3. Update Layout
                        layout["input"].update(self.get_input_panel())
                        layout["header"].update(self.get_header())
                        layout["now_playing"].update(self.get_now_playing())
                        layout["queue"].update(self.get_queue_table())

                        await asyncio.sleep(0.01)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            time.sleep(2)

    async def execute_command(self, websocket, cmd_line):
        parts = cmd_line.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "exit":
            self.running = False
            return

        msg = None
        if cmd == "add":
            msg = {"type": "add", "data": {"query": args, "requested_by": "CLI"}}
            self.last_msg = f"Adding: {args}"
        elif cmd == "remove":
            try:
                msg = {"type": "remove", "data": {"index": int(args)}}
                self.last_msg = f"Removed index {args}"
            except ValueError:
                self.last_msg = "Remove requires index number"
        elif cmd in ["skip", "pause", "resume"]:
            msg = {"type": cmd}
            self.last_msg = f"Command: {cmd}"
        elif cmd == "seek":
            try:
                msg = {"type": "seek", "data": {"seconds": int(args)}}
                self.last_msg = f"Seeked to {args}s"
            except ValueError:
                self.last_msg = "Seek requires seconds"

        if msg:
            await websocket.send(json.dumps(msg))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python music_cli.py <guild_id> [host] [port]")
        sys.exit(1)

    guild_id = sys.argv[1]
    host = sys.argv[2] if len(sys.argv) > 2 else "localhost"
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 8001

    cli = MusicCLI(guild_id, host, port)
    asyncio.run(cli.run())
