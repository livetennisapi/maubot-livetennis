"""Unit tests for the pure formatting/derivation helpers.

Shapes mirror the published OpenAPI spec (nullable points/server, empty
games arrays on some completed matches, null fixture start times).
"""

from livetennis.format import (
    format_fixture,
    format_live_match,
    format_player_detail,
    format_player_line,
    format_ranking,
    games_summary,
    is_break_point,
    points_display,
)


def make_score(**overrides):
    score = {
        "sets": [1, 0],
        "games": [[6, 3], [4, 2]],
        "points": ["30", "15"],
        "server": 1,
        "is_tiebreak": False,
        "win_probability_p1": None,
        "danger": None,
        "timestamp": "2026-08-17T14:00:00Z",
    }
    score.update(overrides)
    return score


def make_match(**overrides):
    match = {
        "id": 12345,
        "tournament": "Wimbledon",
        "tour": "atp",
        "round_code": "SF",
        "status": "live",
        "players": {
            "p1": {"id": 1, "name": "Sinner"},
            "p2": {"id": 2, "name": "Alcaraz"},
        },
        "score": make_score(),
    }
    match.update(overrides)
    return match


class TestGamesSummary:
    def test_two_sets(self):
        assert games_summary([[6, 3], [4, 2]]) == "6-4 3-2"

    def test_empty_arrays(self):
        # Observed live on completed matches per the spec.
        assert games_summary([[], []]) == ""

    def test_missing(self):
        assert games_summary(None) == ""
        assert games_summary([[6]]) == ""

    def test_uneven_arrays_use_common_prefix(self):
        assert games_summary([[6, 3], [4]]) == "6-4"


class TestPointsDisplay:
    def test_normal(self):
        assert points_display(make_score()) == "30-15"

    def test_null_point_entry(self):
        # Entries can be NULL per the spec; never render a null.
        assert points_display(make_score(points=[None, "15"])) == ""
        assert points_display(make_score(points=["30", None])) == ""

    def test_missing_points(self):
        assert points_display(make_score(points=None)) == ""

    def test_tiebreak_prefix(self):
        assert points_display(make_score(points=["5", "3"], is_tiebreak=True)) == "TB 5-3"


class TestIsBreakPoint:
    def test_receiver_at_ad(self):
        assert is_break_point(make_score(server=1, points=["40", "AD"]))

    def test_receiver_at_40_server_below(self):
        for server_pts in ("0", "15", "30"):
            assert is_break_point(make_score(server=1, points=[server_pts, "40"]))

    def test_deuce_is_not_break_point(self):
        assert not is_break_point(make_score(server=1, points=["40", "40"]))

    def test_server_advantage_is_not_break_point(self):
        assert not is_break_point(make_score(server=1, points=["AD", "40"]))

    def test_server_two_perspective(self):
        assert is_break_point(make_score(server=2, points=["40", "15"]))
        assert not is_break_point(make_score(server=2, points=["15", "40"]))

    def test_never_in_tiebreak(self):
        assert not is_break_point(
            make_score(server=1, points=["6", "5"], is_tiebreak=True)
        )

    def test_null_server_or_points(self):
        assert not is_break_point(make_score(server=None))
        assert not is_break_point(make_score(points=None))
        assert not is_break_point(make_score(points=[None, "40"]))


class TestFormatLiveMatch:
    def test_full_line_with_serving_marker(self):
        line = format_live_match(make_match())
        assert line == "Sinner* vs Alcaraz — 6-4 3-2 (30-15) — Wimbledon, SF"

    def test_marker_follows_server(self):
        line = format_live_match(make_match(score=make_score(server=2)))
        assert "Sinner vs Alcaraz*" in line

    def test_break_point_flag(self):
        line = format_live_match(make_match(score=make_score(points=["15", "40"])))
        assert "[BP]" in line

    def test_no_score_yet(self):
        line = format_live_match(make_match(score=None))
        assert "score pending" in line
        assert "*" not in line

    def test_missing_round_code(self):
        line = format_live_match(make_match(round_code=None))
        assert line.endswith("— Wimbledon")


class TestFormatFixture:
    def test_with_start_time(self):
        line = format_fixture(
            {
                "start_time": "2026-08-17T14:30:00Z",
                "player1_name": "Sinner",
                "player2_name": "Alcaraz",
                "tournament": "Wimbledon",
                "round_code": "SF",
            }
        )
        assert line == "14:30 UTC — Sinner vs Alcaraz — Wimbledon, SF"

    def test_null_start_time_falls_back_to_date(self):
        # A date-only fixture is a real state per the spec.
        line = format_fixture(
            {
                "start_time": None,
                "event_date": "2026-08-17",
                "player1_name": "Sinner",
                "player2_name": "Alcaraz",
            }
        )
        assert line.startswith("2026-08-17 — ")

    def test_everything_null(self):
        assert format_fixture({}) == "TBD — ? vs ?"


class TestFormatRanking:
    def test_full(self):
        player = {"ranking": 1, "ranking_points": 11830, "ranking_movement": "up"}
        assert format_ranking(player) == "#1 (11,830 pts ▲)"

    def test_no_ranking_is_none(self):
        assert format_ranking({"ranking": None}) is None

    def test_rank_only(self):
        assert format_ranking({"ranking": 42}) == "#42"


class TestFormatPlayer:
    def test_line_with_country_and_ranking(self):
        player = {"name": "Jannik Sinner", "country": "ita", "ranking": 1}
        assert format_player_line(player) == "Jannik Sinner (ITA) — ranking #1"

    def test_line_without_ranking(self):
        player = {"name": "A Junior", "country": None, "ranking": None}
        assert format_player_line(player) == "A Junior — no current ranking data"

    def test_detail_includes_bio(self):
        player = {
            "name": "Jannik Sinner",
            "country": "ita",
            "ranking": 1,
            "hand": "R",
            "backhand": 2,
            "birthday": "2001-08-16",
        }
        detail = format_player_detail(player)
        assert "right-handed" in detail
        assert "two-handed backhand" in detail
        assert "born 2001-08-16" in detail

    def test_detail_without_bio(self):
        detail = format_player_detail({"name": "X", "ranking": None})
        assert detail == "X — no current ranking data"
