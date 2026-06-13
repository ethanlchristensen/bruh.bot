import logging
from logging.config import dictConfig

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

# Create a custom theme for Rich
custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "critical": "bold white on red",
        "success": "bold green",
        "title": "bold blue",
        "subtitle": "italic cyan",
    }
)

console = Console(theme=custom_theme)

# Configure logging with Rich
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"rich": {"format": "%(message)s", "datefmt": "[%X]"}},
    "handlers": {
        "rich_console": {
            "class": "rich.logging.RichHandler",
            "level": "DEBUG",
            "formatter": "rich",
            "markup": True,
            "rich_tracebacks": True,
            "tracebacks_show_locals": False,
            "console": console,
            "show_time": True,
            "show_path": True,
        }
    },
    "loggers": {
        "bot": {"handlers": ["rich_console"], "level": "INFO", "propagate": False},
        "discord": {"handlers": ["rich_console"], "level": "INFO", "propagate": False},
        "httpx": {"handlers": ["rich_console"], "level": "ERROR", "propagate": False},
        "google_genai": {
            "handlers": ["rich_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

dictConfig(LOGGING_CONFIG)

# Get the logger for our bot
logger = logging.getLogger("bot")


def print_startup_banner():
    subtitle = Text("AI-Powered Discord Bot", style="subtitle", justify="center")
    version = Text("v1.0.0", style="dim")

    panel = Panel(
        renderable=subtitle,
        title="Juno",
        subtitle=version,
        border_style="blue",
    )

    console.print(panel)


def load_components(items, load_function, component_type="component"):
    """
    Simplified component loading with basic logging

    Args:
        items: List of items to load
        load_function: Function that loads an item, should return True on success
        component_type: String name of the component type (e.g., "cog", "command")
    """
    total = len(items)
    loaded_successfully = 0

    logger.info(f"📁 Found {total} {component_type}s to load")

    # Process each item with simple logging
    for item in items:
        try:
            success = load_function(item)

            if success:
                loaded_successfully += 1
                logger.info(f"✅ Successfully loaded {component_type}: {item}")
            else:
                logger.error(f"❌ Failed to load {component_type}: {item}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Error loading {component_type} {item}: {error_msg}")

    # Log the final summary
    if loaded_successfully == total:
        logger.info(f"🎉 All {loaded_successfully} {component_type}s loaded successfully!")
    else:
        logger.info(f"📊 {component_type.capitalize()}s loaded: {loaded_successfully}/{total}")
