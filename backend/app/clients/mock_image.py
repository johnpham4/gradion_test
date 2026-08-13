"""
Mock Image Client for Development/Testing

Generates placeholder images without calling external APIs.
Useful for development when API keys are not available or for testing purposes.
"""

from typing import Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFont
import os
import time
from loguru import logger


class MockImageClient:
    """Mock client for image generation without external API calls"""
    
    def __init__(self, output_dir: str = "data/mock_images"):
        """
        Initialize mock image client
        
        Args:
            output_dir: Directory to save generated mock images
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"MockImageClient initialized with output dir: {output_dir}")
    
    def generate_image_context(
        self,
        prompt: str,
        model: Optional[str] = None,
        previous_interaction_id: Optional[str] = None
    ) -> str:
        """
        Return a synthetic interaction ID for context chaining.

        Mirrors the Gemini image context interaction (notebook pattern) so the
        pipeline code is provider-agnostic. The mock ignores the prompt.
        """
        interaction_id = f"mock_interaction_context_{abs(hash(prompt)) % 100000}"
        logger.info(f"Mock image context created: {interaction_id}")
        return interaction_id

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        previous_interaction_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Generate a mock image based on prompt
        
        Args:
            prompt: Text prompt for image generation
            aspect_ratio: Aspect ratio (e.g., "9:16", "1:1", "16:9")
            previous_interaction_id: Optional interaction ID (ignored in mock)
            model: Model name (ignored in mock)
            
        Returns:
            Tuple of (image_path, interaction_id)
        """
        start_time = time.time()
        logger.info(f"Generating mock image for prompt: {prompt[:50]}...")
        
        # Parse aspect ratio
        width, height = self._parse_aspect_ratio(aspect_ratio)
        
        # Create image with gradient background
        image = self._create_gradient_image(width, height, prompt)
        
        # Add text overlay
        self._add_text_overlay(image, prompt, width, height)
        
        # Save image
        filename = self._generate_filename(prompt)
        image_path = os.path.join(self.output_dir, filename)
        image.save(image_path)

        logger.success(f"Mock image saved to: {image_path}")

        # Return mock interaction ID
        interaction_id = f"mock_interaction_{abs(hash(prompt)) % 10000}"

        elapsed = time.time() - start_time
        logger.success(f"Mock image generation completed in {elapsed:.2f}s")

        # Normalize to forward slashes so the path works as a URL segment
        return image_path.replace(os.sep, "/"), interaction_id
    
    def _parse_aspect_ratio(self, aspect_ratio: str) -> tuple[int, int]:
        """Parse aspect ratio string to width, height"""
        ratio_map = {
            "9:16": (540, 960),
            "1:1": (512, 512),
            "16:9": (960, 540),
            "3:4": (600, 800),
            "4:3": (800, 600),
            "4:5": (640, 800),
            "5:4": (800, 640)
        }
        return ratio_map.get(aspect_ratio, (540, 960))
    
    def _create_gradient_image(self, width: int, height: int, prompt: str) -> Image.Image:
        """Create a gradient background based on prompt hash"""
        # Generate colors from prompt hash
        prompt_hash = hash(prompt)
        
        # Create gradient based on hash
        r1 = (prompt_hash >> 16) & 0xFF
        g1 = (prompt_hash >> 8) & 0xFF
        b1 = prompt_hash & 0xFF
        
        r2 = ((prompt_hash >> 8) + 100) % 256
        g2 = ((prompt_hash + 50) >> 8) & 0xFF
        b2 = ((prompt_hash >> 16) + 150) % 256
        
        # Create gradient
        image = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(image)
        
        for y in range(height):
            ratio = y / height
            r = int(r1 * (1 - ratio) + r2 * ratio)
            g = int(g1 * (1 - ratio) + g2 * ratio)
            b = int(b1 * (1 - ratio) + b2 * ratio)
            draw.rectangle([(0, y), (width, y + 1)], fill=(r, g, b))
        
        return image
    
    def _add_text_overlay(self, image: Image.Image, prompt: str, width: int, height: int):
        """Add text overlay with prompt summary"""
        draw = ImageDraw.Draw(image)
        
        # Try to use a system font, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        # Create text summary
        text = "MOCK IMAGE"
        subtext = prompt[:30] + "..." if len(prompt) > 30 else prompt
        
        # Calculate text position (center)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) // 2
        y = height // 2 - 50
        
        # Add main text
        draw.text((x, y), text, fill="white", font=font)
        
        # Add subtext
        subtext_bbox = draw.textbbox((0, 0), subtext, font=font)
        subtext_width = subtext_bbox[2] - subtext_bbox[0]
        subtext_x = (width - subtext_width) // 2
        draw.text((subtext_x, y + 40), subtext, fill="lightgray", font=font)
    
    def _generate_filename(self, prompt: str) -> str:
        """Generate unique filename based on prompt"""
        safe_prompt = "".join(c for c in prompt if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_prompt = safe_prompt[:20] if len(safe_prompt) > 20 else safe_prompt
        safe_prompt = safe_prompt.replace(' ', '_')
        
        timestamp = int(time.time())
        return f"mock_{safe_prompt}_{timestamp}.png"
