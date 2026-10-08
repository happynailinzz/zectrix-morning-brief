#!/usr/bin/env python3
"""Fetch daily data, render a 400x300 NOTE4 page, and optionally upload it."""

import argparse
import datetime as dt
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from PIL import Image, ImageDraw, ImageFont
import cairosvg


CONFIG_DIR = os.environ.get(
    "ZECTRIX_MORNING_CONFIG_DIR",
    os.path.expanduser("~/.config/zectrix-morning-brief"),
)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
BASE = "https://cloud.zectrix.com/open/v1"
QMRL = "https://www.qmrl888.com/{year}-{month}-{day}.html"
HOLIDAY = "https://timor.tech/api/holiday/info/{date}"
W, H = 400, 300
ONE_BPP_THRESHOLD = 128

WEATHER = {
    0: "晴", 1: "晴", 2: "多云", 3: "阴", 45: "雾", 48: "雾",
    51: "小雨", 53: "小雨", 55: "中雨", 56: "冻雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒", 80: "阵雨",
    81: "阵雨", 82: "强阵雨", 85: "阵雪", 86: "阵雪", 95: "雷雨",
    96: "雷雨", 99: "雷雨",
}
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
SNOW_CODES = {71, 73, 75, 77, 85, 86}
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
FONT_CANDIDATES = [
    os.environ.get("ZECTRIX_FONT", ""),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts", "Zfull.ttf"),
    os.path.expanduser("~/Library/Fonts/Zfull.ttf"),
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "qweather-icons")


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        value = html.unescape(data).strip()
        if value:
            self.parts.append(value)

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            alt = dict(attrs).get("alt", "").strip()
            if alt:
                self.parts.append(alt)


def fetch_json(url, timeout=20):
    request = urllib.request.Request(url, headers={"User-Agent": "zectrix-morning-brief/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "zectrix-morning-brief/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8", "ignore")
    parser = TextParser()
    parser.feed(raw)
    return "\n".join(parser.parts)


def safe_fetch(source, function, default, attempts=2):
    for attempt in range(1, attempts + 1):
        try:
            return function()
        except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
            if attempt == attempts:
                print("WARN: 数据源失败 [%s]（已重试%d次）：%s" % (source, attempts - 1, error), file=sys.stderr)
            else:
                print("WARN: 数据源暂时失败 [%s]，%d秒后重试：%s" % (source, 2, error), file=sys.stderr)
                time.sleep(2)
    return default


def load_config(allow_sample=False):
    if not os.path.exists(CONFIG_FILE):
        if allow_sample:
            return {
                "api_key": "",
                "device_id": "",
                "page": "1",
                "location": {
                    "label": "郑州",
                    "lat": 34.7466,
                    "lon": 113.6254,
                    "timezone": "Asia/Shanghai",
                },
            }
        raise RuntimeError("未找到配置，请先运行 scripts/init.py")
    with open(CONFIG_FILE, encoding="utf-8") as handle:
        return json.load(handle)


def fetch_weather(config, date, tomorrow=False):
    location = config["location"]
    params = {
        "latitude": location["lat"],
        "longitude": location["lon"],
        "timezone": location.get("timezone", "Asia/Shanghai"),
        "forecast_days": 2 if tomorrow else 1,
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max,sunrise,sunset",
        "hourly": "temperature_2m",
    }
    if not tomorrow:
        params["current"] = "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m,is_day"
    data = fetch_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params))
    current = data.get("current", {})
    daily = data.get("daily", {})
    hourly = data.get("hourly", {})
    index = 1 if tomorrow else 0
    code = int((daily.get("weather_code") or [0])[index])
    if not tomorrow:
        code = int(current.get("weather_code", code))
    hourly = hourly.get("temperature_2m") or []
    hourly_values = hourly[index * 24:(index + 1) * 24]
    high = round(float((daily.get("temperature_2m_max") or [0])[index]))
    low = round(float((daily.get("temperature_2m_min") or [0])[index]))
    if tomorrow:
        current = {"temperature_2m": high, "apparent_temperature": high, "relative_humidity_2m": 0, "wind_speed_10m": 0, "wind_direction_10m": 0, "is_day": 1}
    return {
        "condition": WEATHER.get(code, "未知"),
        "code": code,
        "current": round(float(current.get("temperature_2m", 0))),
        "feels": round(float(current.get("apparent_temperature", 0))),
        "humidity": round(float(current.get("relative_humidity_2m", 0))),
        "high": high,
        "low": low,
        "rain_probability": int((daily.get("precipitation_probability_max") or [0])[index] or 0),
        "wind_speed": round(float(current.get("wind_speed_10m", 0))),
        "wind_direction": int(current.get("wind_direction_10m", 0) or 0),
        "is_day": bool(current.get("is_day", 1)),
        "sunrise": (daily.get("sunrise") or [""])[index].split("T")[-1][:5],
        "sunset": (daily.get("sunset") or [""])[index].split("T")[-1][:5],
        "hourly_temperatures": [round(float(value)) for value in hourly_values],
        "date": (daily.get("time") or [date.isoformat()])[index],
        "forecast": tomorrow,
    }


def aqi_level(aqi):
    """Return AQI label in Chinese."""
    if aqi <= 50:
        return "优"
    elif aqi <= 100:
        return "良"
    elif aqi <= 150:
        return "轻度"
    elif aqi <= 200:
        return "中度"
    elif aqi <= 300:
        return "重度"
    else:
        return "严重"


def fetch_air_quality(config):
    location = config["location"]
    params = {
        "latitude": location["lat"],
        "longitude": location["lon"],
        "current": "us_aqi,pm2_5,pm10",
    }
    data = fetch_json("https://air-quality-api.open-meteo.com/v1/air-quality?" + urllib.parse.urlencode(params))
    cur = data.get("current", {})
    aqi = int(round(float(cur.get("us_aqi", 0))))
    pm25 = round(float(cur.get("pm2_5", 0)), 1)
    pm10 = round(float(cur.get("pm10", 0)), 1)
    return {"aqi": aqi, "pm25": pm25, "pm10": pm10, "level": aqi_level(aqi)}


def parse_holiday(date):
    data = fetch_json(HOLIDAY.format(date=date.isoformat()))
    holiday = data.get("holiday") or {}
    if holiday.get("holiday"):
        name = holiday.get("name", "节假日")
        if name == "国庆节" and date.month == 10 and 1 <= date.day <= 7:
            name = "国庆假期第%d天" % date.day
        return {"label": name, "off": True}
    workday = data.get("workday") or {}
    if workday.get("holiday") is False and workday.get("name"):
        return {"label": "工作日（补班）", "off": False}
    return {"label": "工作日" if data.get("code") == 0 else "日期信息未知", "off": False}


def between(text, start, end=None):
    begin = text.find(start)
    if begin < 0:
        return ""
    begin += len(start)
    finish = text.find(end, begin) if end else len(text)
    return text[begin:finish if finish >= 0 else len(text)]


ZODIAC_CHARS = "鼠牛虎兔龙蛇马羊猴鸡狗猪"


def compact_lunar(raw):
    """Keep the full lunar 年月日 but drop the zodiac token (e.g. 马年) and the
    trailing solar-term annotation (e.g. （寒露）) that the source appends."""
    value = re.sub(r"（[^（）]*节气[^（）]*）|（\s*[^（）]*\s*）\s*$", " ", str(raw or ""))
    tokens = [token for token in value.split()
              if not (len(token) == 2 and token.endswith("年") and token[0] in ZODIAC_CHARS)]
    return " ".join(tokens).strip()


def first_match(pattern, text, default=""):
    match = re.search(pattern, text, re.S)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else default


def parse_qmrl(date):
    text = fetch_text(QMRL.format(year=date.year, month=date.month, day=date.day))
    lunar = compact_lunar(first_match(r"农历\s+([^\n]+)", text, "数据暂不可用"))
    ganzhi = first_match(r"(\S+年（[^\n]+?\）\S+月（[^\n]+?\）\S+日（[^\n]+?\）)", text, "")
    day_pillar = first_match(r"([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])日", text, "")
    wuxing = first_match(r"五行：(.+?)(?:建执位|\n)", text, "")
    value_god = first_match(r"今日值神是([^，。\n]+)", text, "")
    build_day = first_match(r"黄道吉日是[“\"]?([^”\"，。]+)", text, "")
    yi_block = between(text, "\n宜\n", "\n胎神")
    ji_block = between(text, "\n忌\n", "\n五行")
    yi = split_items(yi_block, limit=12)
    ji = split_items(ji_block, limit=12)
    colors = parse_colors(text)
    event = first_match(r"公历\s+[^\n]+\n\n?[^\n]*（[^）]+）", text, "")
    previous_term, next_term = solar_term_pair(text, date)
    if previous_term == "无" and next_term == "无":
        next_term = event or "无"
    return {
        "lunar": lunar,
        "ganzhi": ganzhi,
        "day_pillar": day_pillar,
        "wuxing": wuxing,
        "value_god": value_god,
        "build_day": build_day,
        "yi": yi,
        "ji": ji,
        "colors": colors,
        "term": next_term,
        "previous_term": previous_term,
        "next_term": next_term,
    }


def solar_term_pair(text, date):
    """Return the most recent and next solar terms around date."""
    terms = {"立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏", "小满", "芒种", "夏至", "小暑", "大暑", "立秋", "处暑", "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至", "小寒", "大寒"}
    candidates = []
    for month, day, name in re.findall(r"(\d{1,2})月\s*(\d{1,2})日\s*([^\d\s]+)", text):
        name = name.strip()
        if name not in terms:
            continue
        try:
            event_date = dt.date(date.year, int(month), int(day))
        except ValueError:
            continue
        candidates.append((event_date, name))
    candidates = sorted(set(candidates))
    previous = [(event_date, name) for event_date, name in candidates if event_date <= date]
    upcoming = [(event_date, name) for event_date, name in candidates if event_date > date]
    previous_text = "%s %d月%d日" % (previous[-1][1], previous[-1][0].month, previous[-1][0].day) if previous else "无"
    next_text = "%s %d月%d日" % (upcoming[0][1], upcoming[0][0].month, upcoming[0][0].day) if upcoming else "无"
    return previous_text, next_text


def next_solar_term(text, date):
    """Return the next solar term as a compact name and date."""
    month_text = between(text, "%d年%d所有节日节气" % (date.year, date.month), "小运播报")
    candidates = []
    terms = {"寒露", "霜降", "立冬", "小雪", "大雪", "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏", "小满", "芒种", "夏至", "小暑", "大暑", "立秋", "处暑", "白露", "秋分"}
    for month, day, name in re.findall(r"(\d{1,2})月(\d{1,2})日\s*([^\d\s]+)", month_text):
        if name in terms:
            event_date = dt.date(date.year, int(month), int(day))
            candidates.append((event_date, name))
    upcoming = sorted(item for item in candidates if item[0] > date)
    if upcoming:
        return "%s %d月%d日" % (upcoming[0][1], upcoming[0][0].month, upcoming[0][0].day)
    return "无"


def split_items(block, limit=6):
    items = []
    for line in block.splitlines():
        line = re.sub(r"^[\-•·\s]+", "", line).strip()
        if line and len(line) <= 24 and line not in items:
            items.append(line)
    return items[:limit]


def parse_colors(text):
    section = between(text, "五行穿衣颜色", "是什么建日")
    result = {}
    labels = [("贵人色", "大吉"), ("合作色", "次吉"), ("进财色", "一般"), ("消耗色", "较差"), ("不利色", "不宜")]
    for index, (key, marker) in enumerate(labels):
        end_marker = labels[index + 1][1] if index + 1 < len(labels) else None
        segment = between(section, marker, end_marker)
        values = re.findall(r"(?:黑色|深蓝色|深灰色|白色|银白色|银色|浅灰色|金色|红色|紫色|玫红色|粉红色|粉色|黄色|焦糖色|咖啡色|绿色|蓝色|青色|泥土色)", segment)
        result[key] = list(dict.fromkeys(values))
    return result


def sample_data(config, date):
    return {
        "weather": {"condition": "多云转阴", "code": 3, "current": 20, "feels": 18, "humidity": 30, "high": 22, "low": 14, "rain_probability": 10, "wind_speed": 3, "wind_direction": 45, "sunrise": "06:18", "sunset": "18:08", "is_day": True, "hourly_temperatures": [15, 15, 14, 14, 15, 17, 19, 20, 21, 22, 22, 21, 20, 19, 18, 17, 16, 16, 15, 15, 14, 14, 14, 14], "aqi": 75, "pm25": 18.2, "pm10": 35.6, "level": "良"},
        "holiday": {"label": "国庆假期第2天", "off": True},
        "calendar": {
            "lunar": "二〇二六年八月廿二", "ganzhi": "丙午年 丁酉月 己酉日", "day_pillar": "己酉",
            "wuxing": "大驿土", "value_god": "玉堂", "build_day": "建日", "term": "寒露 10月8日",
            "previous_term": "秋分 9月23日", "next_term": "寒露 10月8日",
            "yi": ["祭祀", "出行"], "ji": ["嫁娶", "入宅", "动土", "会亲友", "破土"],
            "colors": {"贵人色": ["黑色", "深蓝", "深灰"], "合作色": ["白色", "银色", "金色", "浅灰"], "进财色": ["红色", "粉色"], "消耗色": ["黄色", "咖啡色", "泥土色"], "不利色": ["绿色", "青色"]},
        },
    }


def font(size):
    path = next((candidate for candidate in FONT_CANDIDATES if candidate and os.path.exists(candidate)), None)
    # Keep text solid and predictable on the 400x300 monochrome canvas.
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def fit(text, max_chars):
    text = str(text or "").replace("\n", " ")
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def fit_width(text, font_obj, max_width):
    """Trim text by rendered pixels so CJK strings stay inside a card."""
    text = str(text or "").replace("\n", " ")
    if ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=font_obj) <= max_width:
        return text
    suffix = "…"
    while text and ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text + suffix, font=font_obj) > max_width:
        text = text[:-1]
    return text + suffix


def weather_icon_file(code, is_day=True):
    """Translate Open-Meteo WMO codes to the equivalent QWeather icon."""
    qweather_codes = {
        0: 100, 1: 100, 2: 101, 3: 104,
        45: 501, 48: 501,
        51: 309, 53: 309, 55: 305, 56: 313, 57: 314,
        61: 305, 63: 306, 65: 310, 66: 313, 67: 314,
        71: 400, 73: 401, 75: 402, 77: 407,
        80: 300, 81: 301, 82: 302,
        85: 406, 86: 406,
        95: 302, 96: 311, 99: 312,
    }
    qweather_code = qweather_codes.get(code, 999)
    if not is_day:
        qweather_code = {
            100: 150, 101: 151, 300: 300, 301: 301,
            400: 400, 401: 401, 406: 406,
        }.get(qweather_code, qweather_code)
    return os.path.join(ICON_DIR, "%d.svg" % qweather_code)


def draw_weather_icon(image, cx, cy, code, is_day=True):
    """Rasterize the supplied QWeather SVG for the native PNG output."""
    path = weather_icon_file(code, is_day)
    icon_size = 66
    try:
        with open(path, "rb") as handle:
            png = cairosvg.svg2png(bytestring=handle.read(), output_width=icon_size, output_height=icon_size)
        icon = Image.open(io.BytesIO(png)).convert("RGBA")
        alpha = icon.getchannel("A")
        monochrome = Image.new("L", icon.size, 0)
        monochrome.paste(35, mask=alpha)
        image.paste(monochrome, (cx - icon_size // 2, cy - icon_size // 2), alpha)
    except (OSError, ValueError):
        # Keep rendering usable if an optional asset is missing.
        draw = ImageDraw.Draw(image)
        radius = icon_size // 2 - 3
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=35, width=2)


def wind_level(speed):
    """Convert km/h to the 0-12 Beaufort wind-force scale."""
    thresholds = (1, 5, 11, 19, 28, 38, 49, 61, 74, 88, 102, 117)
    speed = max(0.0, float(speed or 0))
    return next((level for level, threshold in enumerate(thresholds) if speed <= threshold), 12)


def draw_temperature_chart(draw, x, y, width, height, weather, small_font):
    values = weather.get("hourly_temperatures") or [weather.get("low", 0), weather.get("current", 0), weather.get("high", 0)]
    values = values[:24]
    low = min(values + [weather.get("low", 0)])
    high = max(values + [weather.get("high", 0)])
    span = max(1, high - low)
    draw.text((x, y - 12), "明日温度" if weather.get("forecast") else "今日温度", font=small_font, fill=0)
    # Use the full left side for the plot; the axis carries no temperature labels.
    axis_x = x + 2
    plot_right = x + width - 8
    plot_top, plot_bottom = y + 1, y + height - 8
    plot_height = plot_bottom - plot_top
    for tick_value in (low, low + span / 2, high):
        tick_y = plot_bottom - round((tick_value - low) / span * plot_height)
        draw.line((axis_x, tick_y, plot_right, tick_y), fill=0, width=1)
    for index, value in enumerate(values):
        bx = axis_x + 1 + index * max(1, (plot_right - axis_x - 1) // len(values))
        bar_width = max(2, (plot_right - axis_x - 1) // len(values) - 1)
        bar_top = plot_bottom - round((value - low) / span * plot_height)
        draw.rectangle((bx, bar_top, bx + bar_width, plot_bottom), fill=0)
    draw.line((axis_x, plot_top, axis_x, plot_bottom), fill=90, width=1)
    draw.line((axis_x, plot_bottom, plot_right, plot_bottom), fill=90, width=1)
    hour_y = plot_bottom + 1
    for hour, position in (("00", 0), ("06", 6), ("12", 12), ("18", 18), ("24", 24)):
        tick_x = axis_x + round((plot_right - axis_x) * position / 24)
        draw.line((tick_x, plot_bottom, tick_x, plot_bottom + 2), fill=90, width=1)
        draw.text((tick_x, hour_y), hour, font=small_font, fill=0, anchor="ma")
    draw.text(
        ((axis_x + plot_right) // 2, plot_bottom + 11),
        "日出 %s  日落 %s" % (weather.get("sunrise", "--:--"), weather.get("sunset", "--:--")),
        font=small_font,
        fill=0,
        anchor="ma",
    )


def draw_wrapped(draw, text, xy, font_obj, fill, max_chars, line_gap=13, max_lines=2):
    text = str(text or "")
    lines = [text[index:index + max_chars] for index in range(0, len(text), max_chars)] or [""]
    for index, line in enumerate(lines[:max_lines]):
        draw.text((xy[0], xy[1] + index * line_gap), line, font=font_obj, fill=fill)


def wrap_by_width(draw, text, font_obj, max_width, max_lines):
    lines = []
    line = ""
    for char in str(text or ""):
        if line and draw.textlength(line + char, font=font_obj) > max_width:
            lines.append(line)
            line = char
            if len(lines) == max_lines:
                return lines
        else:
            line += char
    if line and len(lines) < max_lines:
        lines.append(line)
    return lines


def render(config, date, data, output):
    image = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(image)
    black, white = 0, 255
    f_title, f_body, f_small, f_tiny = font(17), font(13), font(12), font(11)
    label = config["location"].get("label", "")
    weather = data["weather"]
    calendar = data["calendar"]
    holiday = data["holiday"]

    draw.text((10, 5), label or "郑州", font=f_title, fill=black)
    draw.text((390, 7), "%d年%d月%d日 %s" % (date.year, date.month, date.day, WEEKDAYS[date.weekday()]), font=f_small, fill=black, anchor="ra")
    draw.line((10, 27, 390, 27), fill=black, width=2)
    draw.line((200, 34, 200, 292), fill=black, width=1)

    # Left column: glanceable weather and clothing information.
    draw.rounded_rectangle((10, 32, 190, 225), radius=4, fill=white, outline=0, width=1)
    draw.text((12, 35), "明日天气" if weather.get("forecast") else "当前天气", font=f_body, fill=black)
    draw_weather_icon(image, 148, 68, weather.get("code", 0), weather.get("is_day", True))
    draw.text((12, 58), "%d℃" % weather["current"], font=font(34), fill=black)
    condition = str(weather.get("condition", ""))
    range_prefix = "%d~%d℃  " % (weather["low"], weather["high"])
    # Keep the three left-side metric rows aligned and clear of the card border.
    content_x = 16
    draw.text((content_x, 94), range_prefix + condition, font=f_small, fill=black)
    metric_font = f_tiny
    metric_x = 104
    if weather.get("forecast"):
        draw.text((content_x, 112), "次日预报", font=metric_font, fill=black)
        draw.text((metric_x, 112), "降水 %d%%" % weather.get("rain_probability", 0), font=metric_font, fill=black)
    else:
        draw.text((content_x, 112), "AQI %d" % weather.get("aqi", 0), font=metric_font, fill=black)
        draw.text((metric_x, 112), "湿度 %d%%" % weather.get("humidity", 0), font=metric_font, fill=black)
    if weather.get("forecast"):
        draw.text((content_x, 130), "%d~%d℃" % (weather["low"], weather["high"]), font=metric_font, fill=black)
    else:
        draw.text((content_x, 130), "降水 %d%%" % weather.get("rain_probability", 0), font=metric_font, fill=black)
        draw.text((metric_x, 130), "风力 %d级" % wind_level(weather.get("wind_speed", 0)), font=metric_font, fill=black)
    # Leave a clear gap below the metrics; the chart title used to overlap the wind row.
    draw_temperature_chart(draw, 16, 157, 168, 48, weather, f_tiny)
    draw.rounded_rectangle((10, 230, 190, 292), radius=4, fill=white, outline=0, width=1)
    draw.text((16, 234), "明日穿搭" if weather.get("forecast") else "穿搭推荐", font=f_body, fill=black)
    clothing = "早晚温差较大，建议长袖/薄卫衣搭配薄外套"
    if weather["low"] <= 8:
        clothing = "气温偏低，建议保暖外套，早晚注意防风"
    elif weather["high"] >= 28:
        clothing = "天气偏暖，建议轻薄衣物，外出注意防晒"
    if weather["code"] in RAIN_CODES:
        clothing = "有降水可能，建议带伞并穿防水鞋"
    for index, line in enumerate(wrap_by_width(draw, clothing, f_tiny, 154, 2)):
        draw.text((16, 255 + index * 12), line, font=f_tiny, fill=black)

    # Right column: calendar, five-element colors, and yi/ji.
    rx = 211
    draw.rounded_rectangle((208, 32, 390, 292), radius=4, fill=white, outline=0, width=1)
    draw.text((rx, 35), "明日黄历" if weather.get("forecast") else "今日黄历", font=f_body, fill=black)
    draw.text((388, 37), fit_width(holiday.get("label", "日期信息未知"), f_tiny, 90), font=f_tiny, fill=black, anchor="ra")
    draw.text((rx, 55), fit_width("农历 " + calendar.get("lunar", "数据暂不可用"), f_tiny, 169), font=f_tiny, fill=black)
    draw.text((rx, 70), fit_width("上节气 " + calendar.get("previous_term", "无"), f_tiny, 169), font=f_tiny, fill=black)
    draw.text((rx, 85), fit_width("下节气 " + calendar.get("next_term", "无"), f_tiny, 169), font=f_tiny, fill=black)
    draw.text((rx, 100), fit_width("日柱 %s  %s" % (calendar.get("day_pillar", "—"), calendar.get("value_god", "")), f_tiny, 169), font=f_tiny, fill=black)
    draw.text((rx, 115), fit_width("五行 %s  %s" % (calendar.get("wuxing", "—"), calendar.get("build_day", "")), f_tiny, 169), font=f_tiny, fill=black)
    draw.line((rx, 131, 388, 131), fill=black, width=1)
    draw.text((rx, 136), "五行穿衣", font=f_body, fill=black)
    color_rows = [("贵", "贵人色"), ("合", "合作色"), ("财", "进财色"), ("耗", "消耗色"), ("忌", "不利色")]
    for index, (prefix, key) in enumerate(color_rows):
        y = 154 + index * 11
        values = "、".join(calendar.get("colors", {}).get(key, [])) or "数据暂不可用"
        shade = (65, 120, 170, 205, 235)[index]
        draw.rounded_rectangle((rx, y - 1, rx + 12, y + 9), radius=2, fill=shade, outline=80, width=1)
        draw.text((rx + 5, y - 1), prefix, font=f_tiny, fill=255 if index < 2 else black, anchor="ma")
        draw.text((rx + 18, y), fit_width(values, f_tiny, 151), font=f_tiny, fill=black)
    draw.line((rx, 212, 388, 212), fill=black, width=1)

    yi = "、".join(calendar.get("yi", [])) or "数据暂不可用"
    ji = "、".join(calendar.get("ji", [])) or "数据暂不可用"
    draw.text((rx, 216), "宜", font=f_body, fill=black)
    yi_lines = wrap_by_width(draw, yi, f_tiny, 151, 3)
    for index, line in enumerate(yi_lines):
        draw.text((rx + 22, 227 + index * 10), line, font=f_tiny, fill=black)
    draw.text((rx, 260), "忌", font=f_body, fill=black)
    ji_lines = wrap_by_width(draw, ji, f_tiny, 151, 2)
    for index, line in enumerate(ji_lines):
        draw.text((rx + 22, 271 + index * 10), line, font=f_tiny, fill=black)
    # NOTE4 is a 1BPP panel. Quantize once here so the cloud does not dither
    # already-antialiased text a second time and soften its strokes.
    one_bpp = image.point(lambda value: 0 if value < ONE_BPP_THRESHOLD else 255, mode="1")
    one_bpp.convert("RGB").save(output)


def push(config, output):
    with open(output, "rb") as handle:
        payload = handle.read()
    boundary = "----ZectrixMorningBrief" + os.urandom(8).hex()
    parts = []
    for key, value in (("pageId", str(config.get("page", "1"))), ("dither", "false")):
        parts.append(("--" + boundary + "\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (key, value)).encode())
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"images\"; filename=\"morning-brief.png\"\r\nContent-Type: image/png\r\n\r\n" % boundary).encode() + payload + b"\r\n")
    body = b"".join(parts) + ("--%s--\r\n" % boundary).encode()
    url = "%s/devices/%s/display/image" % (BASE, urllib.parse.quote(config["device_id"], safe=":"))
    request = urllib.request.Request(url, data=body, method="POST", headers={"X-API-Key": config["api_key"], "Content-Type": "multipart/form-data; boundary=%s" % boundary})
    with urllib.request.urlopen(request, timeout=40) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("code") != 0:
        raise RuntimeError("推送失败：%s" % result)
    print("PUSH pageId=%s OK" % config.get("page", "1"))


def main():
    parser = argparse.ArgumentParser(description="生成 Zectrix 每日晨报")
    parser.add_argument("--output", default="/tmp/zectrix-morning-brief.png")
    parser.add_argument("--date", help="固定日期 YYYY-MM-DD，用于调试")
    parser.add_argument("--offline-sample", action="store_true")
    parser.add_argument("--tomorrow", action="store_true", help="显示并抓取次日天气和黄历")
    args = parser.parse_args()
    config = load_config(allow_sample=args.offline_sample)
    date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    target_date = date + dt.timedelta(days=1) if args.tomorrow else date
    if args.offline_sample:
        data = sample_data(config, target_date)
        data["weather"]["forecast"] = args.tomorrow
    else:
        data = {
            "weather": safe_fetch("Open-Meteo天气", lambda: fetch_weather(config, date, tomorrow=args.tomorrow), {"condition": "天气暂不可用", "code": 0, "current": 0, "feels": 0, "humidity": 0, "high": 0, "low": 0, "rain_probability": 0, "wind_speed": 0, "wind_direction": 0}),
            "holiday": safe_fetch("Timor节假日", lambda: parse_holiday(target_date), {"label": "节假日数据暂不可用", "off": False}),
            "calendar": safe_fetch("全民万年历黄历", lambda: parse_qmrl(target_date), {"lunar": "黄历数据暂不可用", "colors": {}, "yi": [], "ji": []}),
        }
    if not args.tomorrow:
        data["air_quality"] = safe_fetch("Open-Meteo空气质量", lambda: fetch_air_quality(config), {"aqi": 0, "pm25": 0, "pm10": 0, "level": "数据暂不可用"})
        data["weather"].update(data["air_quality"])
    render(config, target_date, data, args.output)
    print("saved %s" % args.output)
    if os.environ.get("ZECTRIX_NO_PUSH") != "1" and not args.offline_sample:
        push(config, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR: %s" % error, file=sys.stderr)
        sys.exit(1)
