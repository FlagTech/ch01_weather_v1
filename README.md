# Personal Weather CLI

以 Python 標準函式庫實作的即時天氣命令列工具。

```powershell
uv run weather 基隆
uv run weather "New York" --lang en
uv run weather
```

未帶地名時，工具會使用 `ipapi.co` 以公開 IP 推測城市；結果只代表大略位置。

天氣資料由 [Open-Meteo](https://open-meteo.com/) 提供。中文／台灣地名的備援地理編碼使用 [OpenStreetMap Nominatim](https://www.openstreetmap.org/copyright) 資料；程式對該服務實作每秒一次節流與記憶體快取，且只接受行政區與聚落結果。

## 開發與測試

```powershell
uv run python -m unittest discover -s tests
```
