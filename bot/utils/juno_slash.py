import logging
import os

from discord import app_commands

from bot import settings

logger = logging.getLogger("bot")


class SlashLoader:
    def __init__(self, tree: app_commands.CommandTree):
        self.path = os.path.join(os.getcwd(), "bot", "commands")
        self.tree = tree

    async def load_commands(self, args=None):
        logger.info(f"📁 Looking for commangs in: {self.path}")
        command_files = [f[:-3] for f in os.listdir(self.path) if f.endswith(".py") and f not in ["__pycache__", "__init__.py"]]

        # Define the load function for a command
        def load_command(file_name):
            class_name = "".join(word.capitalize() for word in file_name.split("_"))
            try:
                command = self.import_from(f"bot.commands.{file_name}", class_name)
                command(self.tree, args=args)
                return True
            except Exception as e:
                logger.error(f"Error details for {class_name}: {str(e)}")
                return False

        # Use the utility function to load commands with visual feedback
        settings.load_components(command_files, load_command, "command")

    def get_next_command(self):
        for file in os.listdir(self.path):
            if file.endswith(".py") and file not in ["__pycache__", "__init__.py"]:
                yield file[:-3]

    @staticmethod
    def import_from(module: str, name: str):
        module = __import__(module, fromlist=[name])
        return getattr(module, name)
