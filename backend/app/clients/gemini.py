"""
Gemini API Client

Thin wrapper around Google Gemini SDK for:
- File API upload
- Text generation
- Structured JSON generation
- Image generation

NOTE: As of January 2026, image generation is PAID-ONLY.
Free tier no longer supports any Nano Banana image models.
See: https://github.com/googleapis/python-genai/issues/1776
"""

from typing import Optional, Dict, Any
from google import genai
from google.genai import types
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
        file = self.client.files.upload(file=file_path, display_name=display_name)
        logger.info(f"File uploaded successfully: {file.uri}")
        return file
    
    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        previous_interaction_id: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Generate text response from Gemini
        
        Args:
            prompt: Text prompt
            model: Model to use (defaults to configured text model)
            previous_interaction_id: Optional interaction ID for chat context
            
        Returns:
            Tuple of (generated text response, interaction_id)
        """
        model_to_use = model or self.text_model
        
        if previous_interaction_id:
            # Continue existing conversation
            interaction = self.client.interactions.create(
                model=model_to_use,
                input=prompt,
                previous_interaction_id=previous_interaction_id
            )
            return interaction.output_text, interaction.id
        else:
            # Start new conversation
            interaction = self.client.interactions.create(
                model=model_to_use,
                input=prompt
            )
            return interaction.output_text, interaction.id
    
    def generate_structured_json(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        previous_interaction_id: Optional[str] = None
    ) -> tuple[Dict[str, Any], str]:
        """
        Generate structured JSON response from Gemini
        
        Args:
            prompt: Text prompt
            schema: JSON schema for response structure
            model: Model to use (defaults to configured text model)
            previous_interaction_id: Optional interaction ID for chat context
            
        Returns:
            Tuple of (parsed JSON response matching schema, interaction_id)
        """
        model_to_use = model or self.text_model
        
        if previous_interaction_id:
            interaction = self.client.interactions.create(
                model=model_to_use,
                input=prompt,
                previous_interaction_id=previous_interaction_id,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema,
                }
            )
        else:
            interaction = self.client.interactions.create(
                model=model_to_use,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema,
                }
            )
        
        return json.loads(interaction.output_text), interaction.id
    
    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        previous_interaction_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> tuple[Any, str]:
        """
        Generate image from Gemini (PAID-ONLY)
        
        WARNING: As of January 2026, image generation is PAID-ONLY.
        Free tier no longer supports any Nano Banana image models.
        This method will fail without billing enabled.
        
        Args:
            prompt: Text prompt for image generation
            aspect_ratio: Aspect ratio (e.g., "9:16", "1:1", "16:9")
            previous_interaction_id: Optional interaction ID for chat context
            model: Image model to use (defaults to configured image model)
            
        Returns:
            Tuple of (generated image part, interaction_id)
            
        Raises:
            Exception: If billing is not enabled or quota exceeded
        """
        model_to_use = model or self.image_model
        
        logger.warning(
            f"Image generation requires billing. Using model: {model_to_use}. "
            "Free tier no longer supports image generation."
        )
        
        # Build the prompt with style instructions
        system_instructions = """
        There must be no text on the image, it should not look like a cover page.
        It should be a full illustration with no borders, titles, nor description.
        Unless asked otherwise, stay family-friendly with uplifting colors.
        Each produced should be a simple image, no panels.
        """
        
        full_prompt = f"{system_instructions}\n\n{prompt}"
        
        try:
            if previous_interaction_id:
                # Continue existing conversation with image generation
                interaction = self.client.interactions.create(
                    model=model_to_use,
                    input=full_prompt,
                    previous_interaction_id=previous_interaction_id,
                    response_modalities=["Image"]
                )
            else:
                # Start new conversation with image generation
                interaction = self.client.interactions.create(
                    model=model_to_use,
                    input=full_prompt,
                    response_modalities=["Image"]
                )
            
            # Extract image from response
            for step in reversed(interaction.steps):
                if step.type == "model_output" and step.content:
                    for content in reversed(step.content):
                        if content.type == "image":
                            return content, interaction.id
            
            raise Exception("No image generated in response")
            
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise Exception(
                f"Image generation failed. This requires billing. Error: {str(e)}"
            )
    
    def extract_image_from_interaction(self, interaction: Any) -> Optional[Any]:
        """
        Extract image from an interaction response
        
        Args:
            interaction: Gemini interaction object
            
        Returns:
            Image part if found, None otherwise
        """
        for step in reversed(interaction.steps):
            if step.type == "model_output" and step.content:
                for content in reversed(step.content):
                    if content.type == "image":
                        return content
        return None
