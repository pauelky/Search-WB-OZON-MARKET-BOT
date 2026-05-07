from __future__ import annotations

import unittest

from price_bot.providers import _yandex_market_price


class ProviderParsingTest(unittest.TestCase):
    def test_yandex_market_price_ignores_duty(self) -> None:
        text = (
            "Смартфон Apple iPhone 15 128 ГБ "
            "Цена с картой Яндекс Пэй 47796 ₽ вместо 47 796 ₽ "
            "Пошлина 5 655"
        )
        self.assertEqual(_yandex_market_price(text), 47796)


if __name__ == "__main__":
    unittest.main()
