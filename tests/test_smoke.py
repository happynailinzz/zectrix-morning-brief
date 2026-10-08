import os
import tempfile
import unittest
from datetime import date

from PIL import Image

from scripts.morning_brief import (
    compute_clothing,
    compute_colors,
    nayin_element,
    next_solar_term,
    parse_colors,
    parse_holiday,
    render,
    sample_data,
    wuxing_element,
)


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

    def test_nayin_element_from_day_pillar(self):
        # Spot-check across the element cycle; the day pillar is the source of
        # truth, so these must hold regardless of what the page string shows.
        self.assertEqual(nayin_element("乙卯"), "水")   # 大溪水
        self.assertEqual(nayin_element("丙辰"), "土")   # 沙中土
        self.assertEqual(nayin_element("戊午"), "火")   # 天上火
        self.assertEqual(nayin_element("己未"), "火")   # 天上火
        self.assertEqual(nayin_element("庚申"), "木")  # 石榴木
        self.assertEqual(nayin_element("辛酉"), "木")  # 石榴木
        self.assertEqual(nayin_element("壬戌"), "水")  # 大海水
        self.assertEqual(nayin_element("丁卯"), "火")  # 炉中火
        self.assertEqual(nayin_element("壬申"), "金")  # 剑锋金
        self.assertEqual(nayin_element("甲子"), "金")  # 海中金
        self.assertEqual(nayin_element("癸亥"), "水")  # 大海水
        # Unresolvable pillar yields an empty string, never a guess.
        self.assertEqual(nayin_element(""), "")
        self.assertEqual(nayin_element("Xy"), "")
        self.assertEqual(nayin_element("甲"), "")

    def test_clothing_color_buckets_follow_element_rules(self):
        # 土 day: 贵人=我生(金), 合作=比和(土), 进财=克我(木), 消耗=生我(火), 不利=我克(水).
        self.assertEqual(
            compute_clothing("丙辰", "沙中土"),
            {
                "贵人色": ["白色", "银色"],
                "合作色": ["黄色", "咖啡色"],
                "进财色": ["绿色", "青色"],
                "消耗色": ["红色", "粉色", "橙色"],
                "不利色": ["黑色", "蓝色", "灰色"],
            },
        )
        # 水 day (壬戌 大海水).
        self.assertEqual(
            compute_clothing("壬戌", "大海水"),
            {
                "贵人色": ["绿色", "青色"],
                "合作色": ["黑色", "蓝色", "灰色"],
                "进财色": ["黄色", "咖啡色"],
                "消耗色": ["白色", "银色"],
                "不利色": ["红色", "粉色", "橙色"],
            },
        )
        # 木 day (庚申 石榴木).
        self.assertEqual(
            compute_clothing("庚申", "石榴木"),
            {
                "贵人色": ["红色", "粉色", "橙色"],
                "合作色": ["绿色", "青色"],
                "进财色": ["白色", "银色"],
                "消耗色": ["黑色", "蓝色", "灰色"],
                "不利色": ["黄色", "咖啡色"],
            },
        )

    def test_clothing_prefers_pillar_over_garbled_source(self):
        # A wrong/garbled source string must not override the pillar-derived
        # element: 丙辰 is 土, so even a 火-tinted source string yields 土 buckets.
        result = compute_clothing("丙辰", "天上火", fallback={"贵人色": []})
        self.assertEqual(result["合作色"], ["黄色", "咖啡色"])  # 土 比和


if __name__ == "__main__":
    unittest.main()
