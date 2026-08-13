"""
Gemini API Client

Thin wrapper around Google Gemini SDK (google-genai >= 2.10, interactions API) for:
- File API upload
- Text generation (chat context chaining via interaction IDs)
- Structured JSON generation
- Image generation (Nano Banana family)

The interactions API is the notebook workflow: upload the book once, then chain
every subsequent step from the previous interaction's ID so Gemini keeps the
history without re-sending the book each time.
"""

from typing import Optional, Dict, Any
from google import genai
from app.config import settings
import json
import logging

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for interacting with Gemini API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client

        Args:
            api_key: Gemini API key (defaults to settings.GEMINI_API_KEY)
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required")

        self.client = genai.Client(api_key=self.api_key)
        self.text_model = settings.GEMINI_TEXT_MODEL
        self.image_model = settings.GEMINI_IMAGE_MODEL

    def upload_file(self, file_path: str, display_name: Optional[str] = None) -> Any:
        """
        Upload a file to Gemini File API

        Args:
            file_path: Path to the file to upload
            display_name: Optional display name for the file

        Returns:
            Uploaded file object with URI
        """
        logger.info(f"Uploading file: {file_path}")
        config = {"display_name": display_name} if display_name else None
        file = self.client.files.upload(file=file_path, config=config)
        logger.info(f"File uploaded successfully: {file.uri}")
        return file

    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        previous_interaction_id: Optional[str] = None,
        file_uri: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Generate text response from Gemini, optionally chaining an interaction.

        Notebook pattern: the book is attached to the first interaction via its
        File API URI so the whole conversation has the book context without
        re-sending the text on later steps.

        Args:
            prompt: Text prompt
            model: Model to use (defaults to configured text model)
            previous_interaction_id: Optional interaction ID for chat context
            file_uri: Optional File API URI to attach as a document part

        Returns:
            Tuple of (generated text response, interaction_id)
        """
        model_to_use = model or self.text_model

        input_data: Any = prompt
        if file_uri:
            input_data = [
                {"type": "text", "text": prompt},
                {"type": "document", "uri": file_uri},
            ]

        if previous_interaction_id:
            interaction = self.client.interactions.create(
                model=model_to_use,
                input=input_data,
                previous_interaction_id=previous_interaction_id,
            )
        else:
            interaction = self.client.interactions.create(
                model=model_to_use,
                input=input_data,
            )
        return interaction.output_text, interaction.id

    def generate_structured_json(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        previous_interaction_id: Optional[str] = None,
    ) -> tuple[Any, str]:
        """
        Generate structured JSON response from Gemini.

        Args:
            prompt: Text prompt
            schema: JSON schema for response structure
            model: Model to use (defaults to configured text model)
            previous_interaction_id: Optional interaction ID for chat context

        Returns:
            Tuple of (parsed JSON response matching schema, interaction_id)
        """
        model_to_use = model or self.text_model

        response_format = {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        }

        if previous_interaction_id:
            interaction = self.client.interactions.create(
                model=model_to_use,
                input=prompt,
                previous_interaction_id=previous_interaction_id,
                response_format=response_format,
            )
        else:
            interaction = self.client.interactions.create(
                model=model_to_use,
                input=prompt,
                response_format=response_format,
            )

        return json.loads(interaction.output_text), interaction.id

    def generate_image_context(
        self,
        prompt: str,
        model: Optional[str] = None,
        previous_interaction_id: Optional[str] = None,
    ) -> str:
        """
        Start (or continue) the image-model conversation with context.

        Notebook pattern: before generating the first portrait we seed the image
        model with the style + system instructions, then chain every portrait
        from that interaction so the characters stay consistent across images.

        Args:
            prompt: Context prompt (style + system instructions)
            model: Image model to use
            previous_interaction_id: Optional interaction ID to chain from

        Returns:
            interaction_id to chain image generation from
        """
        model_to_use = model or self.image_model

        if previous_interaction_id:
            interaction = self.client.interactions.create(
                model=model_to_use,
                input=prompt,
                previous_interaction_id=previous_interaction_id,
            )
        else:
            interaction = self.client.interactions.create(
                model=model_to_use,
                input=prompt,
            )
        return interaction.id

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        previous_interaction_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> tuple[Any, str]:
        """
        Generate an image from Gemini (Nano Banana family).

        Args:
            prompt: Text prompt for image generation (style + system
                instructions are embedded by the pipeline, notebook style)
            aspect_ratio: Aspect ratio (e.g., "9:16", "1:1", "16:9")
            previous_interaction_id: Optional interaction ID for chat context
            model: Image model to use (defaults to configured image model)

        Returns:
            Tuple of (generated image part, interaction_id)
        """
        model_to_use = model or self.image_model

        try:
            if previous_interaction_id:
                interaction = self.client.interactions.create(
                    model=model_to_use,
                    input=prompt,
                    previous_interaction_id=previous_interaction_id,
                    response_modalities=["Image"],
                )
            else:
                interaction = self.client.interactions.create(
                    model=model_to_use,
                    input=prompt,
                    response_modalities=["Image"],
                )

            # Extract image from response steps (notebook pattern)
            for step in reversed(interaction.steps):
                if step.type == "model_output" and step.content:
                    for content in reversed(step.content):
                        if content.type == "image":
                            return content, interaction.id

            raise Exception("No image generated in response")

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise Exception(f"Image generation failed. Error: {str(e)}")