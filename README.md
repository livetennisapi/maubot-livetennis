# maubot-livetennis

A [maubot](https://github.com/maubot/maubot) plugin for live tennis scores,
fixtures and player lookups in Matrix rooms, powered by the
[Live Tennis API](https://livetennisapi.com).

> **Disclosure:** this plugin is written and maintained by the Live Tennis API
> team — it is the official maubot client for our own API.

## Commands

| Command | What it does |
|---|---|
| `!tennis live` | Matches in play right now — one line each with the score, a `*` serving marker, and a `[BP]` flag on break points |
| `!tennis today` | Today's scheduled fixtures (UTC), earliest first |
| `!tennis player <name>` | Search a player and show their bio + current ranking |

Example output:

```
Sinner* vs Alcaraz — 6-4 3-2 (30-15) [BP] — Wimbledon, SF
```

## Setup

1. Get a free API key (no card required): https://livetennisapi.com/subscribe/free
2. Download the `.mbp` file from the
   [latest release](https://github.com/livetennisapi/maubot-livetennis/releases)
   (or build it yourself, below) and upload it in the maubot manager.
3. Create an instance of the plugin and set `api_key` in its config.

## API tier honesty

The plugin uses **free-tier endpoints only** (`/matches?status=live`,
`/fixtures`, `/players`). The free tier allows **30 requests/minute and
100 requests/day**.

- Every command is a **one-shot request** made only when someone runs it.
  There are no polling loops or background timers, so normal chat use stays
  well within 100/day.
- A player's **own current ranking is free** (it is on the player object,
  which is what `!tennis player` shows). The rank-ordered rankings *listing*
  (`/rankings`) is a PRO endpoint and this plugin does not use it.
- Historical results, head-to-head and match statistics are paid tiers and
  are deliberately out of scope here.

API reference: https://docs.livetennisapi.com ·
OpenAPI spec: https://github.com/livetennisapi/openapi

## Break-point flag

`[BP]` is derived from the current score snapshot: the receiver is at AD, or
the receiver is at 40 while the server is at 0/15/30. It is never shown in
tiebreaks, and never shown when the server or point state is unknown.

## Building from source

```bash
pip install maubot
mbc build
```

This produces `com.livetennisapi.livetennis-v0.1.0.mbp`, ready to upload.

## Development

```bash
pip install maubot pytest pytest-asyncio ruff
ruff check .
pytest
```

The formatting/derivation logic lives in `livetennis/format.py` as pure
functions with unit tests in `tests/`.

## License

[MIT](LICENSE)
