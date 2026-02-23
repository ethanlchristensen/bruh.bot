import logging
from io import BytesIO
from typing import TYPE_CHECKING

import aiohttp
from google.genai import Client
from PIL import Image

from bot.services.ai.ai_service_factory import AiServiceFactory

from .types import ImageGenerationResponse, Message, Role

if TYPE_CHECKING:
    from bot.juno import Juno

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """Service for generating and editing images using Gemini AI."""

    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.base_prompt = "You must generate an image with the following user prompt. Do not ask follow questions to get the user to refine the prompt."

    async def boost_prompt(self, guild_id: int, user_prompt: str, image_description: str | None = None) -> str:
        try:
            logger.info(f"Boosting prompt: {user_prompt}")

            system_message = Message(
                role=Role.SYSTEM,
                content="""You are a prompt enhancement specialist for image generation AI.
Your job is to take user prompts and enhance them with specific details about composition,
lighting, style, colors, mood, and technical aspects that will help generate better images.
Keep the core intent of the user's request while adding helpful details.
Return ONLY the enhanced prompt, no explanations or commentary.""",
            )

            if image_description:
                user_message = Message(
                    role=Role.USER,
                    content=f"""Original image description: {image_description}

User's edit request: {user_prompt}

Please enhance this edit request with specific details while maintaining the context of the original image.""",
                )
            else:
                user_message = Message(
                    role=Role.USER,
                    content=f"User prompt: {user_prompt}\n\nPlease enhance this prompt with specific details for image generation.",
                )

            config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig
            ai_service = AiServiceFactory.get_service(self.bot, config.preferredAiProvider)

            response = await ai_service.chat(guild_id, messages=[system_message, user_message])
            boosted_prompt = response.content.strip()

            logger.info(f"Boosted prompt: {boosted_prompt}")
            return boosted_prompt

        except Exception as e:
            logger.error(f"Error boosting prompt: {e}", exc_info=True)
            return user_prompt

    async def describe_image(self, guild_id: int, image: Image.Image) -> str:
        try:
            logger.info("Generating image description")

            buffered = BytesIO()
            image.save(buffered, format="PNG")
            import base64

            img_str = base64.b64encode(buffered.getvalue()).decode()

            system_message = Message(
                role=Role.SYSTEM,
                content="""You are an image analysis expert. Describe the image in detail,
including composition, subjects, colors, lighting, mood, style, and any notable elements.
Be specific and thorough as this description will be used for image editing context.""",
            )

            user_message = Message(
                role=Role.USER,
                content="Please describe this image in detail.",
                images=[{"type": "image/png", "data": img_str}],
            )

            config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig
            ai_service = AiServiceFactory.get_service(self.bot, config.preferredAiProvider)

            response = await ai_service.chat(guild_id, messages=[system_message, user_message])
            description = response.content.strip()

            logger.info(f"Generated description: {description[:100]}...")
            return description

        except Exception as e:
            logger.error(f"Error describing image: {e}", exc_info=True)
            return "Unable to describe image"

    async def download_image_from_url(self, url: str) -> Image.Image | None:
        try:
            logger.info(f"Downloading image from: {url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()
                        image = Image.open(BytesIO(image_data))
                        logger.info("Image downloaded successfully")
                        return image
                    else:
                        logger.error(f"Failed to download image: HTTP {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading image: {e}", exc_info=True)
            return None

    async def download_images_from_urls(self, urls: list[str]) -> list[Image.Image]:
        images = []
        for url in urls:
            image = await self.download_image_from_url(url)
            if image:
                images.append(image)
        return images

    async def generate_image(self, guild_id: int, prompt: str) -> ImageGenerationResponse | None:
        try:
            config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig

            boosted_prompt = prompt
            if config.imageGeneration.boostImagePrompts:
                boosted_prompt = await self.boost_prompt(guild_id, prompt)

            logger.info(f"Generating image with {'boosted ' if config.imageGeneration.boostImagePrompts else ''}prompt: {boosted_prompt}")

            client = Client(api_key=config.google.apiKey.get_secret_value())

            response = await client.aio.models.generate_content(
                model=config.imageGeneration.preferredModel,
                contents=[self.base_prompt, boosted_prompt],
            )

            image_generation_response = ImageGenerationResponse()

            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        image = Image.open(BytesIO(part.inline_data.data))
                        image_generation_response.generated_image = image
                        logger.info("Image generated successfully")
                    elif part.text is not None:
                        image_generation_response.text_response = part.text
                        logger.info(f"Received text response: {part.text}")

            return image_generation_response

        except Exception as e:
            logger.error(f"Error generating image: {e}", exc_info=True)
            return None

    async def edit_image(self, guild_id: int, prompt: str, source_images: list[Image.Image]) -> ImageGenerationResponse | None:
        try:
            config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig

            if config.boostImagePrompts and source_images:
                descriptions = []
                for idx, img in enumerate(source_images, 1):
                    desc = await self.describe_image(guild_id, img)
                    descriptions.append(f"Image {idx}: {desc}")

                combined_description = "\n\n".join(descriptions)
                boosted_prompt = await self.boost_prompt(guild_id, prompt, combined_description)
                logger.info(f"Editing {len(source_images)} image(s) with boosted prompt: {boosted_prompt}")
            else:
                boosted_prompt = prompt

            contents = [self.base_prompt, boosted_prompt]
            contents.extend(source_images)

            google_config = config.google
            client = Client(api_key=google_config.apiKey.get_secret_value())

            response = await client.aio.models.generate_content(
                model=google_config.preferredModel,
                contents=contents,
            )

            if response.candidates[0].finish_reason and response.candidates[0].finish_reason.name == "IMAGE_SAFETY":
                logger.warning(f"Image generation blocked by IMAGE_SAFETY for prompt: {boosted_prompt}")
                image_generation_response = ImageGenerationResponse()
                image_generation_response.text_response = "Image generation was blocked due to safety filters. Please try a different prompt."
                return image_generation_response

            image_generation_response = ImageGenerationResponse()

            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image = Image.open(BytesIO(part.inline_data.data))
                    image_generation_response.generated_image = image
                    logger.info("Image edited successfully")
                elif part.text is not None:
                    image_generation_response.text_response = part.text
                    logger.info(f"Received text response: {part.text}")

            return image_generation_response

        except Exception as e:
            logger.error(f"Error editing image: {e}", exc_info=True)
            return None

    async def edit_image_from_url(self, guild_id: int, prompt: str, image_url: str) -> ImageGenerationResponse | None:
        source_image = await self.download_image_from_url(image_url)
        if source_image is None:
            return None

        return await self.edit_image(guild_id, prompt, [source_image])

    async def edit_images_from_urls(self, guild_id: int, prompt: str, image_urls: list[str]) -> ImageGenerationResponse | None:
        source_images = await self.download_images_from_urls(image_urls)
        if not source_images:
            logger.error("No images could be downloaded")
            return None

        logger.info(f"Successfully downloaded {len(source_images)}/{len(image_urls)} images")
        return await self.edit_image(guild_id, prompt, source_images)

    def image_to_bytes(self, image: Image.Image, format: str = "PNG") -> BytesIO:
        output = BytesIO()
        image.save(output, format=format)
        output.seek(0)
        return output

    async def save_image(self, image: Image.Image, filepath: str) -> bool:
        try:
            image.save(filepath)
            logger.info(f"Image saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving image to {filepath}: {e}", exc_info=True)
            return False
