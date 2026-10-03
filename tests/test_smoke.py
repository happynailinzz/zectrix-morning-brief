import os
import tempfile
import unittest
from datetime import date

from PIL import Image

from scripts.morning_brief import render, sample_data


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


if __name__ == "__main__":
    unittest.main()
