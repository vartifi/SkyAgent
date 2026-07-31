# SkyAgent
Weather assistant based on LLM agents. Provides personalized weather forecasts, recommendations, and natural language interaction.

## Weather API

The project uses Open-Meteo Weather Forecast API.

Configuration:

- `WEATHER_DEFAULT_LATITUDE` - fallback forecast latitude for weather tools.
- `WEATHER_DEFAULT_LONGITUDE` - fallback forecast longitude for weather tools.
- `WEATHER_DEFAULT_FORECAST_DAYS` - fallback forecast length from 1 to 16 days.
- `WEATHER_DEFAULT_TIMEZONE` - fallback timezone for forecast timestamps.

## LLM Agent

SkyAgent uses a LangChain ReAct-style agent backed by OpenAI ChatGPT models. The
agent receives user questions, decides when weather data is needed, and calls the
weather relatied tools.

Configuration:

- `LLM_API_KEY` - API key for the ChatGPT-compatible provider.
- `LLM_BASE_URL` - API base URL for a ChatGPT-compatible endpoint.
- `LLM_MODEL` - model name.
- `LLM_TEMPERATURE` - model temperature.
- `LLM_REQUEST_TIMEOUT` - model request timeout in seconds.

Local runs automatically load these variables from `.env`.

