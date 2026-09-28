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
weather related tools.

Configuration:

- `LLM_API_KEY` - API key for the ChatGPT-compatible provider.
- `LLM_BASE_URL` - API base URL for a ChatGPT-compatible endpoint.
- `LLM_MODEL` - model name.
- `LLM_TEMPERATURE` - model temperature.
- `LLM_REQUEST_TIMEOUT` - model request timeout in seconds.

Local runs automatically load these variables from `.env`.

## Telegram Bot

SkyAgent can run as a Telegram bot using long polling.

Configuration:

- `TELEGRAM_BOT_TOKEN` - token from BotFather.
- `TELEGRAM_POLL_TIMEOUT` - long polling timeout in seconds, defaults to 30.
- `TELEGRAM_REQUEST_TIMEOUT` - Telegram API request timeout in seconds, defaults to 35.

Run locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with your BotFather token and LLM provider settings, then run:

```bash
python -m src.main
```

Run with Docker Compose:

```bash
docker compose up --build
```

The bot registers `/start` and `/help` in Telegram's command menu. Send a text
question such as `Погода в Москве завтра`. Each question is independent; include
the city and forecast period in each message. Commands addressed to another bot
are ignored. Photos, voice messages and other non-text updates are ignored.

At startup, the bot removes any existing webhook without dropping pending
updates. Run only one polling instance per token. Invalid credentials or a
polling conflict stop the process; transient polling failures are retried.
Telegram rate limits are retried up to twice using the server's `retry_after`.
Other message delivery failures are logged and skipped so one inaccessible chat
does not block the queue. Update offsets are held in memory, so a restart can
redeliver an unconfirmed update.

`TELEGRAM_REQUEST_TIMEOUT` must exceed `TELEGRAM_POLL_TIMEOUT`. Ctrl+C and Docker's
SIGTERM stop polling and close the HTTP client. Default application logs suppress
HTTP request URLs because Telegram URLs contain the bot token.

Run the offline test suite:

```bash
python -m pytest -q
```
