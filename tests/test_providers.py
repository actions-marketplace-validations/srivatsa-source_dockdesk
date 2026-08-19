import unittest
import os
import time
import sys
from unittest.mock import patch, MagicMock

# Mock raw SDKs so lazy imports in __init__ don't fail if they aren't installed
sys.modules['openai'] = MagicMock()
sys.modules['anthropic'] = MagicMock()

from dockdesk.providers import get_provider, OpenAIProvider, AnthropicProvider, OllamaProvider

class TestProviders(unittest.TestCase):
    
    def test_get_provider_dispatch(self):
        self.assertIsInstance(get_provider("ollama"), OllamaProvider)
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
            self.assertIsInstance(get_provider("openai"), OpenAIProvider)
            
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            self.assertIsInstance(get_provider("anthropic"), AnthropicProvider)

    def test_missing_api_keys(self):
        with patch.dict(os.environ, clear=True):
            with self.assertRaises(ValueError) as ctx:
                OpenAIProvider()
            self.assertIn("OPENAI_API_KEY not set", str(ctx.exception))
            
            with self.assertRaises(ValueError) as ctx:
                AnthropicProvider()
            self.assertIn("ANTHROPIC_API_KEY not set", str(ctx.exception))

    @patch("time.sleep", return_value=None) # Don't actually sleep in tests
    def test_retry_with_backoff_transient_failure(self, mock_sleep):
        # We test that it retries on failure and eventually raises after 3 attempts
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
            provider = OpenAIProvider()
            
            mock_client = MagicMock()
            # Configure the mock to fail 3 times
            mock_client.chat.completions.create.side_effect = [
                RuntimeError("Transient 1"),
                RuntimeError("Transient 2"),
                RuntimeError("Transient 3"),
                "Success"
            ]
            
            provider.client = mock_client
            
            # Wrap it by getting the provider
            # And call complete
            
            # Since max_attempts=3, it will fail 3 times and raise the 3rd error
            with self.assertRaises(RuntimeError) as ctx:
                provider.complete("test-model", [{"role": "user", "content": "test prompt"}], 0.1, 100)
            
            self.assertEqual(str(ctx.exception), "Transient 3")
            
            # Should have called create 3 times
            self.assertEqual(mock_client.chat.completions.create.call_count, 3)
            # Should have slept 2 times before the 3rd failure
            self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep", return_value=None)
    def test_retry_with_backoff_success(self, mock_sleep):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            provider = AnthropicProvider()
            
            mock_client = MagicMock()
            # Fails twice, succeeds on the third try
            mock_response = MagicMock()
            mock_content = MagicMock()
            mock_content.text = "Success Payload"
            mock_response.content = [mock_content]
            
            mock_client.messages.create.side_effect = [
                RuntimeError("Transient 1"),
                RuntimeError("Transient 2"),
                mock_response
            ]
            
            provider.client = mock_client
            
            result = provider.complete("test-model", [{"role": "user", "content": "test prompt"}], 0.1, 100)
            
            self.assertEqual(result, "Success Payload")
            self.assertEqual(mock_client.messages.create.call_count, 3)
            self.assertEqual(mock_sleep.call_count, 2)

if __name__ == "__main__":
    unittest.main()
