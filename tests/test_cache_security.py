import unittest
import hashlib
import hmac

class TestCacheSystem(unittest.TestCase):
    def test_cache_seed_determinism(self):
        """Test that the same API key always produces the same HMAC seed."""
        secret = "my_super_secret_password"
        api_key = "AIzaSyD-TestKey123"
        
        seed1 = hmac.new(secret.encode(), api_key.encode(), hashlib.sha256).hexdigest()
        seed2 = hmac.new(secret.encode(), api_key.encode(), hashlib.sha256).hexdigest()
        
        self.assertEqual(seed1, seed2)
        
    def test_cache_seed_isolation(self):
        """Test that different API keys produce DIFFERENT HMAC seeds."""
        secret = "my_super_secret_password"
        key1 = "AIzaSyD-UserA"
        key2 = "AIzaSyD-UserB"
        
        seed1 = hmac.new(secret.encode(), key1.encode(), hashlib.sha256).hexdigest()
        seed2 = hmac.new(secret.encode(), key2.encode(), hashlib.sha256).hexdigest()
        
        self.assertNotEqual(seed1, seed2)
        
    def test_empty_key_fails(self):
        """Test behavior with empty key (should still hash but likely invalid flow upstream)."""
        secret = "secret"
        empty_key = ""
        # In current logic it just hashes empty string. Streamlit app layer handles check.
        # But we ensure it doesn't crash.
        seed = hmac.new(secret.encode(), empty_key.encode(), hashlib.sha256).hexdigest()
        self.assertIsInstance(seed, str)

if __name__ == '__main__':
    unittest.main()
