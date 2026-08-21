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
from datetime import UTC, datetime
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
from tools.trading_card_publisher import VALID_ENVIRONMENTS, TradingCardPublisher

console = Console()
logger = logging.getLogger("card_gen")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

CARD_IMAGE_MODEL = "google/gemini-3.1-flash-image"
CARD_TEXT_MODEL = "deepseek/deepseek-v4-pro"
CARD_FRIENDLY_DESCRIPTION_MODEL = "google/gemini-3.1-flash-lite"
CARD_ASPECT_RATIO = "3:4"
CHARACTER_SHEET_ASPECT_RATIO = "16:9"
CARD_IMAGE_MAX_TOKENS = 4096

RARITY_COUNTS = {"basic": 14, "common": 12, "rare": 9, "epic": 6, "legendary": 4, "diamond": 3, "platinum": 2}

THEME_STORY_BEATS = {
    "basic": "awakening: each character is discovered in its own corner of the reclaimed vault",
    "common": "exploration: the characters range farther into the forest-machine ecosystem",
    "rare": "alliance: recurring characters encounter and begin cooperating with one another",
    "epic": "conflict: the alliance faces territorial threats and unstable old technology",
    "legendary": "convergence: all three characters unite around a major power source",
    "diamond": "overclock: the united cast transforms the vault through overwhelming living circuitry",
    "platinum": "ascension: the fully united cast embodies the set's ultimate techno-organic state",
}


def apply_theme_story(cards: list[dict], theme_bible: dict) -> list[dict]:
    """Guarantee every themed card advances the recurring cast's visual story."""
    characters = theme_bible.get("characters", [])
    if len(characters) != 3:
        return cards

    for card in cards:
        number = int(card["number"])
        rarity = card.get("rarity", "basic")
        primary = (number - 1) % len(characters)
        if rarity in {"basic", "common"}:
            featured = [characters[primary]]
        elif rarity in {"rare", "epic"}:
            featured = [characters[primary], characters[(primary + 1) % len(characters)]]
        else:
            featured = characters
        card["featured_character_ids"] = [character["id"] for character in featured]
        card["faction"] = featured[0]["faction"]
        card["story_beat"] = THEME_STORY_BEATS.get(rarity, "the recurring cast advances its shared story")
    return cards


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


async def generate_image(
    prompt: str,
    api_key: str,
    reference_images: list[Image.Image] | None = None,
    aspect_ratio: str = CARD_ASPECT_RATIO,
) -> tuple[Image.Image | None, str]:
    parts = [MessagePart(type="text", text=prompt)]
    for reference_image in reversed(reference_images or []):
        buf = BytesIO()
        reference_image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        parts.insert(0, MessagePart(type="image", url=f"data:image/png;base64,{b64}"))

    request = NormalizedRequest(
        provider="openrouter",
        model=CARD_IMAGE_MODEL,
        messages=[Message(role="user", parts=parts)],
        stream=False,
        max_tokens=CARD_IMAGE_MAX_TOKENS,
        modalities=["image", "text"],
        image_config={"aspect_ratio": aspect_ratio},
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


async def generate_card_names(theme_name: str, theme_desc: str, rarity_themes: dict, api_key: str, theme_bible: dict | None = None) -> list[dict] | None:
    sections = []
    for rarity in ["basic", "common", "rare", "epic", "legendary", "diamond", "platinum"]:
        count = RARITY_COUNTS[rarity]
        theme = rarity_themes.get(rarity, f"Cards of {rarity} tier.")
        sections.append(f"{rarity.upper()} ({count} cards): {theme}")

    themed_rules = ""
    if theme_bible:
        characters = theme_bible.get("characters", [])
        character_lines = "\n".join(f'- {c["id"]}: {c["name"]} — {c["description"]}' for c in characters)
        themed_rules = f"""
Set visual mechanics: {theme_bible.get("visual_mechanics", "")}
Recurring characters (use their ids exactly when featured):
{character_lines}
The generator assigns the recurring characters and story progression after this response. Retain the set mechanics in every visual description and make each scene suitable for recurring characters to visibly inhabit.
"""

    prompt = f"""Generate {sum(RARITY_COUNTS.values())} trading card names and art-direction descriptions for a card set called "{theme_name}".

Theme description: {theme_desc}
{themed_rules}

Rarity tiers and what each represents:
{chr(10).join(sections)}

For EACH card, provide card number (1-50), name (2-4 words, evocative), rarity, and description.
The description should be VISUAL ART DIRECTION ONLY: describe the subject, composition, setting, mood,
color palette, lighting, and notable visual details to guide an AI image generator.
Do NOT write player-facing lore, flavor text, or story snippets.
Do NOT write "A trading card of..." or "This card features..." — just the visual scene.

Return ONLY valid JSON as a list: [{{"number": 1, "name": "Card Name", "rarity": "basic", "description": "Visual description."}}, ...]
Start BASIC (1-14), COMMON (15-26), RARE (27-35), EPIC (36-41), LEGENDARY (42-45), DIAMOND (46-48), PLATINUM (49-50).
Platinum cards should be the ultimate chase cards. Each description must be unique."""

    request = NormalizedRequest(
        provider="openrouter",
        model=CARD_TEXT_MODEL,
        messages=[Message(role="user", parts=[MessagePart(type="text", text=prompt)])],
        stream=False,
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
            cards.append(
                {
                    "number": item["number"],
                    "name": str(item.get("name", "")),
                    "rarity": str(item.get("rarity", "common")).lower(),
                    "description": str(item.get("description", "")),
                }
            )
    return cards if len(cards) >= 10 else None


async def generate_theme_characters(theme_name: str, theme_desc: str, visual_mechanics: str, api_key: str) -> list[dict] | None:
    prompt = f"""Create exactly three recurring character designs for the trading-card set "{theme_name}".

World: {theme_desc}
Visual mechanics: {visual_mechanics}

Create one character in each faction: plugs, slots, and nodes. Each must have a distinct, repeatable silhouette, hardware chassis, material treatment, LED core color/state, and personality expressed visually. These descriptions are art direction for character reference sheets, not player-facing lore. Do not include readable text, symbols, code, labels, or logos.

Return ONLY valid JSON: [{{"id": "rootwake_cabinet", "name": "Rootwake Cabinet", "faction": "plugs", "description": "Visual character-sheet direction."}}, ...]"""
    request = NormalizedRequest(
        provider="openrouter",
        model=CARD_TEXT_MODEL,
        messages=[Message(role="user", parts=[MessagePart(type="text", text=prompt)])],
        stream=False,
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
    characters = []
    expected_factions = {"plugs", "slots", "nodes"}
    for item in data:
        if isinstance(item, dict) and item.get("faction") in expected_factions and item.get("id"):
            characters.append({"id": str(item["id"]).lower().replace(" ", "_"), "name": str(item.get("name", item["id"])), "faction": item["faction"], "description": str(item.get("description", ""))})
    return characters if {character["faction"] for character in characters} == expected_factions else None


async def generate_rarity_themes(theme_name: str, theme_desc: str, api_key: str) -> dict[str, str] | None:
    prompt = f"""For a trading card set called "{theme_name}" with this theme: {theme_desc}

Define what each rarity tier represents in this specific theme. Each tier should feel distinct and logically escalate in power/importance:

- Basic ({RARITY_COUNTS["basic"]} cards): Common, everyday elements of this theme.
- Common ({RARITY_COUNTS["common"]} cards): Familiar but notable elements.
- Rare ({RARITY_COUNTS["rare"]} cards): Significant, respected elements.
- Epic ({RARITY_COUNTS["epic"]} cards): Heroic, powerful elements.
- Legendary ({RARITY_COUNTS["legendary"]} cards): Mythical, near-pinnacle elements.
- Diamond ({RARITY_COUNTS["diamond"]} cards): Transcendent, reality-bending elements.
- Platinum ({RARITY_COUNTS["platinum"]} cards): The absolute pinnacle — embodiment of the theme itself.

Return ONLY valid JSON: {{"basic": "description", "common": "...", "rare": "...", "epic": "...", "legendary": "...", "diamond": "...", "platinum": "..."}}"""

    request = NormalizedRequest(
        provider="openrouter",
        model=CARD_TEXT_MODEL,
        messages=[Message(role="user", parts=[MessagePart(type="text", text=prompt)])],
        stream=False,
    )
    response = await get_mesh_gateway().complete(request, credentials={"api_key": api_key})
    text = "".join(p.content for p in response.parts if p.type == "text")

    import re

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    expected = list(RARITY_COUNTS.keys())
    if not all(k in data for k in expected):
        return None
    return {k: str(data[k]) for k in expected}


async def generate_friendly_description(image: Image.Image, card_name: str, rarity: str, api_key: str) -> str | None:
    buf = BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    prompt = (
        f"Based on the card art above, write 1-2 short, evocative sentences describing this trading card "
        f'for players. The card is named "{card_name}" and is {rarity} rarity. '
        f"Describe what is depicted — the character, creature, object, or scene — in a way that feels "
        f'exciting and collectible. Do NOT say "This card shows" or "The card features" — just describe '
        f"the subject directly. Keep it concise. Return ONLY the description text, no title or prefix."
    )

    request = NormalizedRequest(
        provider="openrouter",
        model=CARD_FRIENDLY_DESCRIPTION_MODEL,
        messages=[
            Message(
                role="user",
                parts=[
                    MessagePart(type="image", url=f"data:image/png;base64,{b64}"),
                    MessagePart(type="text", text=prompt),
                ],
            )
        ],
        stream=False,
    )
    response = await get_mesh_gateway().complete(request, credentials={"api_key": api_key})
    text = "".join(p.content for p in response.parts if p.type == "text")
    text = text.strip().strip('"').strip()
    return text if text else None


# ── Card Set Generator ──
class CardSetGenerator:
    def __init__(self, env: str = "dev"):
        if env not in VALID_ENVIRONMENTS:
            raise ValueError(f"Environment must be one of: {', '.join(VALID_ENVIRONMENTS)}")
        self.env = env
        self.api_key = ""
        self.pub = TradingCardPublisher(env=env)
        self.set_id = ""
        self.base_image = None
        self.character_images: dict[str, Image.Image] = {}

    async def connect(self, resolve_credentials: bool = True):
        if resolve_credentials:
            self.api_key = await resolve_api_key(self.env)
        await self.pub.connect()

    async def health(self):
        result = await self.pub.health_check()
        console.print(f"[bold]Environment:[/bold] {result['environment']}")
        console.print(f"[bold]Database:[/bold] {result['database']}")
        console.print("\n[bold]Collections:[/bold]")
        for name, present in result["collections"].items():
            console.print(f"  {'[green]OK[/green]' if present else '[red]MISSING[/red]'} {name}")
        counts = result["counts"]
        console.print("\n[bold]Counts:[/bold]")
        console.print(f"  Sets: {counts['sets']}")
        console.print(f"  Cards: {counts['cards']}")
        console.print(f"  Packs: {counts['packs']}")
        console.print(f"  Catalog revision: {counts['revision']}")
        console.print(f"  GridFS files: {counts['gridfs_files']}")
        console.print(f"  GridFS chunks: {counts['gridfs_chunks']}")
        console.print("\n[bold]Card artwork by set:[/bold]")
        missing_total = 0
        unreadable_total = 0
        for set_status in result["sets"]:
            missing = set_status["missing_card_files"]
            unreadable = set_status["unreadable_card_files"]
            missing_total += len(missing)
            unreadable_total += len(unreadable)
            if missing or unreadable:
                preview = ", ".join(missing[:5])
                if unreadable:
                    preview = ", ".join([*missing[:5], *unreadable[:5]])
                issue_count = len(missing) + len(unreadable)
                suffix = "..." if issue_count > 10 else ""
                console.print(f"  [red]ISSUES[/red] {set_status['set_id']}: {issue_count}/{set_status['cards']} card files ({preview}{suffix})")
            else:
                console.print(f"  [green]OK[/green] {set_status['set_id']}: {set_status['card_files']}/{set_status['cards']} card files")
        if missing_total or unreadable_total:
            console.print(f"\n[red]Missing card artwork files: {missing_total}[/red]")
            console.print(f"[red]Unreadable card artwork files: {unreadable_total}[/red]")
        else:
            console.print("\n[green]Every catalog card has a GridFS artwork file.[/green]")

    async def _load_character_images(self, set_doc: dict):
        self.character_images = {}
        for character in set_doc.get("theme_bible", {}).get("characters", []):
            data = await self.pub.get_asset_bytes(f"{self.set_id}_character_{character['id']}")
            if data:
                self.character_images[character["id"]] = Image.open(BytesIO(data))

    async def _generate_character_references(self, theme_bible: dict):
        self.character_images = {}
        for character in theme_bible["characters"]:
            prompt = (
                f"Create a full-body character reference sheet for {character['name']} in the '{theme_bible['name']}' trading card set. "
                f"World direction: {theme_bible['description']} Visual mechanics: {theme_bible['visual_mechanics']} "
                f"Character faction: {character['faction']}. Character identity: {character['description']} "
                "Create a four-view character turnaround on a simple dark neutral background: front, three-quarter, side, and rear. "
                "These are design angles of exactly one character, not four characters and not a story scene. Keep every angle visually identical in chassis, silhouette, materials, colors, LED core, and accessories. "
                "CRITICAL: no text, words, letters, logos, labels, stat boxes, or code."
            )
            console.print(f"\n[cyan]Generating character sheet for {character['name']}...[/cyan]")
            image, _ = await generate_image(prompt, self.api_key, aspect_ratio=CHARACTER_SHEET_ASPECT_RATIO)
            if not image:
                raise RuntimeError(f"Character sheet generation failed for {character['name']}")

            tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            image.save(tf.name)
            console.print(f"[green]Character sheet preview: {tf.name}[/green]")
            console.print("[dim]Opening for review...[/dim]")
            webbrowser.open(tf.name)
            while True:
                choice = Prompt.ask(f"Approve {character['name']}?", choices=["approve", "retry", "cancel"], default="approve")
                if choice == "cancel":
                    tf.close()
                    os.unlink(tf.name)
                    raise RuntimeError(f"Character sheet approval cancelled for {character['name']}")
                if choice == "approve":
                    break
                adjustment = Prompt.ask("What should change?", default="")
                if adjustment:
                    prompt = f"{prompt} {adjustment}"
                image, _ = await generate_image(prompt, self.api_key, aspect_ratio=CHARACTER_SHEET_ASPECT_RATIO)
                if image:
                    image.save(tf.name)
                    webbrowser.open(tf.name)
                    console.print("[green]Updated.[/green]")
                else:
                    console.print("[red]Generation failed. Keeping the previous preview.[/red]")

            self.character_images[character["id"]] = image
            buf = BytesIO()
            image.save(buf, format="PNG")
            await self.pub.upload_asset(f"{self.set_id}_character_{character['id']}", buf.getvalue(), replace=True)
            tf.close()
            os.unlink(tf.name)

    async def regenerate_character_sheets(self, set_id: str):
        self.set_id = set_id
        set_doc = await self.pub.get_set(set_id)
        if not set_doc:
            console.print(f"[red]Set '{set_id}' not found in Mongo.[/red]")
            return
        theme_bible = set_doc.get("theme_bible", {})
        if not theme_bible.get("characters"):
            console.print(f"[red]Set '{set_id}' has no recurring character theme.[/red]")
            return
        await self._generate_character_references(theme_bible)
        console.print("[green]Character sheets updated. Regenerate card art to apply them.[/green]")

    def _reference_images_for_card(self, card: dict) -> list[Image.Image]:
        references = [self.base_image] if self.base_image else []
        for character_id in card.get("featured_character_ids", []):
            image = self.character_images.get(character_id)
            if image:
                references.append(image)
        return references

    def _build_card_prompt(self, card: dict) -> str:
        character_ids = card.get("featured_character_ids", [])
        character_instruction = ""
        if character_ids:
            character_instruction = (
                f"The attached character reference sheets for {', '.join(character_ids)} are canonical; "
                "depict exactly ONE visible instance of each referenced character in this card. Never duplicate, clone, echo, or repeat a character in the same composition. "
                "Use the reference sheets only for character design, not as a multi-angle composition to copy. Preserve their silhouettes, chassis, materials, and LED cores. "
            )
        return (
            "Use the provided base template card to create a trading card. "
            f"Depict the following concept as a character or scene illustration: {card['description']} "
            f"Story progression: {card.get('story_beat', 'an independent scene from this set')}. "
            f"{character_instruction}"
            "CRITICAL: Do NOT put any text, words, letters, titles, names, placeholders, "
            "or description text on the card. The card must have zero text — only artwork."
        )

    async def apply_theme_story(self, set_id: str) -> bool:
        self.set_id = set_id
        set_doc = await self.pub.get_set(set_id)
        if not set_doc:
            console.print(f"[red]Set '{set_id}' not found in Mongo.[/red]")
            return False
        if not set_doc.get("theme_bible", {}).get("characters"):
            console.print(f"[red]Set '{set_id}' has no recurring character theme to apply.[/red]")
            return False

        cards = await self.pub.get_all_cards(set_id)
        if not cards:
            console.print(f"[red]Set '{set_id}' has no cards.[/red]")
            return False
        apply_theme_story(cards, set_doc["theme_bible"])
        for card in cards:
            await self.pub.catalog_col.update_one(
                {"card_id": card["card_id"]},
                {"$set": {"featured_character_ids": card["featured_character_ids"], "faction": card["faction"], "story_beat": card["story_beat"]}},
            )
        console.print(f"[green]Assigned recurring characters and story beats to {len(cards)} cards.[/green]")
        return True

    # ── Wizard ──
    async def wizard(self, auto_release: bool = False):
        console.print(Panel.fit("[bold cyan]Card Set Generator — Direct to Mongo[/bold cyan]\n\nDefine a theme, generate cards with AI, and publish directly to MongoDB.", title="bruh.bot Card Generator"))

        self.set_id = Prompt.ask("\n[bold]Set ID[/bold]", default="my_set").lower().replace(" ", "_")
        theme_name = Prompt.ask("[bold]Display name[/bold]", default=self.set_id.replace("_", " ").title())
        theme_desc = Prompt.ask("[bold]Theme description[/bold]", default="A mysterious collection of dark fantasy trading cards.")
        themed = Confirm.ask("Create recurring themed characters?", default=False)
        theme_bible = {}
        if themed:
            visual_mechanics = Prompt.ask("[bold]Visual elements and set mechanics[/bold]", default="Keep a consistent visual language across every card.")
            console.print("\n[cyan]Generating the three faction character designs...[/cyan]")
            characters = None
            while not characters:
                characters = await generate_theme_characters(theme_name, theme_desc, visual_mechanics, self.api_key)
                if not characters and not Confirm.ask("Character generation failed. Retry?", default=True):
                    return
            theme_bible = {"name": theme_name, "description": theme_desc, "visual_mechanics": visual_mechanics, "characters": characters}
            character_table = Table(title="Recurring Characters")
            character_table.add_column("Faction")
            character_table.add_column("Name")
            character_table.add_column("Visual identity", max_width=70)
            for character in characters:
                character_table.add_row(character["faction"].title(), character["name"], character["description"])
            console.print(character_table)
            if not Confirm.ask("Approve recurring characters?", default=True):
                return

        console.print("\n[cyan]Generating rarity tier descriptions with AI...[/cyan]")
        rarity_themes = None
        while not rarity_themes:
            rarity_themes = await generate_rarity_themes(theme_name, theme_desc, self.api_key)
            if not rarity_themes:
                console.print("[red]AI generation failed.[/red]")
                if not Confirm.ask("Retry?", default=True):
                    return

        table = Table(title=f"Rarity Themes — {theme_name}")
        table.add_column("Rarity", style="bold")
        table.add_column("#")
        table.add_column("Theme", max_width=60)
        for rarity in RARITY_COUNTS:
            table.add_row(rarity.title(), str(RARITY_COUNTS[rarity]), rarity_themes.get(rarity, ""))
        console.print(table)

        if not Confirm.ask("\nApprove rarity themes?", default=True):
            console.print("\n[bold]Enter custom rarity themes:[/bold]")
            rarity_themes = {}
            for rarity in RARITY_COUNTS:
                default = self._default_rarity_desc(rarity)
                rarity_themes[rarity] = Prompt.ask(f"  [bold]{rarity.title()}[/bold] ({RARITY_COUNTS[rarity]} cards)", default=default)

        # Generate card names
        console.print("\n[cyan]Generating card names and descriptions with AI...[/cyan]")
        ai_cards = None
        while not ai_cards or len(ai_cards) < 10:
            ai_cards = await generate_card_names(theme_name, theme_desc, rarity_themes, self.api_key, theme_bible or None)
            if not ai_cards or len(ai_cards) < 10:
                console.print("[red]AI generation returned too few cards.[/red]")
                if not Confirm.ask("Retry?", default=True):
                    return

        if theme_bible:
            apply_theme_story(ai_cards, theme_bible)

        table = Table(title=f"Preview — {theme_name}")
        table.add_column("#", style="dim")
        table.add_column("Name")
        table.add_column("Rarity")
        table.add_column("Generation Prompt", max_width=50)
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
            cards.append(
                {
                    "card_id": f"{self.set_id}_{c['number']:03d}",
                    "series_id": self.set_id,
                    "number": c["number"],
                    "name": c["name"],
                    "rarity": c["rarity"],
                    "description": c["description"],
                    "featured_character_ids": c.get("featured_character_ids", []),
                    "faction": c.get("faction"),
                    "story_beat": c.get("story_beat", ""),
                    "art_path": f"{self.set_id}/{c['rarity']}_{safe}.png",
                    "tradable": True,
                }
            )

        # Generate base template
        base_prompt = self._build_base_prompt(theme_name, theme_desc, theme_bible.get("visual_mechanics", ""))
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

        if theme_bible:
            try:
                await self._generate_character_references(theme_bible)
            except RuntimeError as error:
                console.print(f"[red]{error}[/red]")
                return

        # Pack definitions
        console.print("\n[bold]Pack settings:[/bold]")

        def ask_int(label: str, default: int, minimum: int, maximum: int) -> int:
            while True:
                try:
                    value = int(Prompt.ask(label, default=str(default)))
                except ValueError:
                    console.print(f"[red]Enter a whole number between {minimum} and {maximum}.[/red]")
                    continue
                if minimum <= value <= maximum:
                    return value
                console.print(f"[red]Enter a number between {minimum} and {maximum}.[/red]")

        pack_count = ask_int("  Number of packs", 2, 1, 10)
        packs = []
        rarity_choices = ["none", *RARITY_COUNTS]
        for index in range(pack_count):
            default_name = f"{theme_name} Pack" if index == 0 else f"{theme_name} Premium Pack" if index == 1 else f"{theme_name} Pack {index + 1}"
            default_price = 350 if index == 0 else 1100 if index == 1 else 500
            default_cards = 3 if index == 0 else 5
            default_guarantee = "none" if index == 0 else "rare" if index == 1 else "none"

            console.print(f"\n[bold cyan]Pack {index + 1}/{pack_count}[/bold cyan]")
            pack_name = Prompt.ask("  Name", default=default_name)
            price = ask_int("  Price", default_price, 0, 1_000_000)
            cards_per_pack = ask_int("  Cards per pack", default_cards, 1, 50)
            guaranteed = Prompt.ask("  Guaranteed rarity", choices=rarity_choices, default=default_guarantee)
            description = Prompt.ask("  Description", default=f"A pack from {theme_name}.")
            packs.append(
                {
                    "pack_id": f"{self.set_id}_pack_{index + 1}",
                    "series_id": self.set_id,
                    "name": pack_name,
                    "price": price,
                    "cards_per_pack": cards_per_pack,
                    "guaranteed_rarity": None if guaranteed == "none" else guaranteed,
                    "description": description,
                    "released": False,
                }
            )

        # Save set metadata to Mongo
        await self.pub.upsert_set(
            self.set_id,
            {
                "display_name": theme_name,
                "description": theme_desc,
                "base_prompt": base_prompt,
                "rarity_themes": rarity_themes,
                "theme_bible": theme_bible,
                "status": "generating",
                "generation_model": CARD_IMAGE_MODEL,
                "version": 1,
            },
        )
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
        await self.pub.bump_revision(f"created set {self.set_id}")

        # Mark complete
        await self.pub.upsert_set(
            self.set_id,
            {
                "display_name": theme_name,
                "description": theme_desc,
                "base_prompt": base_prompt,
                "rarity_themes": rarity_themes,
                "theme_bible": theme_bible,
                "status": "ready",
                "generation_model": CARD_IMAGE_MODEL,
            },
        )
        if auto_release or themed:
            await self.release(self.set_id)
        else:
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

            prompt = self._build_card_prompt(card)
            console.print(f"  [{i + 1}/{total}] [cyan]{card['card_id']} ({card['rarity']})...[/cyan]")

            try:
                image, _ = await generate_image(prompt, self.api_key, self._reference_images_for_card(card))
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

                    console.print("    [dim]Generating friendly description...[/dim]")
                    try:
                        friendly = await generate_friendly_description(image, card.get("name", ""), card.get("rarity", "common"), self.api_key)
                        if friendly:
                            now = datetime.now(UTC)
                            await self.pub.catalog_col.update_one(
                                {"card_id": card["card_id"]},
                                {
                                    "$set": {
                                        "friendly_description": friendly,
                                        "friendly_description_status": "ready",
                                        "friendly_description_error": None,
                                        "friendly_description_updated_at": now,
                                    }
                                },
                            )
                            console.print(f"    [green]Description: {friendly[:60]}...[/green]")
                        else:
                            await self.pub.catalog_col.update_one(
                                {"card_id": card["card_id"]},
                                {
                                    "$set": {
                                        "friendly_description_status": "failed",
                                        "friendly_description_error": "No description returned",
                                    }
                                },
                            )
                            console.print("    [yellow]Friendly description generation returned empty[/yellow]")
                    except Exception as e:
                        await self.pub.catalog_col.update_one(
                            {"card_id": card["card_id"]},
                            {
                                "$set": {
                                    "friendly_description_status": "failed",
                                    "friendly_description_error": str(e)[:200],
                                }
                            },
                        )
                        console.print(f"    [yellow]Friendly description failed: {e}[/yellow]")
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

        # A cancelled process can leave its in-flight card in generating state.
        statuses = ["pending", "generating"]
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

        await self._load_character_images(sd)
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
        await self.pub.catalog_col.update_many({"set_id": set_id}, {"$set": {"released": True}})
        await self.pub.bump_revision(f"published set {set_id}")
        console.print(f"[green]Set '{s['display_name']}' published! Run /bruh-cards-admin reload in Discord.[/green]")

    async def release(self, set_id: str):
        if self.env != "dev":
            console.print("[red]Release must start from dev so the production catalog has a reviewed source.[/red]")
            return
        status = await self.pub.get_set_status(set_id)
        if not status["total_cards"] or status["ready"] != status["total_cards"]:
            console.print(f"[red]Cannot release: {status['ready']}/{status['total_cards']} cards are ready in dev.[/red]")
            return

        await self.publish(set_id)
        await self.promote(set_id, "prod")
        prod = CardSetGenerator(env="prod")
        try:
            await prod.connect(resolve_credentials=False)
            await prod.publish(set_id)
        finally:
            await prod.pub.close()
        console.print(f"[bold green]Released '{status['display_name']}' to dev and prod.[/bold green]")

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
            await dst.upsert_set(
                set_id,
                {
                    "display_name": sd["display_name"],
                    "description": sd.get("description", ""),
                    "base_prompt": sd.get("base_prompt", ""),
                    "rarity_themes": sd.get("rarity_themes", {}),
                    "theme_bible": sd.get("theme_bible", {}),
                    "status": sd.get("status", "ready"),
                    "released": sd.get("released", False),
                    "version": sd.get("version", 1),
                    "generation_model": sd.get("generation_model", ""),
                },
            )

            # Copy base template
            base = await src.get_asset_bytes(f"{set_id}_base_template")
            if base:
                await dst.upload_asset(f"{set_id}_base_template", base, replace=True)
                console.print("  Base template copied")

            for character in sd.get("theme_bible", {}).get("characters", []):
                character_asset = f"{set_id}_character_{character['id']}"
                image = await src.get_asset_bytes(character_asset)
                if image:
                    await dst.upload_asset(character_asset, image, replace=True)
                    console.print(f"  Character sheet copied: {character['name']}")

            # Copy cards
            cards = await src.get_all_cards(set_id)
            ready = 0
            for c in cards:
                c["released"] = sd.get("released", True)
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
                pk["released"] = sd.get("released", True)
                await dst.upsert_pack(pk)

            await dst.catalog_col.update_many({"set_id": set_id}, {"$set": {"released": True}})
            await dst.packs_col.update_many({"set_id": set_id}, {"$set": {"released": True}})
            await dst.bump_revision(f"promoted set {set_id} from {self.env}")

            console.print(f"[green]Promoted {ready}/{len(cards)} cards + {len(packs)} packs to {target_env}.[/green]")
            console.print(f"  Run /bruh-cards-admin reload in Discord ({target_env} bot).")
        finally:
            await dst.close()

    async def promote_all(self, target_env: str):
        if self.env == target_env:
            console.print("[red]Source and target environments must be different.[/red]")
            return

        sets = await self.pub.sets_col.find({}, {"set_id": 1, "_id": 0}).sort("set_id", 1).to_list(length=10000)
        set_ids = [entry["set_id"] for entry in sets]
        if not set_ids:
            console.print(f"[yellow]No sets found in {self.env}.[/yellow]")
            return

        console.print(f"Found {len(set_ids)} set(s) in {self.env}: {', '.join(set_ids)}")
        if not Confirm.ask(f"Promote all sets from {self.env} to {target_env}?", default=False):
            console.print("[yellow]Promotion cancelled.[/yellow]")
            return

        failed = []
        for set_id in set_ids:
            try:
                await self.promote(set_id, target_env)
            except Exception as error:
                failed.append((set_id, str(error)))
                console.print(f"[red]Failed to promote {set_id}: {error}[/red]")

        if failed:
            console.print(f"[yellow]Completed with {len(failed)} failure(s).[/yellow]")
        else:
            console.print(f"[green]Promoted all {len(set_ids)} set(s) to {target_env}.[/green]")

    async def archive(self, set_id: str):
        if not Confirm.ask(f"Archive set '{set_id}'? This hides it from players but preserves data.", default=False):
            return
        await self.pub.archive_set(set_id)
        await self.pub.bump_revision(f"archived set {set_id}")
        console.print(f"[yellow]Set '{set_id}' archived.[/yellow]")

    async def delete(self, set_id: str):
        existing = await self.pub.get_set(set_id)
        if not existing:
            console.print(f"[red]Set '{set_id}' not found in {self.env}.[/red]")
            return
        warning = f"Permanently delete '{set_id}' from {self.env}, including all cards, packs, and artwork?"
        if not Confirm.ask(warning, default=False):
            console.print("[yellow]Deletion cancelled.[/yellow]")
            return
        counts = await self.pub.delete_set(set_id)
        console.print(f"[red]Deleted '{set_id}' from {self.env}: {counts['sets']} set, {counts['cards']} cards, {counts['packs']} packs, {counts['assets']} assets.[/red]")

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
            exp_cards.append(
                {
                    "card_id": c["card_id"],
                    "series_id": c["set_id"],
                    "number": c["number"],
                    "name": c["name"],
                    "rarity": c["rarity"],
                    "description": c.get("description", ""),
                    "art_path": f"{set_id}/{c.get('rarity', 'basic')}_{safe}.png",
                    "tradable": c.get("tradable", True),
                    "released": True,
                }
            )
        exp_packs = []
        for p in packs:
            exp_packs.append(
                {
                    "pack_id": p["pack_id"],
                    "series_id": p["set_id"],
                    "name": p["name"],
                    "price": p["price"],
                    "cards_per_pack": p["cards_per_pack"],
                    "guaranteed_rarity": p.get("guaranteed_rarity"),
                    "description": p.get("description", ""),
                    "released": True,
                }
            )

        data = {
            "set_id": sd["set_id"],
            "display_name": sd["display_name"],
            "description": sd.get("description", ""),
            "base_prompt": sd.get("base_prompt", ""),
            "rarity_themes": sd.get("rarity_themes", {}),
            "theme_bible": sd.get("theme_bible", {}),
            "version": sd.get("version", 1),
            "cards": exp_cards,
            "packs": exp_packs,
        }
        (out / "set.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

        if base:
            (out / "base_template.png").write_bytes(base)

        for character in sd.get("theme_bible", {}).get("characters", []):
            reference = await self.pub.get_asset_bytes(f"{set_id}_character_{character['id']}")
            if reference:
                (out / f"character_{character['id']}.png").write_bytes(reference)

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

    # ── Regenerate card art ──
    async def regenerate_card(self, set_id: str, card_id: str, prompt_override: str | None = None, yes: bool = False):
        self.set_id = set_id
        sd = await self.pub.get_set(set_id)
        if not sd:
            console.print(f"[red]Set '{set_id}' not found in Mongo.[/red]")
            return

        doc = await self.pub.catalog_col.find_one({"card_id": card_id})
        if not doc:
            console.print(f"[red]Card '{card_id}' not found in catalog.[/red]")
            return

        if sd.get("theme_bible", {}).get("characters"):
            apply_theme_story([doc], sd["theme_bible"])
        if doc.get("set_id") != set_id:
            console.print(f"[red]Card '{card_id}' belongs to set '{doc.get('set_id')}', not '{set_id}'.[/red]")
            return

        rarity = doc.get("rarity", "common")
        description = doc.get("description", "")
        card_name = doc.get("name", card_id)

        console.print(f"\n[bold]{sd['display_name']}[/bold] — [cyan]{card_name}[/cyan] ({rarity})")
        console.print(f"  Description: {description}")

        prompt = prompt_override if prompt_override else self._build_card_prompt(doc)
        if prompt_override:
            console.print(f"  [yellow]Prompt override: {prompt}[/yellow]")
        else:
            console.print("  [dim]Using description as prompt[/dim]")

        base_data = await self.pub.get_asset_bytes(f"{set_id}_base_template")
        if base_data:
            self.base_image = Image.open(BytesIO(base_data))
            console.print("[green]Loaded base template from GridFS[/green]")
        else:
            self.base_image = None
            console.print("[yellow]No base template in GridFS, generating without reference[/yellow]")

        await self._load_character_images(sd)

        console.print("\n[cyan]Generating card art...[/cyan]")
        image, _ = await generate_image(prompt, self.api_key, self._reference_images_for_card(doc))
        if not image:
            console.print("[red]Generation returned no image.[/red]")
            return

        if image.mode != "RGBA":
            image = image.convert("RGBA")

        tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        image.save(tf.name)
        console.print(f"[green]Preview: {tf.name}[/green]")

        if not yes:
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
                adj = Prompt.ask("Tweak prompt", default="")
                if adj:
                    prompt = f"{prompt} {adj}"
                image, _ = await generate_image(prompt, self.api_key, self._reference_images_for_card(doc))
                if image:
                    if image.mode != "RGBA":
                        image = image.convert("RGBA")
                    image.save(tf.name)
                    webbrowser.open(tf.name)
                    console.print("[green]Updated.[/green]")

        buf = BytesIO()
        image.save(buf, format="PNG")
        data = buf.getvalue()
        sha = TradingCardPublisher.compute_sha256(data)
        await self.pub.upload_asset(card_id, data, checksum=sha, replace=True)

        await self.pub.catalog_col.update_one(
            {"card_id": card_id},
            {
                "$set": {
                    "asset_status": "ready",
                    "asset_sha256": sha,
                    "asset_content_type": "image/png",
                    "asset_filename": f"{rarity}_{card_name.lower().replace(' ', '_').replace(chr(39), '')}.png",
                    "asset_error": None,
                    "asset_updated_at": datetime.now(UTC),
                    "featured_character_ids": doc.get("featured_character_ids", []),
                    "faction": doc.get("faction"),
                    "story_beat": doc.get("story_beat", ""),
                }
            },
        )

        tf.close()
        os.unlink(tf.name)

        console.print(f"\n[bold green]Card '{card_id}' art updated![/bold green]")
        console.print(f"  SHA-256: {sha}")

        console.print("\n[dim]Generating friendly description from final art...[/dim]")
        try:
            friendly = await generate_friendly_description(image, card_name, rarity, self.api_key)
            if friendly:
                now = datetime.now(UTC)
                await self.pub.catalog_col.update_one(
                    {"card_id": card_id},
                    {
                        "$set": {
                            "friendly_description": friendly,
                            "friendly_description_status": "ready",
                            "friendly_description_error": None,
                            "friendly_description_updated_at": now,
                        }
                    },
                )
                console.print(f"[green]Friendly description: {friendly}[/green]")
            else:
                await self.pub.catalog_col.update_one(
                    {"card_id": card_id},
                    {
                        "$set": {
                            "friendly_description_status": "failed",
                            "friendly_description_error": "No description returned",
                        }
                    },
                )
                console.print("[yellow]Friendly description generation returned empty[/yellow]")
        except Exception as e:
            await self.pub.catalog_col.update_one(
                {"card_id": card_id},
                {
                    "$set": {
                        "friendly_description_status": "failed",
                        "friendly_description_error": str(e)[:200],
                    }
                },
            )
            console.print(f"[yellow]Friendly description failed: {e}[/yellow]")

        console.print("[yellow]Run /bruh-cards-admin reload in Discord to refresh the bot cache.[/yellow]")

    # ── Regenerate all cards ──
    async def regenerate_all(self, set_id: str, yes: bool = False, skip_base: bool = False):
        self.set_id = set_id
        sd = await self.pub.get_set(set_id)
        if not sd:
            console.print(f"[red]Set '{set_id}' not found in Mongo.[/red]")
            return

        st = await self.pub.get_set_status(set_id)
        console.print(f"\n[bold]{st['display_name']}[/bold]")
        console.print(f"   Total: {st['total_cards']} | Ready: {st['ready']} | Pending: {st['pending']} | Failed: {st['failed']}")

        if st["total_cards"] == 0:
            console.print("[red]No cards found for this set.[/red]")
            return

        if sd.get("theme_bible", {}).get("characters"):
            await self.apply_theme_story(set_id)

        if not yes:
            if not Confirm.ask(f"\nReset all {st['total_cards']} cards to pending and regenerate?", default=False):
                return

        console.print(f"\n[cyan]Resetting {st['total_cards']} cards to pending...[/cyan]")
        await self.pub.catalog_col.update_many(
            {"set_id": set_id},
            {"$set": {"asset_status": "pending", "asset_error": None}},
        )
        console.print("[green]All cards reset to pending.[/green]")

        if skip_base:
            console.print("[dim]Skipping base template regeneration — loading existing...[/dim]")
            base_data = await self.pub.get_asset_bytes(f"{set_id}_base_template")
            if base_data:
                self.base_image = Image.open(BytesIO(base_data))
                console.print("[green]Loaded existing base template.[/green]")
            else:
                self.base_image = None
                console.print("[yellow]No base template found — generating cards without reference.[/yellow]")
        else:
            base_prompt = sd.get("base_prompt", "")
            theme_name = sd.get("display_name", set_id)
            theme_desc = sd.get("description", "")
            if not base_prompt:
                base_prompt = self._build_base_prompt(theme_name, theme_desc, sd.get("theme_bible", {}).get("visual_mechanics", ""))

            console.print("\n[cyan]Generating base template...[/cyan]")
            self.base_image, _ = await generate_image(base_prompt, self.api_key)
            if not self.base_image:
                console.print("[red]Base template generation failed.[/red]")
                base_data = await self.pub.get_asset_bytes(f"{set_id}_base_template")
                if base_data:
                    self.base_image = Image.open(BytesIO(base_data))
                    console.print("[yellow]Falling back to existing base template.[/yellow]")
                else:
                    self.base_image = None
                    console.print("[yellow]No base template available — generating cards without reference.[/yellow]")
            else:
                tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                self.base_image.save(tf.name)
                console.print(f"[green]Base template preview: {tf.name}[/green]")
                if not yes:
                    console.print("[dim]Opening for review...[/dim]")
                    webbrowser.open(tf.name)
                    while True:
                        choice = Prompt.ask("Approve base template?", choices=["approve", "retry", "cancel"], default="approve")
                        if choice == "cancel":
                            tf.close()
                            os.unlink(tf.name)
                            console.print("[yellow]Cancelled.[/yellow]")
                            return
                        if choice == "approve":
                            break
                        adj = Prompt.ask("Tweak prompt", default="")
                        if adj:
                            base_prompt += f" {adj}"
                        self.base_image, _ = await generate_image(base_prompt, self.api_key)
                        if self.base_image:
                            self.base_image.save(tf.name)
                            webbrowser.open(tf.name)
                            console.print("[green]Updated.[/green]")
                        else:
                            console.print("[red]Generation failed, keeping previous version.[/red]")
                            break

                buf = BytesIO()
                self.base_image.save(buf, format="PNG")
                await self.pub.upload_asset(f"{set_id}_base_template", buf.getvalue(), replace=True)
                console.print("[green]Base template uploaded.[/green]")
                tf.close()
                os.unlink(tf.name)

        cards = await self.pub.get_cards_by_status(set_id, "pending")
        await self._load_character_images(sd)
        console.print(f"\nGenerating {len(cards)} cards...")
        await self._generate_cards_direct(cards)
        await self.pub.bump_revision(f"regenerated set {set_id}")
        console.print(f"\n[green]Done. Check status: poetry run python tools/card_gen.py status {set_id} --env {self.env}[/green]")

    # ── Upload pre-generated set ──
    async def upload_set(self, set_id: str, folder: str, display_name: str | None = None, prefix: str | None = None, manifest: str | None = None):
        folder_path = Path(folder)
        if not folder_path.is_dir():
            console.print(f"[red]Folder not found: {folder}[/red]")
            return

        prefix = prefix or set_id
        display_name = display_name or set_id.replace("_", " ").title()

        # Check if set already exists
        existing = await self.pub.get_set(set_id)
        if existing:
            if not Confirm.ask(f"Set '{set_id}' already exists. Overwrite?", default=False):
                return
            console.print(f"[yellow]Overwriting existing set '{set_id}'...[/yellow]")

        # Load manifest
        cards = []
        if manifest:
            manifest_path = Path(manifest)
            if not manifest_path.is_file():
                console.print(f"[red]Manifest not found: {manifest}[/red]")
                return
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            cards = manifest_data.get("cards", [])
            display_name = manifest_data.get("display_name", display_name)
            console.print(f"[green]Loaded manifest: {len(cards)} cards[/green]")

        # Scan folder for images
        image_files: dict[int, Path] = {}
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            for f in sorted(folder_path.glob(ext)):
                name = f.stem
                if name.startswith(prefix):
                    try:
                        suffix = name[len(prefix) :].lstrip("_")
                        num = int(suffix)
                        image_files[num] = f
                    except ValueError:
                        pass

        if not image_files:
            console.print(f"[red]No images found matching prefix '{prefix}_###' in {folder}[/red]")
            return

        console.print(f"\n[bold]Uploading '{display_name}' to {self.env}...[/bold]")
        console.print(f"  Found {len(image_files)} images (prefix: {prefix})")

        # Upload base template if present
        base_file = folder_path / "base_template.png"
        if not base_file.exists():
            base_file = folder_path / "base_template.jpg"
        if not base_file.exists():
            base_file = folder_path / "base_template.jpeg"

        base_image = None
        if base_file.exists():
            base_image = Image.open(base_file).convert("RGBA")
            buf = BytesIO()
            base_image.save(buf, format="PNG")
            await self.pub.upload_asset(f"{set_id}_base_template", buf.getvalue(), replace=True)
            console.print("  [green]Base template uploaded[/green]")
        else:
            console.print("  [yellow]No base_template.* found — cards will render without a reference[/yellow]")

        # Build card list
        if not cards:
            console.print("  [dim]No manifest provided, generating placeholder metadata from filenames[/dim]")
            for num in sorted(image_files.keys()):
                card_id = f"{set_id}_{num:03d}"
                rarity = "platinum" if num == 50 else "diamond" if num >= 47 else "legendary" if num >= 43 else "epic" if num >= 37 else "rare" if num >= 27 else "common" if num >= 15 else "basic"
                cards.append(
                    {
                        "number": num,
                        "name": f"{display_name} #{num}",
                        "rarity": rarity,
                        "description": f"Card #{num} from {display_name}.",
                    }
                )
        else:
            # Validate manifest cards have numbers
            for i, c in enumerate(cards):
                if "number" not in c:
                    c["number"] = i + 1

        # Upload cards
        uploaded = 0
        total = len(cards)
        for card_info in cards:
            num = card_info["number"]
            card_id = f"{set_id}_{num:03d}"
            rarity = card_info.get("rarity", "common").lower()
            name = card_info.get("name", f"Card #{num}")
            description = card_info.get("description", "")

            # Find matching image
            img_path = image_files.get(num)
            if not img_path:
                console.print(f"  [{uploaded + 1}/{total}] [yellow]No image for #{num} — skipping {card_id}[/yellow]")
                continue

            try:
                img = Image.open(img_path).convert("RGBA")
                buf = BytesIO()
                img.save(buf, format="PNG")
                data = buf.getvalue()
                sha = TradingCardPublisher.compute_sha256(data)
                await self.pub.upload_asset(card_id, data, checksum=sha, replace=True)

                await self.pub.upsert_card(
                    {
                        "card_id": card_id,
                        "set_id": set_id,
                        "number": num,
                        "name": name,
                        "rarity": rarity,
                        "description": description,
                        "tradable": True,
                        "asset_status": "ready",
                        "asset_sha256": sha,
                        "asset_content_type": "image/png",
                        "asset_filename": img_path.name,
                    }
                )

                uploaded += 1
                console.print(f"  [{uploaded}/{total}] [green]{card_id}[/green] — {name} ({rarity})")
            except Exception as e:
                console.print(f"  [{uploaded + 1}/{total}] [red]{card_id} failed: {e}[/red]")

        # Save set metadata
        await self.pub.upsert_set(
            set_id,
            {
                "display_name": display_name,
                "description": f"Uploaded from {folder_path.name}",
                "status": "ready",
                "version": 1,
            },
        )

        # Ask for pack definitions
        if Confirm.ask("\nCreate pack definitions?", default=True):
            console.print("\n[bold]Pack settings:[/bold]")
            std_price = int(Prompt.ask("  Standard pack price", default="350"))
            prem_price = int(Prompt.ask("  Premium pack price", default="1100"))
            packs = [
                {"pack_id": f"{set_id}_standard", "series_id": None, "set_id": set_id, "name": f"{display_name} Pack", "price": std_price, "cards_per_pack": 3, "guaranteed_rarity": None, "description": f"Standard pack from {display_name}.", "released": False},
                {"pack_id": f"{set_id}_premium", "series_id": None, "set_id": set_id, "name": f"{display_name} Premium Pack", "price": prem_price, "cards_per_pack": 3, "guaranteed_rarity": "rare", "description": f"Premium pack from {display_name}. Guaranteed Rare+.", "released": False},
            ]
        for pk in packs:
            await self.pub.upsert_pack(pk)
            console.print(f"[green]{len(packs)} pack definitions created.[/green]")

        await self.pub.bump_revision(f"uploaded set {set_id}")
        console.print(f"\n[bold green]Done! {uploaded}/{total} cards uploaded to {self.env}.[/bold green]")
        console.print(f"  Set ID: {set_id}")
        console.print(f"  Publish: poetry run python tools/card_gen.py publish {set_id} --env {self.env}")

    # ── Backfill friendly descriptions ──
    async def backfill_friendly_descriptions(self, set_id: str | None = None, force: bool = False, retry_failed: bool = False, yes: bool = False):
        query: dict = {"asset_status": "ready"}
        if set_id:
            query["set_id"] = set_id

        if not force:
            if retry_failed:
                query["friendly_description_status"] = {"$in": ["pending", "failed", None]}
            else:
                query["$or"] = [
                    {"friendly_description_status": {"$exists": False}},
                    {"friendly_description_status": "pending"},
                    {"friendly_description": {"$exists": False}},
                    {"friendly_description": ""},
                ]

        cursor = self.pub.catalog_col.find(query).sort("set_id", 1).sort("number", 1)
        cards = await cursor.to_list(length=10000)
        if not cards:
            console.print("[green]No cards need friendly descriptions.[/green]")
            return

        sets = sorted({c["set_id"] for c in cards})
        console.print("\n[bold]Friendly Description Backfill[/bold]")
        console.print(f"  Cards to process: {len(cards)} across {len(sets)} set(s)")
        console.print(f"  Mode: {'force' if force else 'retry-failed' if retry_failed else 'missing only'}")
        for sid in sets:
            sub = [c for c in cards if c["set_id"] == sid]
            ready_desc = sum(1 for c in sub if c.get("friendly_description") and c.get("friendly_description_status") == "ready")
            console.print(f"    {sid}: {len(sub)} cards ({ready_desc} already have descriptions)")

        if not yes:
            if not Confirm.ask("\nProceed?", default=True):
                return

        for i, card in enumerate(cards):
            console.print(f"  [{i + 1}/{len(cards)}] [cyan]{card['card_id']}[/cyan] ({card.get('name', '?')})")
            try:
                art = await self.pub.get_asset_bytes(card["card_id"])
                if not art:
                    console.print("    [yellow]No art found in GridFS, skipping[/yellow]")
                    continue

                image = Image.open(BytesIO(art))
                if image.mode != "RGBA":
                    image = image.convert("RGBA")

                friendly = await generate_friendly_description(
                    image,
                    card.get("name", ""),
                    card.get("rarity", "common"),
                    self.api_key,
                )
                if friendly:
                    now = datetime.now(UTC)
                    await self.pub.catalog_col.update_one(
                        {"card_id": card["card_id"]},
                        {
                            "$set": {
                                "friendly_description": friendly,
                                "friendly_description_status": "ready",
                                "friendly_description_error": None,
                                "friendly_description_updated_at": now,
                            }
                        },
                    )
                    console.print(f"    [green]{friendly[:80]}...[/green]")
                else:
                    await self.pub.catalog_col.update_one(
                        {"card_id": card["card_id"]},
                        {
                            "$set": {
                                "friendly_description_status": "failed",
                                "friendly_description_error": "No description returned",
                            }
                        },
                    )
                    console.print("    [yellow]No description returned[/yellow]")
            except Exception as e:
                await self.pub.catalog_col.update_one(
                    {"card_id": card["card_id"]},
                    {
                        "$set": {
                            "friendly_description_status": "failed",
                            "friendly_description_error": str(e)[:200],
                        }
                    },
                )
                console.print(f"    [red]{e}[/red]")

            await asyncio.sleep(0.5)

        console.print("\n[green]Backfill complete. Run /bruh-cards-admin reload to refresh.[/green]")

    # ── Promote friendly descriptions ──
    async def promote_friendly_descriptions(self, set_id: str | None = None, target_env: str = "prod", yes: bool = False):
        src = self.pub
        dst = TradingCardPublisher(env=target_env)
        await dst.connect()

        try:
            query = {"friendly_description_status": "ready", "friendly_description": {"$exists": True, "$ne": ""}}
            if set_id:
                query["set_id"] = set_id

            cursor = src.catalog_col.find(query).sort("set_id", 1).sort("number", 1)
            cards = await cursor.to_list(length=10000)
            if not cards:
                console.print("[green]No cards have ready friendly descriptions to promote.[/green]")
                return

            console.print("\n[bold]Promote Friendly Descriptions[/bold]")
            console.print(f"  Source: {self.env} → Target: {target_env}")
            console.print(f"  Cards with ready descriptions: {len(cards)}")

            matched = 0
            skipped = 0
            for i, src_card in enumerate(cards):
                dst_card = await dst.catalog_col.find_one({"card_id": src_card["card_id"]})
                if not dst_card:
                    console.print(f"  [{i + 1}/{len(cards)}] [yellow]{src_card['card_id']} — not in target env, skipping[/yellow]")
                    skipped += 1
                    continue

                await dst.catalog_col.update_one(
                    {"card_id": src_card["card_id"]},
                    {
                        "$set": {
                            "friendly_description": src_card["friendly_description"],
                            "friendly_description_status": src_card["friendly_description_status"],
                            "friendly_description_error": src_card.get("friendly_description_error"),
                            "friendly_description_updated_at": src_card.get("friendly_description_updated_at"),
                            "description": src_card.get("description", dst_card.get("description", "")),
                        }
                    },
                )
                console.print(f"  [{i + 1}/{len(cards)}] [green]{src_card['card_id']}[/green]")
                matched += 1

            console.print(f"\n[green]Promoted {matched} descriptions ({skipped} skipped).[/green]")
            console.print(f"[yellow]Run /bruh-cards-admin reload in Discord ({target_env} bot) to refresh.[/yellow]")
        finally:
            await dst.close()

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

    def _build_base_prompt(self, name: str, desc: str, visual_mechanics: str = "") -> str:
        return (
            f"A trading card template frame, 768x1024 portrait orientation, "
            f"for the '{name}' card set. {desc} {visual_mechanics} "
            f"Stylized flat-color cartoon illustration with bold clean outlines and cel-shading "
            f"— similar to Hades game art or Castlevania animated series. "
            f"The center shows a subtle gradient background matching the theme. "
            f"CRITICAL: No text, no words, no letters, no card titles, no placeholder text, "
            f"no name plates, no stat boxes — absolutely zero text of any kind. "
            f"No characters, no specific objects — just the atmospheric backdrop and decorative frame elements. "
            f"Color palette and lighting should match the theme description."
        )


async def main():
    parser = argparse.ArgumentParser(description="bruh.bot Card Set Generator — direct to Mongo")
    parser.add_argument("--env", choices=VALID_ENVIRONMENTS, default="dev", help="Environment (default: dev)")

    sub = parser.add_subparsers(dest="command")

    wz = sub.add_parser("wizard", help="Interactive card set creation wizard")
    wz.add_argument("--release", action="store_true", help="Publish in dev and promote-and-publish in prod after generation")
    sub.add_parser("list", help="List all sets in Mongo")
    sub.add_parser("health", help="Check MongoDB and trading-card storage health")

    rs = sub.add_parser("resume", help="Resume an interrupted card generation")
    rs.add_argument("set_id")
    rs.add_argument("--retry-failed", action="store_true", help="Retry failed cards too")

    st = sub.add_parser("status", help="Show set generation status")
    st.add_argument("set_id")

    pb = sub.add_parser("publish", help="Publish a completed set to players")
    pb.add_argument("set_id")

    rl = sub.add_parser("release", help="Publish a completed dev set, then promote and publish it in prod")
    rl.add_argument("set_id")

    ar = sub.add_parser("archive", help="Hide a set from players")
    ar.add_argument("set_id")

    dl = sub.add_parser("delete", help="Permanently delete a set from the selected environment")
    dl.add_argument("set_id")

    pm = sub.add_parser("promote", help="Promote a set to a higher environment")
    pm.add_argument("set_id")
    pm.add_argument("--to", choices=VALID_ENVIRONMENTS, default="prod", help="Target environment (default: prod)")

    pma = sub.add_parser("promote-all", help="Promote every set to a higher environment")
    pma.add_argument("--to", choices=VALID_ENVIRONMENTS, default="prod", help="Target environment (default: prod)")

    ex = sub.add_parser("export", help="Export a set to local files")
    ex.add_argument("set_id")
    ex.add_argument("--output", default="./exports", help="Output directory")

    rc = sub.add_parser("regenerate-card", help="Replace art for one existing card")
    rc.add_argument("set_id")
    rc.add_argument("card_id")
    rc.add_argument("--prompt", default=None, help="Prompt override (default: card description)")
    rc.add_argument("--yes", action="store_true", help="Skip review confirmation")

    ra = sub.add_parser("regenerate-all", help="Regenerate art for ALL cards in a set")
    ra.add_argument("set_id")
    ra.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    ra.add_argument("--skip-base", action="store_true", help="Skip base template regeneration")

    ats = sub.add_parser("apply-theme-story", help="Assign recurring characters and story beats to an existing themed set")
    ats.add_argument("set_id")

    rcs = sub.add_parser("regenerate-character-sheets", help="Replace a themed set's recurring character sheets with approved multi-angle turnarounds")
    rcs.add_argument("set_id")

    up = sub.add_parser("upload-set", help="Upload a pre-generated card set from a folder")
    up.add_argument("set_id")
    up.add_argument("folder", help="Folder containing card images and optional base template")
    up.add_argument("--name", default=None, help="Display name (default: derived from set_id)")
    up.add_argument("--prefix", default=None, help="Filename prefix for card images (default: set_id)")
    up.add_argument("--manifest", default=None, help="Path to manifest.json with card metadata")

    fd = sub.add_parser("generate-friendly-descriptions", help="Backfill friendly descriptions for existing cards")
    fd.add_argument("set_id", nargs="?", default=None, help="Set ID (omit for all sets)")
    fd.add_argument("--force", action="store_true", help="Regenerate descriptions that already exist")
    fd.add_argument("--retry-failed", action="store_true", help="Retry only previously failed descriptions")
    fd.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    pf = sub.add_parser("promote-friendly-descriptions", help="Push friendly descriptions from dev to prod")
    pf.add_argument("set_id", nargs="?", default=None, help="Set ID (omit for all sets)")
    pf.add_argument("--to", default="prod", help="Target environment (default: prod)")
    pf.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    args, unknown = parser.parse_known_args()
    # Allow --env anywhere
    for i, a in enumerate(unknown):
        if a == "--env" and i + 1 < len(unknown):
            args.env = unknown[i + 1]

    if args.env not in VALID_ENVIRONMENTS:
        parser.error(f"argument --env: invalid choice: {args.env!r} (choose from {', '.join(VALID_ENVIRONMENTS)})")

    if not args.command:
        parser.print_help()
        return

    gen = CardSetGenerator(env=args.env)
    try:
        await gen.connect(resolve_credentials=args.command != "health")

        if args.command == "wizard":
            await gen.wizard(auto_release=args.release)
        elif args.command == "list":
            await gen.list_sets()
        elif args.command == "health":
            await gen.health()
        elif args.command == "resume":
            await gen.resume(args.set_id, retry_failed=args.retry_failed)
        elif args.command == "status":
            await gen.status(args.set_id)
        elif args.command == "publish":
            await gen.publish(args.set_id)
        elif args.command == "release":
            await gen.release(args.set_id)
        elif args.command == "archive":
            await gen.archive(args.set_id)
        elif args.command == "delete":
            await gen.delete(args.set_id)
        elif args.command == "promote":
            await gen.promote(args.set_id, args.to)
        elif args.command == "promote-all":
            await gen.promote_all(args.to)
        elif args.command == "export":
            await gen.export_set(args.set_id, args.output)
        elif args.command == "regenerate-card":
            await gen.regenerate_card(args.set_id, args.card_id, prompt_override=args.prompt, yes=args.yes)
        elif args.command == "regenerate-all":
            await gen.regenerate_all(args.set_id, yes=args.yes, skip_base=args.skip_base)
        elif args.command == "apply-theme-story":
            await gen.apply_theme_story(args.set_id)
        elif args.command == "regenerate-character-sheets":
            await gen.regenerate_character_sheets(args.set_id)
        elif args.command == "upload-set":
            await gen.upload_set(args.set_id, args.folder, display_name=args.name, prefix=args.prefix, manifest=args.manifest)
        elif args.command == "generate-friendly-descriptions":
            await gen.backfill_friendly_descriptions(
                set_id=args.set_id,
                force=args.force,
                retry_failed=args.retry_failed,
                yes=args.yes,
            )
        elif args.command == "promote-friendly-descriptions":
            await gen.promote_friendly_descriptions(
                set_id=args.set_id,
                target_env=args.to,
                yes=args.yes,
            )
    finally:
        await gen.pub.close()


if __name__ == "__main__":
    asyncio.run(main())
