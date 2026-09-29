"""副本首杀与竞速系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dungeon.firstkill import FirstKillSystem, RunRecord

class TestFirstKillMembers:
    def test_first_kill_stores_member_details(self):
        fks = FirstKillSystem()
        members = [{"name": "Alice", "class": "warrior", "ilevel": 200}]
        fks.record_first_kill("d1", members, 120.0)
        rec = fks.records[0]
        assert len(rec.members) > 0
        assert rec.members[0].get("class") == "warrior"  # bug1: 可能只存了名字

class TestRaceStartTime:
    def test_timer_starts_at_first_combat(self):
        fks = FirstKillSystem()
        start = fks.get_race_start_time(enter_time=100, first_combat_time=150)
        assert start == 150  # bug2: 返回100

class TestLeaderboardByPartySize:
    def test_leaderboard_separated_by_party_size(self):
        fks = FirstKillSystem()
        fks.records = [
            RunRecord("r1", "d1", "s1", [], 100, player_count=5),
            RunRecord("r2", "d1", "s1", [], 90, player_count=10),
        ]
        board5 = fks.get_leaderboard("d1", player_count=5)
        assert len(board5) == 1  # bug3: 返回2条
        assert board5[0].player_count == 5

class TestTimeValidation:
    def test_impossible_time_flagged(self):
        fks = FirstKillSystem()
        assert fks.validate_time(0.001, 1000) == False  # bug4: 0.001秒通关也通过

class TestFirstKillSeasonBound:
    def test_first_kill_resets_each_season(self):
        fks = FirstKillSystem()
        fks.first_kills["d1"] = "r1"
        fks.season = "s2"
        assert fks.can_claim_first_kill("d1", "s2") == True
        fks.first_kills["d1"] = "r2"  # s2拿了
        assert fks.can_claim_first_kill("d1", "s2") == False  # bug5: 还能拿

class TestTiedRanking:
    def test_same_duration_gets_same_rank(self):
        fks = FirstKillSystem()
        fks.records = [
            RunRecord("r1", "d1", "s1", [], 100),
            RunRecord("r2", "d1", "s1", [], 100),
            RunRecord("r3", "d1", "s1", [], 120),
        ]
        r1 = fks.get_rank(100, "d1")
        r3 = fks.get_rank(120, "d1")
        assert r1 == 1
        assert r3 == 3  # bug6: r3可能是第3但r1和r2应该都是第1

class TestSeasonSeparation:
    def test_records_filtered_by_season(self):
        fks = FirstKillSystem()
        fks.records = [
            RunRecord("r1", "d1", "s1", [], 100),
            RunRecord("r2", "d1", "s2", [], 90),
        ]
        s1 = fks.get_season_records("d1", "s1")
        assert len(s1) == 1  # bug7: 返回2条
        assert s1[0].season == "s1"
