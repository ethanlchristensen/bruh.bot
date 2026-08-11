#!/usr/bin/env python3
"""
Card Set Generator CLI — direct-to-Mongo.
=========================================

Generates trading card names, art, and metadata and publishes directly to MongoDB GridFS.
No local asset files required for normal operation.

Usage:
  poetry run python tools/card_gen.py wizard --env dev
  poetry run python tools/card_gen.py resume <set_id> --env dev
  poetry run python tools/card_gen.py status <set_id> --env dev
  poetry run python tools/card_gen.py publish <set_id> --env dev
  poetry run python tools/card_gen.py list --env dev
  poetry run python tools/card_gen.py export <set_id> --output ./exports --env dev
"""

import argparse
import asyncio
import base64
import json
import logging
import os
import sys
import tempfile
import webbrowser
from io import BytesIO
from pathlib import Path

from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.services.ai.gateway.gateway import get_mesh_gateway
from bot.services.ai.gateway.schemas.request import Message, MessagePart, NormalizedRequest
from bot.services.ai.gateway.utils import parse_data_url
from tools.trading_card_publisher import TradingCardPublisher

console = Console()
logger = logging.getLogger("card_gen")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

CARD_IMAGE_MODEL = "google/gemini-3.1-flash-image"
CARD_TEXT_MODEL = "deepseek/deepseek-v4-flash"
CARD_ASPECT_RATIO = "3:4"

RARITY_COUNTS = {"basic": 14, "common": 12, "rare": 9, "epic": 6, "legendary": 4, "diamond": 3, "platinum": 2}


# ── API utilities ──
async def resolve_api_key(env: str) -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    config_path = Path("config/base_config.yaml")
    if not config_path.exists():
        console.print("[red]No API key found. Set OPENROUTER_API_KEY env var.[/red]")
        sys.exit(1)
    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(cfg["mongoUri"])
    doc = await client[cfg["mongoDbName"]].config.find_one()
    if doc:
        ai = doc.get("aiConfig", {})
        for p in ("openrouter", "mesh_router"):
            k = ai.get(p, {}).get("apiKey", "")
            if k:
                if k.startswith("gAAAA"):
                    try:
                        from cryptography.fernet import Fernet
                        k = Fernet(cfg.get("encryptionKey", "").encode()).decrypt(k.encode()).decode()
                    except Exception:
                        pass
                client.close()
                return k
    client.close()
    console.print("[red]No API key found in MongoDB config.[/red]")
    sys.exit(1)


async def generate_image(prompt: str, api_key: str, reference_image: Image.Image | None = None) -> tuple[Image.Image | None, str]:
    parts = [MessagePart(type="text", text=prompt)]
    if reference_image:
        buf = BytesIO()
        reference_image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        parts.insert(0, MessagePart(type="image", url=f"data:image/png;base64,{b64}"))

    request = NormalizedRequest(
        provider="openrouter", model=CARD_IMAGE_MODEL,
        messages=[Message(role="user", parts=parts)],
        stream=False, modalities=["image", "text"],
        image_config={"aspect_ratio": CARD_ASPECT_RATIO},
    )
    response = await get_mesh_gateway().complete(request, credentials={"api_key": api_key})
    for part in response.parts:
        if part.type == "image" and part.content:
            data = part.content
            if data.startswith("data:image"):
                parsed = parse_data_url(data)
                if parsed:
                    mime, b64_data = parsed
                    fmt = "JPEG" if "jpeg" in mime or "jpg" in mime else "PNG"
                    return Image.open(BytesIO(base64.b64decode(b64_data))), fmt
            else:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(data) as resp:
                        ct = resp.headers.get("Content-Type", "")
                        fmt = "JPEG" if "jpeg" in ct or "jpg" in ct else "PNG"
                        return Image.open(BytesIO(await resp.read())), fmt
    return None, "PNG"


async def generate_card_names(theme_name: str, theme_desc: str, rarity_themes: dict, api_key: str) -> list[dict] | None:
    sections = []
    for rarity in ["basic", "common", "rare", "epic", "legendary", "diamond", "platinum"]:
        count = RARITY_COUNTS[rarity]
        theme = rarity_themes.get(rarity, f"Cards of {rarity} tier.")
        sections.append(f"{rarity.upper()} ({count} cards): {theme}")

    prompt = f"""Generate {sum(RARITY_COUNTS.values())} trading card names and descriptions for a card set called "{theme_name}".

Theme description: {theme_desc}

Rarity tiers and what each represents:
{chr(10).join(sections)}

For EACH card, provide card number (1-50), name (2-4 words, evocative), rarity, and description (1-2 sentences, vivid).
Return ONLY valid JSON as a list: [{{"number": 1, "name": "Card Name", "rarity": "basic", "description": "Vivid description."}}, ...]
Start BASIC (1-14), COMMON (15-26), RARE (27-35), EPIC (36-41), LEGENDARY (42-45), DIAMOND (46-48), PLATINUM (49-50).
Platinum cards should be the ultimate chase cards. Each description must be unique."""

    request = NormalizedRequest(
        provider="openrouter", model=CARD_TEXT_MODEL,
        messages=[Message(role="user", parts=[MessagePart(type="text", text=prompt)])], stream=False,
    )
    response = await get_mesh_gateway().complete(request, credentials={"api_key": api_key})
    text = "".join(p.content for p in response.parts if p.type == "text")

    import re
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    cards = []
    for item in data:
        if isinstance(item, dict) and 1 <= item.get("number", 0) <= 50:
            cards.append({
                "number": item["number"],
                "name": str(item.get("name", "")),
                "rarity": str(item.get("rarity", "common")).lower(),
                "description": str(item.get("description", "")),
            })
    return cards if len(cards) >= 10 else None


# ── Card Set Generator ──
class CardSetGenerator:
    def __init__(self, env: str = "dev"):
        self.env = env
        self.api_key = ""
        self.pub = TradingCardPublisher(env=env)
        self.set_id = ""
        self.base_image = None

    async def connect(self):
        self.api_key = await resolve_api_key(self.env)
        await self.pub.connect()

    # ── Wizard ──
    async def wizard(self):
        console.print(Panel.fit("[bold cyan]Card Set Generator — Direct to Mongo[/bold cyan]\n\nDefine a theme, generate cards with AI, and publish directly to MongoDB.", title="bruh.bot Card Generator"))

        self.set_id = Prompt.ask("\n[bold]Set ID[/bold]", default="my_set").lower().replace(" ", "_")
        theme_name = Prompt.ask("[bold]Display name[/bold]", default=self.set_id.replace("_", " ").title())
        theme_desc = Prompt.ask("[bold]Theme description[/bold]", default="A mysterious collection of dark fantasy trading cards.")

        console.print("\n[bold]Define what each rarity tier represents:[/bold]")
        rarity_themes = {}
        for rarity in RARITY_COUNTS:
            default = self._default_rarity_desc(rarity)
            rarity_themes[rarity] = Prompt.ask(f"  [bold]{rarity.title()}[/bold] ({RARITY_COUNTS[rarity]} cards)", default=default)

        # Generate card names
        console.print("\n[cyan]Generating card names and descriptions with AI...[/cyan]")
        ai_cards = None
        while not ai_cards or len(ai_cards) < 10:
            ai_cards = await generate_card_names(theme_name, theme_desc, rarity_themes, self.api_key)
            if not ai_cards or len(ai_cards) < 10:
                console.print("[red]AI generation returned too few cards.[/red]")
                if not Confirm.ask("Retry?", default=True):
                    return

        table = Table(title=f"Preview — {theme_name}")
        table.add_column("#", style="dim")
        table.add_column("Name")
        table.add_column("Rarity")
        table.add_column("Description", max_width=50)
        for c in ai_cards[:10]:
            table.add_row(str(c["number"]), c["name"], c["rarity"], c["description"][:50])
        if len(ai_cards) > 10:
            table.add_row("...", f"+{len(ai_cards) - 10} more", "", "")
        console.print(table)
        if not Confirm.ask("\nAccept?", default=True):
            return

        # Build card list
        cards = []
        for c in ai_cards:
            safe = c["name"].lower().replace(" ", "_").replace("'", "")
            cards.append({
                "card_id": f"{self.set_id}_{c['number']:03d}",
                "series_id": self.set_id,
                "number": c["number"],
                "name": c["name"],
                "rarity": c["rarity"],
                "description": c["description"],
                "art_path": f"{self.set_id}/{c['rarity']}_{safe}.png",
                "tradable": True,
            })

        # Generate base template
        base_prompt = self._build_base_prompt(theme_name, theme_desc)
        console.print("\n[cyan]Generating base template...[/cyan]")
        self.base_image, base_fmt = await generate_image(base_prompt, self.api_key)
        if not self.base_image:
            console.print("[red]Generation failed.[/red]")
            return

        # Save base template to GridFS
        buf = BytesIO()
        self.base_image.save(buf, format="PNG")
        base_bytes = buf.getvalue()
        await self.pub.upload_asset(f"{self.set_id}_base_template", base_bytes, replace=True)

        # Show for review
        tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        self.base_image.save(tf.name)
        console.print(f"[green]Base template saved to {tf.name}[/green]")
        console.print("[dim]Opening for review...[/dim]")
        webbrowser.open(tf.name)

        while True:
            choice = Prompt.ask("Options", choices=["approve", "retry", "cancel"], default="approve")
            if choice == "cancel":
                tf.close()
                os.unlink(tf.name)
                return
            if choice == "approve":
                break
            adj = Prompt.ask("What to change?", default="")
            if adj:
                base_prompt += f" {adj}"
            self.base_image, _ = await generate_image(base_prompt, self.api_key)
            if self.base_image:
                self.base_image.save(tf.name)
                buf = BytesIO()
                self.base_image.save(buf, format="PNG")
                await self.pub.upload_asset(f"{self.set_id}_base_template", buf.getvalue(), replace=True)
                console.print("[green]Updated.[/green]")
                webbrowser.open(tf.name)

        tf.close()
        os.unlink(tf.name)

        # Pack definitions
        console.print("\n[bold]Pack settings:[/bold]")
        std_price = int(Prompt.ask("  Standard pack price", default="350"))
        prem_price = int(Prompt.ask("  Premium pack price", default="1100"))
        packs = [
            {"pack_id": f"{self.set_id}_standard", "series_id": self.set_id, "name": f"{theme_name} Pack", "price": std_price, "cards_per_pack": 3, "guaranteed_rarity": None, "description": f"Standard pack from {theme_name}.", "released": False},
            {"pack_id": f"{self.set_id}_premium", "series_id": self.set_id, "name": f"{theme_name} Premium Pack", "price": prem_price, "cards_per_pack": 3, "guaranteed_rarity": "rare", "description": f"Premium pack from {theme_name}. Guaranteed Rare+.", "released": False},
        ]

        # Save set metadata to Mongo
        await self.pub.upsert_set(self.set_id, {
            "display_name": theme_name, "description": theme_desc,
            "base_prompt": base_prompt, "rarity_themes": rarity_themes,
            "status": "generating", "generation_model": CARD_IMAGE_MODEL,
            "version": 1,
        })
        for card in cards:
            card["asset_status"] = "pending"
            await self.pub.upsert_card(card)
        for pk in packs:
            await self.pub.upsert_pack(pk)
        console.print(f"[green]Set metadata saved to Mongo. {len(cards)} cards, {len(packs)} packs.[/green]")

        # Generate card art directly to GridFS
        if not Confirm.ask(f"\nGenerate all {len(cards)} cards now? This will take a while.", default=True):
            console.print(f"[yellow]Resume later: poetry run python tools/card_gen.py resume {self.set_id} --env {self.env}[/yellow]")
            return

        await self._generate_cards_direct(cards)

        # Mark complete
        await self.pub.upsert_set(self.set_id, {
            "display_name": theme_name, "description": theme_desc,
            "base_prompt": base_prompt, "rarity_themes": rarity_themes,
            "status": "ready", "generation_model": CARD_IMAGE_MODEL,
        })
        console.print(f"\n[bold green]Done! Publish with: poetry run python tools/card_gen.py publish {self.set_id} --env {self.env}[/bold green]")

    async def _generate_cards_direct(self, cards: list[dict]):
        total = len(cards)
        console.print(f"\n[bold]Generating {total} cards to GridFS...[/bold]")
        for i, card in enumerate(cards):
            doc = await self.pub.catalog_col.find_one({"card_id": card["card_id"]})
            if doc and doc.get("asset_status") == "ready":
                console.print(f"  [{i + 1}/{total}] [dim]{card['card_id']} already ready, skipping[/dim]")
                continue

            card["asset_status"] = "generating"
            await self.pub.upsert_card(card)

            prompt = card["description"]
            console.print(f"  [{i + 1}/{total}] [cyan]{card['card_id']} ({card['rarity']})...[/cyan]")

            try:
                image, _ = await generate_image(prompt, self.api_key, self.base_image)
                if image:
                    if image.mode != "RGBA":
                        image = image.convert("RGBA")
                    buf = BytesIO()
                    image.save(buf, format="PNG")
                    data = buf.getvalue()
                    sha = TradingCardPublisher.compute_sha256(data)
                    await self.pub.upload_asset(card["card_id"], data, checksum=sha, replace=True)
                    card["asset_status"] = "ready"
                    card["asset_sha256"] = sha
                    card["asset_content_type"] = "image/png"
                    card["asset_filename"] = f"{card['rarity']}_{card['name'].lower().replace(' ', '_').replace(chr(39), '')}.png"
                    await self.pub.upsert_card(card)
                    console.print("    [green]Uploaded[/green]")
                else:
                    card["asset_status"] = "failed"
                    card["asset_error"] = "No image returned"
                    await self.pub.upsert_card(card)
                    console.print("    [red]Failed[/red]")
            except Exception as e:
                card["asset_status"] = "failed"
                card["asset_error"] = str(e)[:200]
                card["asset_attempts"] = card.get("asset_attempts", 0) + 1
                await self.pub.upsert_card(card)
                console.print(f"    [red]{e}[/red]")

            await asyncio.sleep(1)

    # ── Resume ──
    async def resume(self, set_id: str, retry_failed: bool = False):
        self.set_id = set_id
        sd = await self.pub.get_set(set_id)
        if not sd:
            console.print(f"[red]Set '{set_id}' not found in Mongo.[/red]")
            return

        st = await self.pub.get_set_status(set_id)
        console.print(f"\n[bold]{st['display_name']}[/bold]")
        console.print(f"   Total: {st['total_cards']} | Ready: {st['ready']} | Pending: {st['pending']} | Failed: {st['failed']}")

        if st["failed"] > 0 and not retry_failed:
            console.print(f"  [yellow]{st['failed']} failed cards exist. Use --retry-failed to retry them.[/yellow]")

        statuses = ["pending"]
        if retry_failed:
            statuses.append("failed")
        cards = await self.pub.get_cards_by_status(set_id, *statuses)
        if not cards:
            if retry_failed:
                console.print("[green]Nothing to retry.[/green]")
            else:
                console.print("[green]All cards ready! Run publish if you haven't already.[/green]")
            return

        console.print(f"\n  Generating {len(cards)} cards ({', '.join(statuses)})...")

        # Load base template from GridFS
        base_data = await self.pub.get_asset_bytes(f"{set_id}_base_template")
        if base_data:
            self.base_image = Image.open(BytesIO(base_data))
            console.print("[green]Loaded base template from GridFS[/green]")
        else:
            console.print("[yellow]No base template in GridFS, generating without reference[/yellow]")

        await self._generate_cards_direct(cards)
        console.print(f"\n[green]Done. Check status: poetry run python tools/card_gen.py status {set_id} --env {self.env}[/green]")

    # ── Status ──
    async def status(self, set_id: str):
        s = await self.pub.get_set_status(set_id)
        if not s or s["total_cards"] == 0:
            console.print(f"[red]Set '{set_id}' not found or empty.[/red]")
            return
        console.print(f"\n[bold]{s['display_name']}[/bold]")
        console.print(f"Status: {s['status']} | Released: {'yes' if s['released'] else 'no'}")
        console.print(f"Cards: {s['total_cards']} total | {s['ready']} ready | {s['pending']} pending | {s['failed']} failed")
        if s["ready"] == s["total_cards"] and s["total_cards"] > 0:
            console.print(f"\n[green]All cards ready! Publish with: poetry run python tools/card_gen.py publish {set_id} --env {self.env}[/green]")

    # ── Publish ──
    async def publish(self, set_id: str):
        s = await self.pub.get_set_status(set_id)
        if s["ready"] < s["total_cards"]:
            console.print(f"[red]{s['ready']}/{s['total_cards']} cards ready. Generate all cards first, then publish.[/red]")
            return
        await self.pub.publish_set(set_id)
        await self.pub.packs_col.update_many({"set_id": set_id}, {"$set": {"released": True}})
        console.print(f"[green]Set '{s['display_name']}' published! Run /bruh-cards-admin reload in Discord.[/green]")

    # ── Promote ──
    async def promote(self, set_id: str, target_env: str):
        console.print(f"[yellow]Promoting '{set_id}' from {self.env} to {target_env}...[/yellow]")

        src = self.pub
        dst = TradingCardPublisher(env=target_env)
        await dst.connect()

        try:
            sd = await src.get_set(set_id)
            if not sd:
                console.print(f"[red]Set '{set_id}' not found in {self.env}.[/red]")
                return

            # Upsert set metadata
            await dst.upsert_set(set_id, {
                "display_name": sd["display_name"], "description": sd.get("description", ""),
                "base_prompt": sd.get("base_prompt", ""), "rarity_themes": sd.get("rarity_themes", {}),
                "status": sd.get("status", "ready"), "released": sd.get("released", False),
                "version": sd.get("version", 1), "generation_model": sd.get("generation_model", ""),
            })

            # Copy base template
            base = await src.get_asset_bytes(f"{set_id}_base_template")
            if base:
                await dst.upload_asset(f"{set_id}_base_template", base, replace=True)
                console.print("  Base template copied")

            # Copy cards
            cards = await src.get_all_cards(set_id)
            ready = 0
            for c in cards:
                await dst.upsert_card(c)
                if c.get("asset_status") == "ready":
                    art = await src.get_asset_bytes(c["card_id"])
                    if art:
                        ct = c.get("asset_content_type", "image/png")
                        await dst.upload_asset(c["card_id"], art, ct, replace=True)
                        ready += 1

            # Copy packs
            packs = await src.packs_col.find({"set_id": set_id}).to_list(length=50)
            for pk in packs:
                await dst.upsert_pack(pk)

            console.print(f"[green]Promoted {ready}/{len(cards)} cards + {len(packs)} packs to {target_env}.[/green]")
            console.print(f"  Run /bruh-cards-admin reload in Discord ({target_env} bot).")
        finally:
            await dst.close()
    async def archive(self, set_id: str):
        if not Confirm.ask(f"Archive set '{set_id}'? This hides it from players but preserves data.", default=False):
            return
        await self.pub.archive_set(set_id)
        console.print(f"[yellow]Set '{set_id}' archived.[/yellow]")

    # ── Export ──
    async def export_set(self, set_id: str, output_dir: str):
        out = Path(output_dir) / set_id
        out.mkdir(parents=True, exist_ok=True)

        sd = await self.pub.get_set(set_id)
        if not sd:
            console.print(f"[red]Set '{set_id}' not found.[/red]")
            return

        cards = await self.pub.get_all_cards(set_id)
        packs = await self.pub.packs_col.find({"set_id": set_id}).to_list(length=50)
        base = await self.pub.get_asset_bytes(f"{set_id}_base_template")

        exp_cards = []
        for c in cards:
            safe = c["name"].lower().replace(" ", "_").replace(chr(39), "")
            exp_cards.append({
                "card_id": c["card_id"], "series_id": c["set_id"], "number": c["number"],
                "name": c["name"], "rarity": c["rarity"], "description": c.get("description", ""),
                "art_path": f"{set_id}/{c.get('rarity', 'basic')}_{safe}.png",
                "tradable": c.get("tradable", True), "released": True,
            })
        exp_packs = []
        for p in packs:
            exp_packs.append({
                "pack_id": p["pack_id"], "series_id": p["set_id"], "name": p["name"],
                "price": p["price"], "cards_per_pack": p["cards_per_pack"],
                "guaranteed_rarity": p.get("guaranteed_rarity"),
                "description": p.get("description", ""), "released": True,
            })

        data = {
            "set_id": sd["set_id"], "display_name": sd["display_name"],
            "description": sd.get("description", ""), "base_prompt": sd.get("base_prompt", ""),
            "rarity_themes": sd.get("rarity_themes", {}), "version": sd.get("version", 1),
            "cards": exp_cards,
            "packs": exp_packs,
        }
        (out / "set.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

        if base:
            (out / "base_template.png").write_bytes(base)

        for c in cards:
            if c.get("asset_status") == "ready":
                art = await self.pub.get_asset_bytes(c["card_id"])
                if art:
                    fname = f"{c.get('rarity', 'basic')}_{c['name'].lower().replace(' ', '_').replace(chr(39), '')}.png"
                    (out / fname).write_bytes(art)

        console.print(f"[green]Exported to {out}[/green]")

    # ── List ──
    async def list_sets(self):
        cursor = self.pub.sets_col.find().sort("set_id", 1)
        sets = await cursor.to_list(length=50)
        if not sets:
            console.print("[dim]No sets in Mongo.[/dim]")
            return
        table = Table(title="Card Sets in Mongo")
        table.add_column("Set ID", style="cyan")
        table.add_column("Display Name")
        table.add_column("Status")
        table.add_column("Cards")
        table.add_column("Released")
        for s in sets:
            total = await self.pub.catalog_col.count_documents({"set_id": s["set_id"]})
            ready = await self.pub.catalog_col.count_documents({"set_id": s["set_id"], "asset_status": "ready"})
            table.add_row(s["set_id"], s.get("display_name", ""), s.get("status", "?"), f"{ready}/{total}", "yes" if s.get("released") else "no")
        console.print(table)

    # ── Helpers ──
    def _default_rarity_desc(self, rarity: str) -> str:
        return {
            "basic": "Common objects, minor relics, simple creatures — everyday items of this world.",
            "common": "Lesser characters, minor artifacts, common creatures.",
            "rare": "Important figures, powerful items, rare beings.",
            "epic": "Heroes, legendary weapons, mythical creatures.",
            "legendary": "The most powerful beings and artifacts — central figures of myth.",
            "diamond": "Transcendent concepts made manifest — reality-bending forces.",
            "platinum": "The absolute pinnacle — embodiment of the theme itself.",
        }.get(rarity, "Cards of this tier.")

    def _build_base_prompt(self, name: str, desc: str) -> str:
        return (
            f"A dark fantasy trading card template frame, 768x1024 portrait orientation, "
            f"for the '{name}' card set. {desc} "
            f"Stylized flat-color cartoon illustration with bold clean outlines and cel-shading "
            f"— similar to Hades game art or Castlevania animated series. "
            f"The center shows a subtle gradient background matching the theme. No text, no characters, "
            f"no specific objects — just the atmospheric backdrop and decorative frame elements. "
            f"Deep moody color palette with vibrant accent highlights."
        )


async def main():
    parser = argparse.ArgumentParser(description="bruh.bot Card Set Generator — direct to Mongo")
    parser.add_argument("--env", default="dev", help="Environment (default: dev)")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("wizard", help="Interactive card set creation wizard")
    sub.add_parser("list", help="List all sets in Mongo")

    rs = sub.add_parser("resume", help="Resume an interrupted card generation")
    rs.add_argument("set_id")
    rs.add_argument("--retry-failed", action="store_true", help="Retry failed cards too")

    st = sub.add_parser("status", help="Show set generation status")
    st.add_argument("set_id")

    pb = sub.add_parser("publish", help="Publish a completed set to players")
    pb.add_argument("set_id")

    ar = sub.add_parser("archive", help="Hide a set from players")
    ar.add_argument("set_id")

    pm = sub.add_parser("promote", help="Promote a set to a higher environment")
    pm.add_argument("set_id")
    pm.add_argument("--to", default="prod", help="Target environment (default: prod)")

    ex = sub.add_parser("export", help="Export a set to local files")
    ex.add_argument("set_id")
    ex.add_argument("--output", default="./exports", help="Output directory")

    args, unknown = parser.parse_known_args()
    # Allow --env anywhere
    for i, a in enumerate(unknown):
        if a == "--env" and i + 1 < len(unknown):
            args.env = unknown[i + 1]

    if not args.command:
        parser.print_help()
        return

    gen = CardSetGenerator(env=args.env)
    try:
        await gen.connect()

        if args.command == "wizard":
            await gen.wizard()
        elif args.command == "list":
            await gen.list_sets()
        elif args.command == "resume":
            await gen.resume(args.set_id, retry_failed=args.retry_failed)
        elif args.command == "status":
            await gen.status(args.set_id)
        elif args.command == "publish":
            await gen.publish(args.set_id)
        elif args.command == "archive":
            await gen.archive(args.set_id)
        elif args.command == "promote":
            await gen.promote(args.set_id, args.to)
        elif args.command == "export":
            await gen.export_set(args.set_id, args.output)
    finally:
        await gen.pub.close()


if __name__ == "__main__":
    asyncio.run(main())