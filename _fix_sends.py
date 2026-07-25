import os

base = os.path.join(os.getcwd())

# Files and their embed variable names (most use 'embed', music_player uses 'now_playing_embed')
special_files = {
    "bot/services/music/music_player.py": "now_playing_embed",
}

files = [
    "bot/cogs/music.py",
    "bot/cogs/scheduler.py",
    "bot/services/music/music_player.py",
    "bot/utils/decarators/admin_check.py",
    "bot/utils/decarators/global_block_check.py",
    "bot/commands/chat_command.py",
    "bot/commands/ping_command.py",
    "bot/commands/sync_command.py",
    "bot/commands/describe_command.py",
    "bot/commands/image_stats_command.py",
    "bot/commands/image_admin_command.py",
    "bot/commands/memory_command.py",
]

for filepath in files:
    fullpath = os.path.join(base, filepath)
    var_name = special_files.get(filepath, "embed")

    with open(fullpath, encoding="utf-8") as f:
        content = f.read()

    old = "get_brand_files())"
    new = f"get_brand_files(embed={var_name}))"

    # Only replace if not already done
    if old in content:
        content = content.replace(old, new)
        with open(fullpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated {filepath} ({old} -> {new})")
    else:
        print(f"Skipped {filepath} (pattern not found or already updated)")

print("Done!")
