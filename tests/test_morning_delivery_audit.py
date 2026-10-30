import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.audit_morning_delivery import audit


class MorningDeliveryAuditTests(unittest.TestCase):
    def check(self, sent, generated):
        return audit(
            {"last_sent_at_kst": sent},
            {"generated_at_kst": generated},
        )

    def test_on_time_both(self):
        result = self.check("2026-10-30T07:29:59+09:00", "2026-10-30T07:20:00+09:00")
        self.assertTrue(result["push_on_time"])
        self.assertTrue(result["briefing_on_time"])
        self.assertEqual(result["push_delay_seconds"], -1)
        self.assertFalse(result["device_receipt_verified"])

    def test_late_push_and_briefing(self):
        result = self.check("2026-10-30T07:51:49+09:00", "2026-10-30T08:58:45+09:00")
        self.assertFalse(result["push_on_time"])
        self.assertEqual(result["push_delay_seconds"], 1309)
        self.assertFalse(result["briefing_on_time"])
        self.assertEqual(result["briefing_delay_seconds"], 5325)

    def test_briefing_from_other_day_is_unknown(self):
        result = self.check("2026-10-30T07:35:00+09:00", "2026-10-29T07:00:00+09:00")
        self.assertFalse(result["briefing_generated_same_day"])
        self.assertIsNone(result["briefing_delay_seconds"])
        self.assertIsNone(result["briefing_on_time"])


    def test_exact_deadline_is_on_time(self):
        result = self.check("2026-10-30T07:30:00+09:00", "2026-10-30T07:30:00+09:00")
        self.assertTrue(result["push_on_time"])
        self.assertTrue(result["briefing_on_time"])
        self.assertEqual(result["push_delay_seconds"], 0)

    def test_utc_timestamps_are_converted_to_kst(self):
        result = self.check("2026-10-29T22:31:00+00:00", "2026-10-29T22:29:00+00:00")
        self.assertEqual(result["date_kst"], "2026-10-30")
        self.assertEqual(result["push_delay_seconds"], 60)
        self.assertFalse(result["push_on_time"])
        self.assertTrue(result["briefing_on_time"])


if __name__ == "__main__":
    unittest.main()
