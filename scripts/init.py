#!/usr/bin/env python3
import argparse
import getpass
import json
import os
import sys
import urllib.parse
import urllib.request


CONFIG_DIR = os.environ.get(
    "ZECTRIX_MORNING_CONFIG_DIR",
    os.path.expanduser("~/.config/zectrix-morning-brief"),
)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
BASE = "https://cloud.zectrix.com/open/v1"
GEO = "https://geocoding-api.open-meteo.com/v1/search"


def get_json(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def geocode(place):
    url = GEO + "?" + urllib.parse.urlencode(
        {"name": place, "count": 8, "language": "zh", "format": "json"}
    )
    data = get_json(url)
    results = data.get("results") or []
    if not results:
        raise RuntimeError("没有找到地区：%s" % place)
    result = results[0]
    return {
        "label": result.get("name", place),
        "lat": result["latitude"],
        "lon": result["longitude"],
        "timezone": result.get("timezone", "Asia/Shanghai"),
    }


def verify(key, device):
    data = get_json(BASE + "/devices", {"X-API-Key": key})
    if data.get("code") != 0:
        raise RuntimeError("API Key 无效：%s" % data.get("msg", data))
    devices = data.get("data") or []
    ids = [str(item.get("deviceId", "")).upper() for item in devices]
    if ids and device.upper() not in ids:
        raise RuntimeError("设备不属于该 API Key：%s" % device)
    print("API Key 校验通过，设备数量：%d" % len(ids))


def main():
    parser = argparse.ArgumentParser(description="初始化 Zectrix 晨报配置")
    parser.add_argument("--api-key")
    parser.add_argument("--device")
    parser.add_argument("--place")
    parser.add_argument("--label")
    parser.add_argument("--page", default="1")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()

    key = args.api_key or getpass.getpass("Zectrix API Key（zt_ 开头）：")
    device = args.device or input("设备 ID（MAC）：").strip()
    place = args.place or input("城市（如郑州）：").strip()
    if not key or not device or not place:
        parser.error("API Key、设备 ID、城市都不能为空")
    if not args.no_verify:
        verify(key, device)
    location = geocode(place)
    if args.label:
        location["label"] = args.label
    config = {
        "api_key": key,
        "device_id": device,
        "page": str(args.page),
        "location": location,
    }
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
    os.chmod(CONFIG_FILE, 0o600)
    print("配置已写入：%s" % CONFIG_FILE)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("初始化失败：%s" % error, file=sys.stderr)
        sys.exit(1)
