import unittest
from scripts.audit_push_history import summarize


class PushHistoryAuditTests(unittest.TestCase):
    def test_empty_history_is_unknown(self):
        result = summarize([])
        self.assertEqual(result["observed_days"], 0)
        self.assertIsNone(result["on_time_rate_observed_only"])

    def test_deduplicates_revisions_by_earliest_timestamp(self):
        records = [
            {"last_sent_date_kst": "2026-10-30", "last_sent_at_kst": "2026-10-30T07:51:49+09:00"},
            {"last_sent_date_kst": "2026-10-30", "last_sent_at_kst": "2026-10-30T07:29:59+09:00"},
            {"last_sent_date_kst": "2026-10-29", "last_sent_at_kst": "2026-10-29T07:40:00+09:00"},
        ]
        result = summarize(records)
        self.assertEqual(result["observed_days"], 2)
        self.assertEqual(result["on_time_days"], 1)
        self.assertEqual(result["on_time_rate_observed_only"], 0.5)

    def test_skips_invalid_dates_and_naive_timestamps(self):
        result = summarize([
            {"last_sent_date_kst": "2026-10-30", "last_sent_at_kst": "2026-10-30T07:00:00"},
            {"last_sent_date_kst": "2026-10-29", "last_sent_at_kst": "2026-10-30T07:00:00+09:00"},
            {"last_sent_date_kst": "2026-10-30", "last_sent_at_kst": "invalid"},
        ])
        self.assertEqual(result["observed_days"], 0)


if __name__ == "__main__":
    unittest.main()
