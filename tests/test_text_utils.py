from __future__ import annotations

import unittest

from price_bot.text_utils import (
    clean_product_title,
    condition_matches,
    duckduckgo_real_url,
    extract_prices_rub,
    has_required_model_phrases,
    has_required_numbers,
    query_from_url_path,
    token_overlap_score,
    wildberries_product_id,
)


class TextUtilsTest(unittest.TestCase):
    def test_extract_prices_rub(self) -> None:
        self.assertEqual(extract_prices_rub("Цена 49 990 ₽, старая цена 59 990 руб."), [49990, 59990])

    def test_clean_product_title(self) -> None:
        self.assertEqual(clean_product_title("Apple iPhone 15 128GB — купить на Ozon"), "Apple iPhone 15 128GB")

    def test_query_from_ozon_url_path(self) -> None:
        url = "https://www.ozon.ru/product/smartfon-apple-iphone-15-128gb-black-123456789/"
        self.assertEqual(query_from_url_path(url), "smartfon apple iphone 15 128gb black")

    def test_query_from_wb_numeric_url_path_is_unknown(self) -> None:
        url = "https://www.wildberries.ru/catalog/123456789/detail.aspx"
        self.assertIsNone(query_from_url_path(url))

    def test_wildberries_product_id(self) -> None:
        url = "https://www.wildberries.ru/catalog/564578829/detail.aspx"
        self.assertEqual(wildberries_product_id(url), "564578829")

    def test_duckduckgo_real_url(self) -> None:
        url = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.ozon.ru%2Fproduct%2Fabc&rut=1"
        self.assertEqual(duckduckgo_real_url(url), "https://www.ozon.ru/product/abc")

    def test_token_overlap_score(self) -> None:
        self.assertGreater(token_overlap_score("iphone 15 128gb", "Apple iPhone 15 128 GB black"), 0.6)

    def test_has_required_numbers(self) -> None:
        self.assertTrue(has_required_numbers("iphone 17 pro max 256gb", "Apple iPhone 17 Pro Max 256 ГБ"))
        self.assertFalse(has_required_numbers("iphone 17 pro max 256gb", "Apple iPhone 15 Pro Max 256 ГБ"))

    def test_has_required_model_phrases(self) -> None:
        self.assertTrue(has_required_model_phrases("iphone 17 pro max", "Apple iPhone 17 Pro Max"))
        self.assertFalse(has_required_model_phrases("iphone 17 pro max", "Apple iPhone 17 Pro без RU-STORE/MAX"))

    def test_condition_matches(self) -> None:
        self.assertFalse(condition_matches("iphone 15 128gb black", "iPhone 15 128 ГБ Восстановленный"))
        self.assertTrue(condition_matches("iphone 15 восстановленный", "iPhone 15 128 ГБ Восстановленный"))


if __name__ == "__main__":
    unittest.main()
