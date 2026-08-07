import unittest
from types import SimpleNamespace

from bot.bruh_bot import BruhBot
from bot.services.ai.gateway.schemas.request import Message, MessagePart
from bot.services.ai.image_generation_service import ImageGenerationService
from bot.services.message_service import MessageService


class FakeChatService:
    def __init__(self, path):
        self.path = path
        self.saved = []

    async def save_message(self, **kwargs):
        self.saved.append(kwargs)

    async def get_conversation_path(self, _message_id):
        return self.path


class FakeMemoryService:
    def __init__(self):
        self.requested_users = []

    async def get_memories_for_user(self, guild_id, user_id, limit):
        self.requested_users.append(user_id)
        if user_id == 2:
            return [{"memory": "loves noir movies", "category": "trait"}]
        return []

    async def get_memories_for_users(self, **_kwargs):
        return {}


class FakeConfigService:
    def __init__(self, memories_enabled=False):
        self.config = SimpleNamespace(
            aiConfig=SimpleNamespace(systemPrompt="You are Bruh."),
            memoryConfig=SimpleNamespace(
                enabled=memories_enabled,
                maxInjectionCount=8,
                semanticRetrieval=False,
            ),
            idToUsers={"2": "Alice", "3": "Bob"},
            usersToId={"Alice": "2", "Bob": "3"},
        )

    async def get_config(self, _guild_id):
        return self.config


def fake_message(message_id, author_id, author_name, content, mentions=()):
    return SimpleNamespace(
        id=message_id,
        guild=SimpleNamespace(id=100),
        channel=SimpleNamespace(id=200),
        author=SimpleNamespace(id=author_id, name=author_name),
        content=content,
        mentions=list(mentions),
        attachments=[],
    )


class MessageContextTests(unittest.IsolatedAsyncioTestCase):
    def make_service(self, path, memories_enabled=False):
        bot = SimpleNamespace(
            user=SimpleNamespace(id=999, name="bruh.bot"),
            chat_service=FakeChatService(path),
            config_service=FakeConfigService(memories_enabled),
            memory_service=FakeMemoryService(),
        )
        return MessageService(bot), bot

    async def test_direct_mention_starts_a_root_thread(self):
        message = fake_message(30, 3, "Bob", "<@999> start a new topic")
        path = [{"_id": 30, "role": "user", "content": message.content, "author_name": "Bob"}]
        service, bot = self.make_service(path)

        await service.build_message_context(message, reference_message=None, username="Bob")

        self.assertIsNone(bot.chat_service.saved[0]["parent_id"])

    async def test_bot_nickname_mention_starts_a_conversation(self):
        message = fake_message(30, 3, "Bob", "<@!999> hello", mentions=(SimpleNamespace(id=999, name="bruh.bot"),))
        path = [{"_id": 30, "role": "user", "content": message.content, "author_name": "Bob"}]
        service, bot = self.make_service(path)

        self.assertTrue(await service.should_respond_to_message(message, reference_message=None))
        await service.build_message_context(message, reference_message=None, username="Bob")
        self.assertIsNone(bot.chat_service.saved[0]["parent_id"])

    async def test_reply_to_bot_message_uses_only_that_branch_history(self):
        message = fake_message(30, 3, "Bob", "continue this branch")
        reference = SimpleNamespace(id=20, author=SimpleNamespace(id=999))
        path = [
            {"_id": 10, "role": "user", "content": "<@999> first topic", "author_name": "Bob"},
            {"_id": 20, "role": "assistant", "content": "first answer", "author_name": None},
            {"_id": 30, "role": "user", "content": "continue this branch", "author_name": "Bob"},
        ]
        service, bot = self.make_service(path)

        context = await service.build_message_context(message, reference, "Bob")

        self.assertEqual(bot.chat_service.saved[0]["parent_id"], 20)
        self.assertEqual([part.text for item in context[1:] for part in item.parts], ["[Bob]: first topic", "first answer", "[Bob]: continue this branch"])

    async def test_assistant_prefix_is_removed_from_model_output(self):
        service, _bot = self.make_service([])

        self.assertEqual(service.strip_assistant_prefix("[bruh.bot]: hello"), "hello")
        self.assertEqual(service.strip_assistant_prefix("bruh.bot: hello"), "hello")
        self.assertEqual(service.strip_assistant_prefix("[Bob]: hello"), "[Bob]: hello")

    async def test_mention_replying_to_a_user_starts_a_root_thread(self):
        message = fake_message(30, 3, "Bob", "<@999> start another topic")
        reference = SimpleNamespace(id=20, author=SimpleNamespace(id=2))
        path = [{"_id": 30, "role": "user", "content": message.content, "author_name": "Bob"}]
        service, bot = self.make_service(path)

        await service.build_message_context(message, reference, "Bob")

        self.assertIsNone(bot.chat_service.saved[0]["parent_id"])

    async def test_ancestor_mentions_keep_their_memories_in_a_reply_branch(self):
        message = fake_message(30, 3, "Bob", "what should we watch?")
        reference = SimpleNamespace(id=20, author=SimpleNamespace(id=999))
        path = [
            {"_id": 10, "role": "user", "content": "<@999> recommend something for <@2>", "author_name": "Bob"},
            {"_id": 20, "role": "assistant", "content": "Try a noir film.", "author_name": None},
            {"_id": 30, "role": "user", "content": "what should we watch?", "author_name": "Bob"},
        ]
        service, bot = self.make_service(path, memories_enabled=True)

        context = await service.build_message_context(message, reference, "Bob")

        self.assertIn(2, bot.memory_service.requested_users)
        self.assertIn("ABOUT @Alice", context[0].parts[0].text)


class ImageGenerationContextTests(unittest.TestCase):
    def test_generation_context_preserves_history_without_mutating_chat_context(self):
        service = ImageGenerationService(SimpleNamespace())
        messages = [
            Message(role="system", parts=[MessagePart(type="text", text="chat instructions")]),
            Message(role="user", parts=[MessagePart(type="text", text="[Bob]: draw a city")]),
        ]

        context = service._build_generation_context(messages, "a neon city at night")

        self.assertEqual(context[0].parts[0].text, service.base_prompt)
        self.assertEqual(context[1].parts[0].text, "chat instructions")
        self.assertEqual(context[-1].parts[0].text, "a neon city at night")
        self.assertEqual(messages[-1].parts[0].text, "[Bob]: draw a city")


class ImageIntentPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_image_turn_uses_shared_context_and_saves_assistant_response(self):
        messages = [Message(role="system", parts=[MessagePart(type="text", text="memories")]), Message(role="user", parts=[MessagePart(type="text", text="[Bob]: draw a city")])]
        self.generated_messages = messages
        self.saved_messages = []
        context_builder = SimpleNamespace(
            build_message_context=self._build_context,
            get_image_attachments=self._get_attachments,
            strip_assistant_prefix=lambda text: text,
        )
        image_service = SimpleNamespace(generate_image=self._generate_image)
        bot = SimpleNamespace(
            message_service=context_builder,
            image_limit_service=SimpleNamespace(can_generate_image=self._can_generate),
            image_generation_service=image_service,
            response_service=SimpleNamespace(send_response=self._send_response),
            chat_service=SimpleNamespace(save_message=self._save_message),
            logger=SimpleNamespace(info=lambda *_args: None),
        )
        message = fake_message(30, 3, "Bob", "<@999> draw a city")

        await BruhBot._handle_image_generation_intent(bot, message, reference_message=None)

        self.assertEqual(self.context_include_current_images, False)
        self.assertIs(self.generate_kwargs["messages"], messages)
        self.assertEqual(self.saved_messages[0]["parent_id"], 30)
        self.assertEqual(self.saved_messages[0]["role"], "assistant")

    async def _can_generate(self, _message):
        return True, ""

    async def _build_context(self, _message, _reference, _username, include_current_images):
        self.context_include_current_images = include_current_images
        return self.generated_messages

    async def _get_attachments(self, _message, _reference):
        return []

    async def _generate_image(self, **kwargs):
        self.generate_kwargs = kwargs
        return SimpleNamespace(generated_image=None, text_response="Here is your city.")

    async def _send_response(self, _message, _content, _image_file=None):
        return SimpleNamespace(id=31)

    async def _save_message(self, **kwargs):
        self.saved_messages.append(kwargs)


if __name__ == "__main__":
    unittest.main()
