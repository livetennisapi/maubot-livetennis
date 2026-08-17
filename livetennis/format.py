"""Pure formatting/derivation helpers for the Live Tennis API maubot plugin.

Everything in this module is side-effect free and imports nothing from
maubot/mautrix, so it can be unit-tested with plain pytest.

API shapes follow the published OpenAPI spec:
https://github.com/livetennisapi/openapi/blob/main/openapi.yaml
"""

from __future__ import annotations

from typing import Any

SERVE_MARKER = "*"

_MOVEMENT_ARROWS = {"up": "▲", "down": "▼", "same": "="}


def _player_name(match: dict[str, Any], slot: str) -> str:
    player = (match.get("players") or {}).get(slot) or {}
    return player.get("name") or "?"


def games_summary(games: Any) -> str:
    """Render the per-set games arrays as "6-4 3-2".

    ``games`` is ``[games_p1, games_p2]`` where each entry is a per-set list.
    Returns "" when the arrays are missing, empty, or uneven (all states the
    API documents as real, e.g. completed matches observed live carry empty
    games arrays).
    """
    if not isinstance(games, (list, tuple)) or len(games) != 2:
        return ""
    p1, p2 = games
    if not isinstance(p1, (list, tuple)) or not isinstance(p2, (list, tuple)):
        return ""
    n = min(len(p1), len(p2))
    return " ".join(f"{p1[i]}-{p2[i]}" for i in range(n))


def points_display(score: dict[str, Any]) -> str:
    """Render current in-game points ("30-15", or "TB 5-3" in a tiebreak).

    Returns "" when either point entry is null/absent — the spec says entries
    can be NULL and must not be decoded into non-nullable strings.
    """
    points = score.get("points")
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        return ""
    p1, p2 = points[0], points[1]
    if p1 is None or p2 is None:
        return ""
    prefix = "TB " if score.get("is_tiebreak") else ""
    return f"{prefix}{p1}-{p2}"


def is_break_point(score: dict[str, Any]) -> bool:
    """Derive break-point state from the current score snapshot.

    A break point is: receiver at AD, or receiver at 40 while the server is
    at 0/15/30. Never in tiebreaks. False when server or points are null.
    """
    if score.get("is_tiebreak"):
        return False
    server = score.get("server")
    if server not in (1, 2):
        return False
    points = score.get("points")
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        return False
    server_pts = points[server - 1]
    receiver_pts = points[2 - server]
    if server_pts is None or receiver_pts is None:
        return False
    if receiver_pts == "AD":
        return True
    return receiver_pts == "40" and server_pts in ("0", "15", "30")


def format_live_match(match: dict[str, Any]) -> str:
    """One line for one live match: names, serving marker, score, context.

    Example: ``Sinner* vs Alcaraz — 6-4 3-2 (30-15) [BP] — Wimbledon, SF``
    """
    score = match.get("score") or {}
    server = score.get("server")
    n1 = _player_name(match, "p1") + (SERVE_MARKER if server == 1 else "")
    n2 = _player_name(match, "p2") + (SERVE_MARKER if server == 2 else "")

    parts = [f"{n1} vs {n2}"]

    score_bits = []
    games = games_summary(score.get("games"))
    if games:
        score_bits.append(games)
    pts = points_display(score)
    if pts:
        score_bits.append(f"({pts})")
    if is_break_point(score):
        score_bits.append("[BP]")
    if score_bits:
        parts.append(" ".join(score_bits))
    else:
        parts.append("score pending")

    context_bits = [b for b in (match.get("tournament"), match.get("round_code")) if b]
    if context_bits:
        parts.append(", ".join(context_bits))

    return " — ".join(parts)


def format_fixture(fixture: dict[str, Any]) -> str:
    """One line for one scheduled fixture.

    Example: ``14:30 UTC — Sinner vs Alcaraz — Wimbledon, SF``
    A null start_time is a real state (order of play not out yet) and is
    shown as the event date or "TBD".
    """
    start = fixture.get("start_time")
    if start:
        # "2026-08-17T14:30:00Z" -> "14:30 UTC"
        when = start[11:16] + " UTC" if len(start) >= 16 else start
    else:
        when = fixture.get("event_date") or "TBD"

    n1 = fixture.get("player1_name") or "?"
    n2 = fixture.get("player2_name") or "?"
    parts = [when, f"{n1} vs {n2}"]

    context_bits = [
        b for b in (fixture.get("tournament"), fixture.get("round_code")) if b
    ]
    if context_bits:
        parts.append(", ".join(context_bits))

    return " — ".join(parts)


def format_ranking(player: dict[str, Any]) -> str | None:
    """Render a player's own current ranking, e.g. "#1 (11,830 pts ▲)".

    Returns None when the API has no ranking for the player (null is a real
    state on lower tours) — the caller should say "unranked / no ranking
    data" rather than invent one.
    """
    ranking = player.get("ranking")
    if ranking is None:
        return None
    extras = []
    points = player.get("ranking_points")
    if points is not None:
        extras.append(f"{points:,} pts")
    arrow = _MOVEMENT_ARROWS.get(player.get("ranking_movement") or "")
    if arrow:
        extras.append(arrow)
    suffix = f" ({' '.join(extras)})" if extras else ""
    return f"#{ranking}{suffix}"


def format_player_line(player: dict[str, Any]) -> str:
    """One line for one player search result.

    Example: ``Jannik Sinner (ITA) — ranking #1 (11,830 pts ▲)``
    """
    name = player.get("name") or "?"
    country = player.get("country")
    label = f"{name} ({country.upper()})" if country else name
    ranking = format_ranking(player)
    if ranking:
        return f"{label} — ranking {ranking}"
    return f"{label} — no current ranking data"


def format_player_detail(player: dict[str, Any]) -> str:
    """Multi-line detail for the top player search hit."""
    lines = [format_player_line(player)]
    bio_bits = []
    hand = player.get("hand")
    if hand:
        bio_bits.append(f"plays {'right' if hand == 'R' else 'left'}-handed")
    backhand = player.get("backhand")
    if backhand:
        bio_bits.append(f"{'one' if backhand == 1 else 'two'}-handed backhand")
    birthday = player.get("birthday")
    if birthday:
        bio_bits.append(f"born {birthday}")
    if bio_bits:
        lines.append(", ".join(bio_bits).capitalize())
    return "\n".join(lines)
