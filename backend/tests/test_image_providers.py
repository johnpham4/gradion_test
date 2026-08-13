"""
Test image provider integrations (Mock only for assessment)
"""

import pytest
import os
from app.clients.mock_image import MockImageClient
from app.config import settings


class TestMockImageClient:
    """Test MockImageClient functionality"""
    
    def test_init(self):
        """Test client initialization"""
        client = MockImageClient(output_dir="test_mock_images")
        assert client.output_dir == "test_mock_images"
        assert os.path.exists(client.output_dir)
    
    def test_generate_image(self):
        """Test mock image generation"""
        client = MockImageClient(output_dir="test_mock_images")
        
        prompt = "A beautiful sunset over mountains"
        image_path, interaction_id = client.generate_image(
            prompt=prompt,
            aspect_ratio="9:16"
        )
        
        assert os.path.exists(image_path)
        assert interaction_id.startswith("mock_interaction_")
        assert "mock" in image_path
        
        # Clean up
        if os.path.exists(image_path):
            os.remove(image_path)
    
    def test_aspect_ratios(self):
        """Test different aspect ratios"""
        client = MockImageClient(output_dir="test_mock_images")
        
        ratios = ["9:16", "1:1", "16:9", "3:4", "4:3"]
        
        for ratio in ratios:
            image_path, _ = client.generate_image(
                prompt="Test image",
                aspect_ratio=ratio
            )
            assert os.path.exists(image_path)
            os.remove(image_path)
    
    def test_cleanup(self):
        """Test cleanup of test directory"""
        import shutil
        if os.path.exists("test_mock_images"):
            shutil.rmtree("test_mock_images")


class TestImageProviderIntegration:
    """Test image provider integration with pipeline"""
    
    def test_config_defaults(self):
        """Test that config has proper defaults"""
        assert hasattr(settings, 'IMAGE_PROVIDER')
        assert hasattr(settings, 'MOCK_IMAGE_OUTPUT_DIR')
    
    def test_provider_selection(self):
        """Test that provider can be selected via environment"""
        # This tests the configuration logic
        provider = settings.IMAGE_PROVIDER
        assert provider in ["mock", "gemini"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
