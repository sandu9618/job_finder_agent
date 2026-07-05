import unittest
from job_finder_agent.core.pii_redaction import redact_pii

class TestPIIRedaction(unittest.TestCase):
    def test_legitimate_email(self):
        text = "contact jane@company.com to apply"
        sanitized, categories = redact_pii(text)
        self.assertEqual(sanitized, "contact [[EMAIL]] to apply")
        self.assertIn("email", categories)

    def test_phone_number(self):
        text = "Call us at 555-123-4567"
        sanitized, categories = redact_pii(text)
        self.assertEqual(sanitized, "Call us at [[PHONE]]")
        self.assertIn("phone", categories)

    def test_address(self):
        text = "Our office is at 123 Main Street"
        sanitized, categories = redact_pii(text)
        self.assertEqual(sanitized, "Our office is at [[ADDRESS]]")
        self.assertIn("address", categories)

    def test_ssn(self):
        text = "Your SSN 123-45-6789 is required"
        sanitized, categories = redact_pii(text)
        self.assertEqual(sanitized, "Your SSN [[SSN]] is required")
        self.assertIn("ssn", categories)

    def test_card_number(self):
        text = "Pay with 1234-5678-9012-3456"
        sanitized, categories = redact_pii(text)
        self.assertEqual(sanitized, "Pay with [[CARD_NUMBER]]")
        self.assertIn("card_number", categories)

    def test_multiple_pii(self):
        text = "Email jane@company.com or call 555-123-4567."
        sanitized, categories = redact_pii(text)
        self.assertIn("[[EMAIL]]", sanitized)
        self.assertIn("[[PHONE]]", sanitized)
        self.assertIn("email", categories)
        self.assertIn("phone", categories)
        
    def test_no_pii(self):
        text = "We are looking for a software engineer."
        sanitized, categories = redact_pii(text)
        self.assertEqual(sanitized, text)
        self.assertEqual(len(categories), 0)

if __name__ == '__main__':
    unittest.main()
