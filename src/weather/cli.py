from __future__ import annotations

import argparse
import sys

from . import __version__
from .services import ServiceError, WeatherService


TEXT = {
    "zh-TW": {
        "usage": "取得即時天氣（未輸入地名時依公開 IP 推測城市）",
        "estimated": "依 IP 推測",
        "location": "地點", "observed": "觀測時間", "condition": "天氣狀況",
        "daynight": "日／夜", "temperature": "氣溫", "apparent": "體感溫度",
        "humidity": "相對濕度", "precipitation": "降水量", "wind": "風速", "cloud": "雲量",
        "day": "白天", "night": "夜晚", "error": "錯誤",
    },
    "en": {
        "usage": "Get current weather (without a location, estimate city from public IP)",
        "estimated": "Estimated from IP",
        "location": "Location", "observed": "Observed", "condition": "Conditions",
        "daynight": "Day/Night", "temperature": "Temperature", "apparent": "Feels like",
        "humidity": "Relative humidity", "precipitation": "Precipitation", "wind": "Wind speed", "cloud": "Cloud cover",
        "day": "Day", "night": "Night", "error": "Error",
    },
}


def configure_utf8() -> None:
    """Avoid mojibake in legacy Windows console configurations."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=TEXT["zh-TW"]["usage"])
    p.add_argument("location", nargs="*", metavar="LOCATION")
    p.add_argument("--lang", choices=("zh-TW", "en"), default="zh-TW")
    p.add_argument("--version", action="version", version=f"weather {__version__}")
    return p


def render(place: dict, current: dict, lang: str, estimated: bool) -> str:
    t = TEXT[lang]
    unit = current["units"]
    prefix = f"[{t['estimated']}] " if estimated else ""
    place_name = place["name"] if lang == "en" else place.get("name_zh", place["name"])
    lines = [
        f"{t['location']}: {prefix}{place_name}, {place['country']}",
        f"{t['observed']}: {current['time']}",
        f"{t['condition']}: {current['condition'][lang]}",
        f"{t['daynight']}: {t['day'] if current['is_day'] else t['night']}",
        f"{t['temperature']}: {current['temperature']} {unit['temperature']}",
        f"{t['apparent']}: {current['apparent_temperature']} {unit['temperature']}",
        f"{t['humidity']}: {current['humidity']} {unit['humidity']}",
        f"{t['precipitation']}: {current['precipitation']} {unit['precipitation']}",
        f"{t['wind']}: {current['wind_speed']} {unit['wind_speed']}",
        f"{t['cloud']}: {current['cloud_cover']} {unit['cloud_cover']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    configure_utf8()
    args = parser().parse_args(argv)
    lang = args.lang
    query = " ".join(args.location).strip()
    try:
        service = WeatherService()
        estimated = not bool(query)
        place = service.locate_by_ip(lang) if estimated else service.geocode(query, lang)
        current = service.current_weather(place["latitude"], place["longitude"])
        print(render(place, current, lang, estimated))
        return 0
    except ServiceError as exc:
        print(f"{TEXT[lang]['error']}: {exc.message(lang)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
