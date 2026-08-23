from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from opencc import OpenCC


OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_WEATHER = "https://api.open-meteo.com/v1/forecast"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
IPAPI = "https://ipapi.co/json/"
USER_AGENT = "personal-weather-cli/0.1.0 (personal, command-line use)"

MESSAGES = {
    "not_found": ("找不到符合的行政區或城市，請嘗試較完整的地名。", "No matching city or administrative area was found. Try a more specific name."),
    "network": ("無法連線至天氣服務，請檢查網路後再試。", "Could not reach the weather service. Check your network and try again."),
    "limited": ("服務暫時限流或忙碌，請稍後再試。", "The service is temporarily rate-limited or busy. Please try again later."),
    "data": ("服務回傳的資料無法使用，請稍後再試。", "The service returned unusable data. Please try again later."),
    "ip": ("無法依 IP 推測城市，請直接輸入地名。", "Could not estimate a city from your IP. Please enter a location."),
}

WEATHER_CODES = {
    0: ("晴朗", "Clear sky"), 1: ("大致晴朗", "Mainly clear"), 2: ("局部多雲", "Partly cloudy"), 3: ("陰天", "Overcast"),
    45: ("有霧", "Fog"), 48: ("霜霧", "Depositing rime fog"), 51: ("毛毛雨（輕）", "Light drizzle"),
    53: ("毛毛雨（中）", "Moderate drizzle"), 55: ("毛毛雨（強）", "Dense drizzle"), 61: ("小雨", "Slight rain"),
    63: ("中雨", "Moderate rain"), 65: ("大雨", "Heavy rain"), 71: ("小雪", "Slight snow"), 73: ("中雪", "Moderate snow"),
    75: ("大雪", "Heavy snow"), 80: ("短暫陣雨（輕）", "Slight rain showers"), 81: ("短暫陣雨（中）", "Moderate rain showers"),
    82: ("短暫陣雨（強）", "Violent rain showers"), 95: ("雷雨", "Thunderstorm"),
}

# Canonical official names make short Taiwanese names unambiguous before global search.
TAIWAN = {
    "台北": ("Taipei City", "臺北市"), "臺北": ("Taipei City", "臺北市"), "新北": ("New Taipei City", "新北市"),
    "桃園": ("Taoyuan City", "桃園市"), "台中": ("Taichung City", "臺中市"), "臺中": ("Taichung City", "臺中市"),
    "台南": ("Tainan City", "臺南市"), "臺南": ("Tainan City", "臺南市"), "高雄": ("Kaohsiung City", "高雄市"),
    "基隆": ("Keelung City", "基隆市"), "新竹市": ("Hsinchu City", "新竹市"), "新竹縣": ("Hsinchu County", "新竹縣"),
    "嘉義市": ("Chiayi City", "嘉義市"), "嘉義縣": ("Chiayi County", "嘉義縣"), "宜蘭": ("Yilan County", "宜蘭縣"),
    "苗栗": ("Miaoli County", "苗栗縣"), "彰化": ("Changhua County", "彰化縣"), "南投": ("Nantou County", "南投縣"),
    "雲林": ("Yunlin County", "雲林縣"), "屏東": ("Pingtung County", "屏東縣"), "台東": ("Taitung County", "臺東縣"),
    "臺東": ("Taitung County", "臺東縣"), "花蓮": ("Hualien County", "花蓮縣"), "澎湖": ("Penghu County", "澎湖縣"),
    "金門": ("Kinmen County", "金門縣"), "馬祖": ("Lienchiang County", "連江縣"), "連江": ("Lienchiang County", "連江縣"),
}

_S2T = OpenCC("s2t")

# Widely used international city and country endonyms.  These take precedence
# over reverse-geocoder neighbourhoods (e.g. Shinjuku for a Tokyo coordinate).
CITY_ZH = {
    "taipei": "臺北", "tokyo": "東京", "seoul": "首爾", "singapore": "新加坡", "new delhi": "新德里", "bangkok": "曼谷",
    "london": "倫敦", "paris": "巴黎", "berlin": "柏林", "rome": "羅馬", "madrid": "馬德里",
    "new york": "紐約", "toronto": "多倫多", "mexico city": "墨西哥城", "são paulo": "聖保羅",
    "sao paulo": "聖保羅", "buenos aires": "布宜諾斯艾利斯", "boston": "波士頓",
}
COUNTRY_ZH = {
    "taiwan": "臺灣", "japan": "日本", "south korea": "南韓", "singapore": "新加坡", "india": "印度",
    "thailand": "泰國", "united kingdom": "英國", "france": "法國", "germany": "德國", "italy": "義大利",
    "spain": "西班牙", "united states": "美國", "canada": "加拿大", "mexico": "墨西哥", "brazil": "巴西",
    "argentina": "阿根廷",
}


def _traditional(value: object) -> str:
    """Convert API Chinese translations to Traditional Chinese safely."""
    return _S2T.convert(str(value))


def _deduplicate_label(value: object) -> str:
    """Nominatim occasionally repeats localized values as `foo;foo`."""
    text = _traditional(value)
    parts = [part.strip() for part in text.split(";") if part.strip()]
    return parts[0] if parts and all(part == parts[0] for part in parts) else text


class ServiceError(Exception):
    def __init__(self, kind: str): self.kind = kind
    def message(self, lang: str) -> str: return MESSAGES[self.kind][0 if lang == "zh-TW" else 1]


def _json(url: str, params: dict[str, object] | None = None) -> object:
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 503): raise ServiceError("limited") from exc
        raise ServiceError("network") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ServiceError("network") from exc


@dataclass
class WeatherService:
    cache: dict[str, dict] = field(default_factory=dict)
    _last_nominatim: float = 0.0

    def _open_meteo_geocode(self, query: str, country: str | None = None, language: str = "en") -> dict | None:
        # Open-Meteo exposes Chinese labels as `zh` (mostly Simplified); OpenCC
        # normalizes them to Traditional Chinese before presentation.
        params: dict[str, object] = {"name": query, "count": 10, "language": language, "format": "json"}
        if country: params["countryCode"] = country
        data = _json(OPEN_METEO_GEO, params)
        if not isinstance(data, dict): raise ServiceError("data")
        for result in data.get("results", []):
            if not isinstance(result, dict): continue
            if country and result.get("country_code") != country: continue
            if all(key in result for key in ("name", "latitude", "longitude", "country")):
                return {"name": _traditional(result["name"]) if language == "zh" else result["name"], "country": _traditional(result["country"]) if language == "zh" else result["country"], "latitude": result["latitude"], "longitude": result["longitude"]}
        return None

    def _nominatim(self, query: str, taiwan_only: bool) -> dict | None:
        cached = self.cache.get(f"nom:{taiwan_only}:{query.casefold()}")
        if cached: return cached
        delay = 1.0 - (time.monotonic() - self._last_nominatim)
        if delay > 0: time.sleep(delay)
        params: dict[str, object] = {"q": query, "format": "jsonv2", "addressdetails": 1, "limit": 5, "accept-language": "zh-TW"}
        if taiwan_only: params["countrycodes"] = "tw"
        self._last_nominatim = time.monotonic()
        data = _json(NOMINATIM, params)
        if not isinstance(data, list): raise ServiceError("data")
        allowed = {"city", "town", "village", "municipality", "county", "state", "administrative"}
        for item in data:
            if not isinstance(item, dict) or item.get("type") not in allowed: continue
            address = item.get("address", {})
            if not isinstance(address, dict) or not address.get("country"): continue
            try: place = {"name": _traditional(item["display_name"].split(",")[0]), "country": _traditional(address["country"]), "latitude": float(item["lat"]), "longitude": float(item["lon"])}
            except (KeyError, ValueError, TypeError): continue
            self.cache[f"nom:{taiwan_only}:{query.casefold()}"] = place
            return place
        return None

    def _localize_place(self, place: dict) -> dict:
        """Get the Traditional-Chinese locality for an already unambiguous point.

        Geocoding is intentionally done in English first: changing Open-Meteo's
        response language can alter its ranking (for example, New York may become
        York, Nebraska). Reverse lookup keeps the chosen coordinates intact.
        """
        key = f"reverse:{place['latitude']:.4f}:{place['longitude']:.4f}"
        localized = self.cache.get(key)
        if localized:
            return {**place, **localized}
        delay = 1.0 - (time.monotonic() - self._last_nominatim)
        if delay > 0: time.sleep(delay)
        self._last_nominatim = time.monotonic()
        data = _json(NOMINATIM_REVERSE, {"lat": place["latitude"], "lon": place["longitude"], "format": "jsonv2", "addressdetails": 1, "accept-language": "zh-TW"})
        if not isinstance(data, dict) or not isinstance(data.get("address"), dict):
            raise ServiceError("data")
        address = data["address"]
        name = next((address.get(field) for field in ("city", "town", "village", "municipality", "county", "state") if address.get(field)), None)
        country = address.get("country")
        if not name or not country: raise ServiceError("data")
        localized = {"name_zh": _deduplicate_label(name), "country": _deduplicate_label(country)}
        self.cache[key] = localized
        return {**place, **localized}

    def geocode(self, query: str, lang: str) -> dict:
        clean = query.strip()
        if not clean: raise ServiceError("not_found")
        taiwan = TAIWAN.get(clean)
        # Always select candidates using English.  Translating this API response
        # changes ranking for some ambiguous international names.
        service_language = "en"
        if taiwan:
            found = self._open_meteo_geocode(taiwan[0], "TW", service_language)
            if found:
                found["name_zh"] = taiwan[1]
                if lang == "zh-TW":
                    found["country"] = "臺灣"
                return found
            # Official-name Nominatim fallback is country-limited and POIs are rejected.
            found = self._nominatim(taiwan[1], True)
            if found:
                found["name_zh"] = taiwan[1]
                if lang == "zh-TW":
                    found["country"] = "臺灣"
                return found
        found = self._open_meteo_geocode(clean, language=service_language)
        if found:
            if lang == "zh-TW":
                known_name = CITY_ZH.get(str(found["name"]).casefold())
                known_country = COUNTRY_ZH.get(str(found["country"]).casefold())
                if known_name:
                    return {**found, "name_zh": known_name, "country": known_country or found["country"]}
                return self._localize_place(found)
            return found
        # For Chinese queries, first give an eligible Taiwan locality a safe preference.
        if any("\u4e00" <= char <= "\u9fff" for char in clean):
            found = self._nominatim(clean, True) or self._nominatim(clean, False)
        else:
            found = self._nominatim(clean, False)
        if found: return found
        raise ServiceError("not_found")

    def locate_by_ip(self, lang: str) -> dict:
        try: data = _json(IPAPI)
        except ServiceError as exc: raise ServiceError("ip") from exc
        if not isinstance(data, dict): raise ServiceError("ip")
        try:
            place = {"name": data["city"], "country": data.get("country_name") or data["country"], "latitude": float(data["latitude"]), "longitude": float(data["longitude"])}
            if lang == "zh-TW":
                place["name_zh"] = CITY_ZH.get(str(place["name"]).casefold(), _traditional(place["name"]))
                place["country"] = COUNTRY_ZH.get(str(place["country"]).casefold(), _traditional(place["country"]))
            return place
        except (KeyError, TypeError, ValueError): raise ServiceError("ip")

    def current_weather(self, latitude: float, longitude: float) -> dict:
        params = {"latitude": latitude, "longitude": longitude, "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,is_day,wind_speed_10m,cloud_cover", "timezone": "auto"}
        data = _json(OPEN_METEO_WEATHER, params)
        if not isinstance(data, dict) or not isinstance(data.get("current"), dict) or not isinstance(data.get("current_units"), dict): raise ServiceError("data")
        c, units = data["current"], data["current_units"]
        keys = {"time", "temperature_2m", "apparent_temperature", "relative_humidity_2m", "precipitation", "weather_code", "is_day", "wind_speed_10m", "cloud_cover"}
        if not keys.issubset(c): raise ServiceError("data")
        code = c["weather_code"]
        condition = WEATHER_CODES.get(code, (f"未知天氣代碼 {code}", f"Unknown weather code {code}"))
        return {"time": c["time"], "temperature": c["temperature_2m"], "apparent_temperature": c["apparent_temperature"], "humidity": c["relative_humidity_2m"], "precipitation": c["precipitation"], "wind_speed": c["wind_speed_10m"], "cloud_cover": c["cloud_cover"], "is_day": bool(c["is_day"]), "condition": {"zh-TW": condition[0], "en": condition[1]}, "units": {"temperature": units.get("temperature_2m", "°C"), "humidity": units.get("relative_humidity_2m", "%"), "precipitation": units.get("precipitation", "mm"), "wind_speed": units.get("wind_speed_10m", "km/h"), "cloud_cover": units.get("cloud_cover", "%")}}
