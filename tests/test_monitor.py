from __future__ import annotations

import unittest

from price_bot.monitor import WatchSnapshot, describe_watch_change


class MonitorTest(unittest.TestCase):
    def test_describe_watch_change_tracks_price_rating_and_reviews(self) -> None:
        previous = WatchSnapshot(
            marketplace="Wildberries",
            title="Dyson",
            url="https://example.com/old",
            price_rub=25000,
            rating=4.7,
            reviews_count=10,
        )
        current = WatchSnapshot(
            marketplace="Wildberries",
            title="Dyson",
            url="https://example.com/new",
            price_rub=23000,
            rating=4.8,
            reviews_count=12,
        )
        change = describe_watch_change(previous, current)
        self.assertIsNotNone(change)
        assert change is not None
        self.assertIn("цена снизилась", change)
        self.assertIn("рейтинг 4.7 -> 4.8", change)
        self.assertIn("новых отзывов/оценок: 2", change)


if __name__ == "__main__":
    unittest.main()
