import unittest
from unittest.mock import patch

from weather.cli import main, render
from weather.services import ServiceError, WeatherService


class WeatherTests(unittest.TestCase):
    @patch("weather.services._json")
    def test_chinese_output_uses_traditional_city_and_country_names(self, request):
        request.return_value = {"results": [{"name": "New York", "country": "United States", "country_code": "US", "latitude": 40.7, "longitude": -74.0}]}
        place = WeatherService().geocode("New York", "zh-TW")
        self.assertEqual(place["name_zh"], "紐約")
        self.assertEqual(place["country"], "美國")
        self.assertEqual(request.call_args_list[0].args[1]["language"], "en")

    @patch("weather.services._json")
    def test_taiwan_alias_uses_official_name_and_country_filter(self, request):
        request.return_value = {"results": [{"name": "Taoyuan City", "country": "Taiwan", "country_code": "TW", "latitude": 24.99, "longitude": 121.3}]}
        place = WeatherService().geocode("桃園", "zh-TW")
        self.assertEqual(place["country"], "臺灣")
        self.assertEqual(place["name_zh"], "桃園市")
        self.assertEqual(request.call_args.args[0], "https://geocoding-api.open-meteo.com/v1/search")
        self.assertEqual(request.call_args.args[1]["countryCode"], "TW")

    @patch("weather.services._json")
    def test_nominatim_rejects_poi(self, request):
        request.return_value = [{"type": "hairdresser", "display_name": "Boston Hair", "lat": "1", "lon": "2", "address": {"country": "Taiwan"}}]
        self.assertIsNone(WeatherService()._nominatim("波士頓", True))

    @patch("weather.services._json")
    def test_ip_location_is_localized_in_chinese(self, request):
        request.return_value = {"city": "Taipei", "country_name": "Taiwan", "latitude": 25.0, "longitude": 121.5}
        place = WeatherService().locate_by_ip("zh-TW")
        self.assertEqual(place["name_zh"], "臺北")
        self.assertEqual(place["country"], "臺灣")

    def test_render_is_translated_and_marks_ip(self):
        output = render({"name": "Taipei", "name_zh": "臺北市", "country": "Taiwan"}, {"time": "2026-01-01T12:00", "condition": {"zh-TW": "晴朗", "en": "Clear sky"}, "is_day": True, "temperature": 25, "apparent_temperature": 26, "humidity": 70, "precipitation": 0, "wind_speed": 5, "cloud_cover": 10, "units": {"temperature": "°C", "humidity": "%", "precipitation": "mm", "wind_speed": "km/h", "cloud_cover": "%"}}, "zh-TW", True)
        self.assertIn("依 IP 推測", output)
        self.assertIn("臺北市", output)

    @patch("weather.cli.WeatherService")
    def test_main_returns_nonzero_for_error(self, service):
        service.return_value.geocode.side_effect = ServiceError("not_found")
        self.assertEqual(main(["nowhere", "--lang", "en"]), 1)


if __name__ == "__main__":
    unittest.main()
