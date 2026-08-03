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
        self.assertEqual(result["rows"][1]["qty"], 2.0)
        self.assertEqual(result["rows"][2]["uom"], "PC3")
        self.assertEqual(result["rows"][2]["rate"], 7.0)


if __name__ == "__main__":
    unittest.main()
