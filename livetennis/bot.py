"""Live Tennis API maubot plugin — on-demand `!tennis` commands.

Every command is a single one-shot request to the API when invoked. There
are no polling loops or background timers, so normal chat use stays well
inside the free tier's 100 requests/day.
"""

from __future__ import annotations

import datetime
from typing import Any

from maubot import MessageEvent, Plugin
from maubot.handlers import command
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

from .format import (
    format_fixture,
    format_live_match,
    format_player_detail,
    format_player_line,
)


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("api_key")
        helper.copy("base_url")
        helper.copy("max_results")


class LiveTennisBot(Plugin):
    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()

    @classmethod
    def get_config_class(cls) -> type[BaseProxyConfig]:
        return Config

    @property
    def _max_results(self) -> int:
        try:
            return max(1, min(int(self.config["max_results"]), 50))
        except (TypeError, ValueError):
            return 10

    async def _api_get(
        self, evt: MessageEvent, path: str, params: dict[str, Any] | None = None
    ) -> Any | None:
        """One GET against the API. Returns parsed JSON, or None after having
        already told the room what went wrong."""
        api_key = self.config["api_key"]
        if not api_key:
            await evt.respond(
                "No API key configured. Set `api_key` in the plugin instance "
                "config — a free key (no card) is available at "
                "https://livetennisapi.com/subscribe/free"
            )
            return None
        url = self.config["base_url"].rstrip("/") + path
        try:
            resp = await self.http.get(
                url, params=params or {}, headers={"X-API-Key": api_key}
            )
        except Exception:
            self.log.exception("Request to %s failed", path)
            await evt.respond("Could not reach the Live Tennis API — try again later.")
            return None
        if resp.status == 200:
            try:
                return await resp.json()
            except Exception:
                self.log.exception("Bad JSON from %s", path)
                await evt.respond("The API returned an unreadable response.")
                return None
        if resp.status == 401:
            await evt.respond(
                "The API rejected the configured key (401). Check `api_key` "
                "in the plugin instance config."
            )
        elif resp.status == 429:
            retry_after = resp.headers.get("Retry-After")
            hint = f" Retry in ~{retry_after}s." if retry_after else ""
            await evt.respond(f"Rate limit reached (429).{hint}")
        elif resp.status == 404:
            await evt.respond("Not found.")
        else:
            self.log.warning("Unexpected %s from %s", resp.status, path)
            await evt.respond(f"The API returned an unexpected error ({resp.status}).")
        return None

    @command.new(
        name="tennis",
        help="Live tennis scores, fixtures and player lookups",
        require_subcommand=True,
    )
    async def tennis(self, evt: MessageEvent) -> None:
        pass

    @tennis.subcommand("live", help="Matches in play right now, one line each")
    async def live(self, evt: MessageEvent) -> None:
        await evt.mark_read()
        body = await self._api_get(
            evt, "/matches", {"status": "live", "limit": self._max_results}
        )
        if body is None:
            return
        matches = body.get("data") or []
        if not matches:
            await evt.respond("No matches in play right now.")
            return
        lines = [format_live_match(m) for m in matches]
        meta = body.get("meta") or {}
        if meta.get("has_more"):
            lines.append(f"…and more (showing first {len(matches)})")
        await evt.respond("\n".join(lines))

    @tennis.subcommand("today", help="Today's scheduled fixtures (UTC)")
    async def today(self, evt: MessageEvent) -> None:
        await evt.mark_read()
        body = await self._api_get(evt, "/fixtures", {"limit": 50})
        if body is None:
            return
        fixtures = body.get("data") or []
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        todays = [f for f in fixtures if f.get("event_date") == today]
        if todays:
            lines = [format_fixture(f) for f in todays[: self._max_results]]
            if len(todays) > self._max_results:
                lines.append(f"…and {len(todays) - self._max_results} more today")
            await evt.respond("\n".join(lines))
            return
        if fixtures:
            lines = ["No fixtures scheduled today (UTC). Next up:"]
            lines += [format_fixture(f) for f in fixtures[: min(self._max_results, 5)]]
            await evt.respond("\n".join(lines))
        else:
            await evt.respond("No scheduled fixtures found.")

    @tennis.subcommand("player", help="Search a player and show their current ranking")
    @command.argument("name", pass_raw=True, required=True)
    async def player(self, evt: MessageEvent, name: str) -> None:
        await evt.mark_read()
        name = name.strip()
        if not name:
            await evt.respond("Usage: `!tennis player <name>`")
            return
        body = await self._api_get(
            evt, "/players", {"search": name, "limit": self._max_results}
        )
        if body is None:
            return
        players = body.get("data") or []
        if not players:
            await evt.respond(f"No players found matching '{name}'.")
            return
        lines = [format_player_detail(players[0])]
        if len(players) > 1:
            lines.append("")
            lines.append("Other matches:")
            lines += [format_player_line(p) for p in players[1:]]
        await evt.respond("\n".join(lines))
