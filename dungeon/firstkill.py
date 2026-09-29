"""副本首杀与竞速系统 - 含7个bug"""
from dataclasses import dataclass, field

@dataclass
class RunRecord:
    rid: str
    dungeon_id: str
    season: str
    members: list = field(default_factory=list)
    duration: float = 0
    player_count: int = 5
    timestamp: float = 0
    is_first_kill: bool = False

class FirstKillSystem:
    def __init__(self):
        self.records: list[RunRecord] = []
        self.first_kills: dict[str, str] = {}  # dungeon_id -> rid
        self.season = "s1"

    def record_first_kill(self, dungeon_id: str, members: list, duration: float):
        # bug1: 不存成员详情
        rec = RunRecord(f"r{len(self.records)}", dungeon_id, self.season, members, duration)
        rec.is_first_kill = True
        self.records.append(rec)
        self.first_kills[dungeon_id] = rec.rid

    def get_race_start_time(self, enter_time: float, first_combat_time: float) -> float:
        # bug2: 从进入开始算
        return enter_time

    def get_leaderboard(self, dungeon_id: str, player_count: int = None) -> list:
        # bug3: 不按人数分段
        return sorted([r for r in self.records if r.dungeon_id == dungeon_id], key=lambda x: x.duration)

    def validate_time(self, duration: float, server_time: float) -> bool:
        # bug4: 无防作弊
        return True

    def can_claim_first_kill(self, dungeon_id: str, season: str) -> bool:
        # bug5: 可重复获取
        return True

    def get_rank(self, duration: float, dungeon_id: str) -> int:
        # bug6: 同分不并列
        board = self.get_leaderboard(dungeon_id)
        for i, r in enumerate(board):
            if r.duration == duration:
                return i + 1
        return len(board) + 1

    def get_season_records(self, dungeon_id: str, season: str) -> list:
        # bug7: 不按赛季区分
        return [r for r in self.records if r.dungeon_id == dungeon_id]
