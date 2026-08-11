# card_gen — bruh.cards Trading Card Generator

CLI tool for creating, publishing, and maintaining trading card sets directly in MongoDB + GridFS.

## Prerequisites

- Python dependencies installed via Poetry
- MongoDB running and `config/base_config.yaml` configured with a valid `mongoUri`
- An OpenRouter API key (set via `OPENROUTER_API_KEY` env var, or present in a MongoDB config doc)

All commands accept `--env dev|prod` (defaults to `dev`). The `--env` flag can appear anywhere in the command.

## Quick Start

```powershell
# Create a brand new card set (interactive wizard)
poetry run python tools/card_gen.py wizard --env dev

# See what sets exist
poetry run python tools/card_gen.py list --env dev
```

## Complete Workflow

### 1. Create a set (`wizard`)

Prompts you for a set ID, display name, theme description, rarity themes, then generates all 50 card names/descriptions via AI, a base template image, and default standard/premium pack definitions. After approval, generates and uploads all 50 card images to GridFS.

```powershell
poetry run python tools/card_gen.py wizard --env dev
```

If generation is interrupted, resume with:

```powershell
poetry run python tools/card_gen.py resume my_set --env dev
poetry run python tools/card_gen.py resume my_set --retry-failed --env dev
```

### 2. Check status (`status`)

```powershell
poetry run python tools/card_gen.py status my_set --env dev
```

Output:
```
Moss And Sunbeam
Status: ready | Released: no
Cards: 50 total | 50 ready | 0 pending | 0 failed
All cards ready! Publish with: poetry run python tools/card_gen.py publish my_set --env dev
```

### 3. Publish to players (`publish`)

Marks all cards and packs in the set as `released: true`. Players can then see and pull them from packs after a catalog reload.

```powershell
poetry run python tools/card_gen.py publish my_set --env dev
```

After publishing, in Discord run:

```
/bruh-cards-admin reload
```

### 4. Promote to production (`promote`)

Copies the entire set (metadata, cards, art, packs) from dev to prod environments.

```powershell
poetry run python tools/card_gen.py promote my_set --env dev
```

> The `--to` flag defaults to `prod`. After promotion, run `/bruh-cards-admin reload` on the prod bot.

### 5. Managing packs

After publishing, use the admin dashboard **Card Packs** page (`/config/card-packs`) to:

- **View** all collections and their eligible cards with rendered images
- **Edit** pack price and guaranteed rarity per pack
- **Create** new pack types in a collection

Or use the CLI to add packs to an existing set:

```powershell
# Packs are created in the wizard automatically.
# To add a new pack type, use the admin dashboard's Card Packs page.
```

### 6. Replace a card's art (`regenerate-card`)

Re-generates the image for a single existing card without changing its name, rarity, description, or collection membership. Useful when one card's art doesn't fit the set.

```powershell
# Use the card's existing description as the prompt (interactive review)
poetry run python tools/card_gen.py regenerate-card moss_and_sunbeam moss_and_sunbeam_014 --env dev

# With a custom prompt override (interactive review)
poetry run python tools/card_gen.py regenerate-card moss_and_sunbeam moss_and_sunbeam_014 --prompt "A ghostly fox in moonlight, watercolor style" --env dev

# Skip review confirmation for scripting
poetry run python tools/card_gen.py regenerate-card moss_and_sunbeam moss_and_sunbeam_014 --yes --env dev
```

During interactive mode the image opens for review. You can `approve`, `retry` (with a prompt tweak), or `cancel`.

After regeneration, run `/bruh-cards-admin reload` in Discord. The admin dashboard will pick up the new image automatically.

### 7. Archive a set (`archive`)

Hides a set from players without deleting data.

```powershell
poetry run python tools/card_gen.py archive my_set --env dev
```

### 8. Export a set (`export`)

Downloads a set's metadata and all card art to local files.

```powershell
poetry run python tools/card_gen.py export my_set --output ./exports --env dev
```

Exports to `./exports/my_set/`:
- `set.json` — full metadata including all card definitions and pack configs
- `base_template.png` — the collection's base template
- One `.png` per card with ready art

## Command Reference

| Command | Arguments | Description |
|---|---|---|
| `wizard` | — | Interactive creation of a full 50-card set |
| `list` | — | Show all sets in the target environment |
| `status` | `<set_id>` | Card generation progress (ready/pending/failed) |
| `resume` | `<set_id> [--retry-failed]` | Continue/resume interrupted generation |
| `publish` | `<set_id>` | Mark all cards & packs as released |
| `archive` | `<set_id>` | Hide a set from players |
| `promote` | `<set_id> [--to prod]` | Copy set from current env to another |
| `export` | `<set_id> [--output ./exports]` | Download set metadata and art to disk |
| `regenerate-card` | `<set_id> <card_id> [--prompt ...] [--yes]` | Replace one card's image |

## Environments

- **dev** — Development/testing. All commands default here. Safe to experiment.
- **prod** — Production. Use `promote` to move sets from dev to prod once ready.

## After Any Change

Run this in Discord to reload the bot's in-memory catalog and clear render caches:

```
/bruh-cards-admin reload
```
