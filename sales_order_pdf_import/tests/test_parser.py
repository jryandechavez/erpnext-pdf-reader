import unittest

from sales_order_pdf_import.parser import parse_purchase_order


SAMPLE = """Order No. POR10000719
A00001295 Grocery Glutinous Rice 6 KG 145.00 Yes 870.00
Generic (Galapong)
Line Dimensions BU 0001
A00001655 Vegetable Camote White 2 KG 195.00 Yes 390.00
Cubes
Line Dimensions BU 0001
A00001739 Produce Banana Saba 60 PC3 7.00 Yes 420.00
Line Dimensions BU 0001
Total PHP 2,797.50
"""


class TestParser(unittest.TestCase):
    def test_parses_wrapped_descriptions_and_values(self):
        result = parse_purchase_order(SAMPLE)
        self.assertEqual(result["order_no"], "POR10000719")
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(result["rows"][0]["description"], "Grocery Glutinous Rice Generic (Galapong)")
        self.assertNotIn("source_code", result["rows"][0])
        self.assertEqual(result["rows"][1]["qty"], 2.0)
        self.assertEqual(result["rows"][2]["uom"], "PC3")
        self.assertEqual(result["rows"][2]["rate"], 7.0)

    def test_footer_sections_never_become_description(self):
        footers = [
            """Ship-to Address
Central Kitchen
Pasay City
Acknowledgement Certificate No.: AC_125_052026_000635
THIS DOCUMENT IS NOT VALID FOR CLAIM OF INPUT TAX""",
            """Acknowledgement Certificate No.: AC_125_052026_000635
Date Issued: 05/01/2026
THIS DOCUMENT IS NOT VALID FOR CLAIM OF INPUT TAX""",
        ]
        for footer in footers:
            with self.subTest(footer=footer.splitlines()[0]):
                text = (
                    "A00013322 Grocery Boiled Tapioca 2 KG 80.00 Yes 160.00\n"
                    "Violet\n"
                    f"{footer}\n"
                )
                result = parse_purchase_order(text)
                self.assertEqual(len(result["rows"]), 1)
                self.assertEqual(
                    result["rows"][0]["description"],
                    "Grocery Boiled Tapioca Violet",
                )

    def test_repeated_page_footer_does_not_stop_later_pages(self):
        text = """Order No. POR10041892
A00000001 First Item 1 KG 10.00 Yes 10.00
Acknowledgement Certificate No.: AC_125_052026_000635
THIS DOCUMENT IS NOT VALID FOR CLAIM OF INPUT TAX
\fPurchase Order Page 2
A00000002 Second Item 2 KG 20.00 Yes 40.00
Acknowledgement Certificate No.: AC_125_052026_000635
\fPurchase Order Page 3
A00000003 Third Item 3 KG 30.00 Yes 90.00
Total PHP 140.00
Ship-to Address
Pasay City
"""
        result = parse_purchase_order(text)
        self.assertEqual(result["order_no"], "POR10041892")
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(
            [row["description"] for row in result["rows"]],
            ["First Item", "Second Item", "Third Item"],
        )


if __name__ == "__main__":
    unittest.main()
