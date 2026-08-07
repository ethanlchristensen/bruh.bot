import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from bot.bruh_bot import BruhBot
from bot.services.ai.gateway.schemas.request import Message, MessagePart
from bot.services.ai.image_generation_service import ImageGenerationService
from bot.services.memory_extraction_service import MemoryExtractionService
from bot.services.memory_tools import MemoryToolExecutor
from bot.services.message_service import MessageService
from bot.services.mongo_reputation_service import REPUTATION_DELTAS, MongoReputationService
from bot.services.reputation_extraction_service import ReputationExtractionService


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
    def __init__(self, memories_enabled=False, reputation_enabled=False):
        self.config = SimpleNamespace(
            aiConfig=SimpleNamespace(systemPrompt="You are Bruh."),
            memoryConfig=SimpleNamespace(
                enabled=memories_enabled,
                maxInjectionCount=8,
                minMessageLength=3,
                semanticRetrieval=False,
            ),
            reputationConfig=SimpleNamespace(enabled=reputation_enabled, minMessageLength=3, minMessagesForExtraction=10, maxMessagesPerExtraction=30, maxExtractionWaitMinutes=60, extractionIntervalMinutes=15),
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
        author=SimpleNamespace(id=author_id, name=author_name, display_name=author_name, bot=False),
        content=content,
        mentions=list(mentions),
        attachments=[],
        created_at=None,
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
        reference = SimpleNamespace(id=20, author=SimpleNamespace(id=2, name="Alice", display_name="Alice"), content="Can someone explain this?", attachments=[], mentions=[])
        path = [{"_id": 30, "role": "user", "content": message.content, "author_name": "Bob"}]
        service, bot = self.make_service(path)

        context = await service.build_message_context(message, reference, "Bob")

        self.assertIsNone(bot.chat_service.saved[0]["parent_id"])
        self.assertEqual(context[1].parts[0].text, "[Alice] (message being replied to): Can someone explain this?")

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


class MemoryExtractionContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_bot_responses_are_not_enqueued_to_memory_queue(self):
        queued = []

        async def enqueue(**kwargs):
            queued.append(kwargs)

        bot = SimpleNamespace(
            user=SimpleNamespace(id=999, name="bruh.bot"),
            config_service=FakeConfigService(memories_enabled=True),
            extraction_queue_service=SimpleNamespace(enqueue=enqueue),
        )
        service = MemoryExtractionService(bot)
        human_message = fake_message(30, 3, "Bob", "hello bot")

        await service.enqueue_message(human_message)
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["author_id"], 3)

    async def test_bot_memory_operation_is_rejected_even_if_its_id_is_allowlisted(self):
        bot = SimpleNamespace(user=SimpleNamespace(id=999))
        executor = MemoryToolExecutor(
            bot=bot,
            guild_id=100,
            valid_user_ids={999},
            id_to_users={},
            users_to_id={},
            mem_cfg=SimpleNamespace(),
        )

        result = await executor.execute("add_memory", {"user_id": 999, "memory": "is a bot"})

        self.assertEqual(result["error"], "Bot memories cannot be created")


class ReputationExtractionContextTests(unittest.IsolatedAsyncioTestCase):
    def test_reputation_deltas_reward_good_interactions_and_penalize_harmful_ones(self):
        self.assertGreater(REPUTATION_DELTAS["helpful_interaction"][2], 0)
        self.assertGreater(REPUTATION_DELTAS["respectful_interaction"][2], 0)
        self.assertLess(REPUTATION_DELTAS["bot_targeted_abuse"][2], 0)

    def test_reputation_timestamps_are_normalized_to_utc(self):
        self.assertEqual(MongoReputationService._as_utc(datetime.now()).tzinfo, UTC)

    async def test_naive_queue_timestamp_does_not_break_batch_wait_check(self):
        async def count(_guild_id):
            return 1

        async def get_oldest_timestamp(_guild_id):
            return datetime.now(UTC).replace(tzinfo=None)

        bot = SimpleNamespace(
            config_service=FakeConfigService(reputation_enabled=True),
            reputation_queue_service=SimpleNamespace(count=count, get_oldest_timestamp=get_oldest_timestamp),
        )

        await ReputationExtractionService(bot)._process_guild(100)

    async def test_human_and_bot_turns_are_staged_with_distinct_roles(self):
        queued = []

        async def enqueue(*args, **kwargs):
            queued.append((args, kwargs))

        bot = SimpleNamespace(
            user=SimpleNamespace(id=999, name="bruh.bot"),
            config_service=FakeConfigService(reputation_enabled=True),
            reputation_queue_service=SimpleNamespace(enqueue=enqueue),
        )
        service = ReputationExtractionService(bot)
        human = fake_message(30, 3, "Bob", "hello bot")
        response = SimpleNamespace(id=31, guild=SimpleNamespace(id=100), channel=SimpleNamespace(id=200), author=SimpleNamespace(id=999), created_at=None)

        await service.enqueue_message(human)
        await service.enqueue_bot_context(response, "Hello Bob")

        self.assertFalse(queued[0][1].get("context_only", False))
        self.assertTrue(queued[1][1]["context_only"])
        self.assertEqual(queued[1][0][4], 999)

    async def test_other_bot_messages_are_not_staged_as_context(self):
        queued = []

        async def enqueue(*args, **kwargs):
            queued.append((args, kwargs))

        bot = SimpleNamespace(
            user=SimpleNamespace(id=999, name="bruh.bot"),
            config_service=FakeConfigService(reputation_enabled=True),
            reputation_queue_service=SimpleNamespace(enqueue=enqueue),
        )
        other_bot_message = SimpleNamespace(id=31, guild=SimpleNamespace(id=100), channel=SimpleNamespace(id=200), author=SimpleNamespace(id=123), created_at=None)

        await ReputationExtractionService(bot).enqueue_bot_context(other_bot_message, "External bot output")

        self.assertEqual(queued, [])


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
            user=SimpleNamespace(id=999, name="bruh.bot"),
            message_service=context_builder,
            image_limit_service=SimpleNamespace(can_generate_image=self._can_generate),
            ai_usage_service=SimpleNamespace(consume_request=self._consume_request),
            image_generation_service=image_service,
            response_service=SimpleNamespace(send_response=self._send_response),
            chat_service=SimpleNamespace(save_message=self._save_message),
            reputation_extraction_service=SimpleNamespace(enqueue_bot_context=self._enqueue_reputation_context),
            logger=SimpleNamespace(info=lambda *_args: None),
        )
        message = fake_message(30, 3, "Bob", "<@999> draw a city")

        await BruhBot._handle_image_generation_intent(bot, message, reference_message=None)

        self.assertEqual(self.context_include_current_images, False)
        self.assertIs(self.generate_kwargs["messages"], messages)
        self.assertEqual(self.saved_messages[0]["parent_id"], 30)
        self.assertEqual(self.saved_messages[0]["role"], "assistant")
        self.assertEqual(self.reputation_context["content"], "Here is your city.")

    async def _can_generate(self, _message):
        return True, ""

    async def _consume_request(self, _user_id, _guild_id):
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
        return SimpleNamespace(id=31, guild=SimpleNamespace(id=100), created_at=None)

    async def _save_message(self, **kwargs):
        self.saved_messages.append(kwargs)

    async def _enqueue_reputation_context(self, _message, content):
        self.reputation_context = {"content": content}


if __name__ == "__main__":
    unittest.main()
