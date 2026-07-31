# SkyAgent
Weather assistant based on LLM agents. Provides personalized weather forecasts, recommendations, and natural language interaction.

## Weather API

The project uses Open-Meteo Weather Forecast API.

Configuration:

- `WEATHER_DEFAULT_LATITUDE` - fallback forecast latitude, defaults to Moscow.
- `WEATHER_DEFAULT_LONGITUDE` - fallback forecast longitude, defaults to Moscow.
- `WEATHER_DEFAULT_FORECAST_DAYS` - fallback forecast length from 1 to 16 days, default to 3 days.
- `WEATHER_DEFAULT_TIMEZONE` - fallback timezone for forecast timestamps, defaults to `auto`.
