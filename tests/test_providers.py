from __future__ import annotations

import unittest

from price_bot.providers import (
    _wb_rating,
    _wb_reviews_count,
    _yandex_market_price,
    _yandex_market_rating,
    _yandex_market_reviews_count,
)


class ProviderParsingTest(unittest.TestCase):
    def test_yandex_market_price_ignores_duty(self) -> None:
        text = (
            "Смартфон Apple iPhone 15 128 ГБ "
            "Цена с картой Яндекс Пэй 47796 ₽ вместо 47 796 ₽ "
            "Пошлина 5 655"
        )
        self.assertEqual(_yandex_market_price(text), 47796)

    def test_yandex_market_rating_and_reviews(self) -> None:
        text = "Рейтинг товара: 4.8 из 5 Оценок: (1 234) · 56 купили"
        self.assertEqual(_yandex_market_rating(text), 4.8)
        self.assertEqual(_yandex_market_reviews_count(text), 1234)

    def test_wb_rating_and_reviews(self) -> None:
        item = {"reviewRating": 4.9, "feedbacks": 333}
        self.assertEqual(_wb_rating(item), 4.9)
        self.assertEqual(_wb_reviews_count(item), 333)


if __name__ == "__main__":
    unittest.main()
