import os
import tempfile
import unittest
from datetime import date

from PIL import Image

from scripts.morning_brief import next_solar_term, parse_colors, parse_holiday, render, sample_data


class MorningBriefSmokeTest(unittest.TestCase):
    def test_sample_is_native_grayscale_400x300(self):
        config = {"page": "1", "location": {"label": "郑州"}}
        data = sample_data(config, date(2026, 10, 2))
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "brief.png")
            render(config, date(2026, 10, 2), data, output)
            image = Image.open(output)
            self.assertEqual(image.size, (400, 300))
            self.assertEqual(image.mode, "RGB")
            colors = set(image.get_flattened_data())
            self.assertIn((0, 0, 0), colors)
            self.assertIn((255, 255, 255), colors)
            self.assertEqual(colors, {(0, 0, 0), (255, 255, 255)})

    def test_five_element_color_aliases_are_kept(self):
        text = """五行穿衣颜色
大吉
白色
银色
次吉
黄色
咖啡色
泥土色
一般
绿色
较差
红色
粉红色
不宜
黑色
深蓝色
是什么建日"""
        self.assertEqual(parse_colors(text), {
            "贵人色": ["白色", "银色"],
            "合作色": ["黄色", "咖啡色", "泥土色"],
            "进财色": ["绿色"],
            "消耗色": ["红色", "粉红色"],
            "不利色": ["黑色", "深蓝色"],
        })

    def test_next_solar_term_is_compact(self):
        text = "2026年10所有节日节气\n10月8日\n寒露\n10月23日\n霜降\n小运播报"
        self.assertEqual(next_solar_term(text, date(2026, 10, 4)), "寒露 10月8日")


if __name__ == "__main__":
    unittest.main()
