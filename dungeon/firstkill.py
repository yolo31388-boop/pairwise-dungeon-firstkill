"""副本首杀与竞速系统"""
import time
from dataclasses import dataclass, field

MIN_CLEAR_TIME = 1.0        # 秒，低于此视为异常时间
MAX_CLEAR_TIME = 4 * 3600   # 秒，超过此视为异常时间
SERVER_TIME_TOLERANCE = 60  # 服务器时间允许的未来漂移（秒）


@dataclass
class RunRecord:
    rid: str
    dungeon_id: str
    season: str
    members: list = field(default_factory=list)  # [{"name","class","ilevel"}, ...]
    duration: float = 0
    player_count: int = 5
    timestamp: float = 0      # 服务器时间戳
    is_first_kill: bool = False
    flagged: bool = False     # 异常时间自动标记


class _FirstKillMap(dict):
    """dungeon_id -> rid，写入时记录所属赛季，用于赛季绑定的首杀判定。"""

    def __init__(self, season_getter):
        super().__init__()
        self._season_getter = season_getter
        self.claim_seasons: dict[str, str] = {}  # dungeon_id -> 认领时的赛季

    def __setitem__(self, dungeon_id, rid):
        super().__setitem__(dungeon_id, rid)
        self.claim_seasons[dungeon_id] = self._season_getter()

    def clear(self):
        super().clear()
        self.claim_seasons.clear()


class FirstKillSystem:
    def __init__(self):
        self.records: list[RunRecord] = []
        self.first_kills = _FirstKillMap(lambda: self.season)
        self.first_kill_history: list[dict] = []  # 跨赛季保留的首杀历史
        self.season = "s1"

    # bug1 修复：保存完整成员列表（含职业、装等）与服务器时间戳，并做时间校验
    def record_first_kill(self, dungeon_id: str, members: list, duration: float):
        server_time = time.time()
        rec = RunRecord(
            rid=f"r{len(self.records)}",
            dungeon_id=dungeon_id,
            season=self.season,
            members=[dict(m) for m in members],
            duration=duration,
            player_count=len(members) or 5,
            timestamp=server_time,
            is_first_kill=True,
            flagged=not self.validate_time(duration, server_time),
        )
        self.records.append(rec)
        self.first_kills[dungeon_id] = rec.rid
        self.first_kill_history.append({
            "dungeon_id": dungeon_id,
            "rid": rec.rid,
            "season": self.season,
            "members": [dict(m) for m in members],
            "timestamp": server_time,
        })
        return rec

    # bug2 修复：计时从第一个战斗事件开始，进本到首战为准备期不计入
    def get_race_start_time(self, enter_time: float, first_combat_time: float) -> float:
        return first_combat_time

    def get_race_duration(self, enter_time: float, first_combat_time: float, finish_time: float) -> float:
        return finish_time - self.get_race_start_time(enter_time, first_combat_time)

    # bug3 修复：排行榜按队伍人数分段，各段独立排名；次级排序：先时间戳后rid
    def get_leaderboard(self, dungeon_id: str, player_count: int = None, season: str = None) -> list:
        board = [r for r in self.records if r.dungeon_id == dungeon_id]
        if player_count is not None:
            board = [r for r in board if r.player_count == player_count]
        if season is not None:
            board = [r for r in board if r.season == season]
        return sorted(board, key=lambda r: (r.duration, r.timestamp, r.rid))

    # bug4 修复：基于服务器时间校验，异常时间判定为不合法
    def validate_time(self, duration: float, server_time: float) -> bool:
        if server_time <= 0 or server_time > time.time() + SERVER_TIME_TOLERANCE:
            return False
        if duration < MIN_CLEAR_TIME or duration > MAX_CLEAR_TIME:
            return False
        return True

    # bug5 修复：首杀成就与赛季绑定，同赛季不可重复获取
    def can_claim_first_kill(self, dungeon_id: str, season: str) -> bool:
        return self.first_kills.claim_seasons.get(dungeon_id) != season

    # 赛季重置：清除当前首杀标记，历史记录保留
    def reset_season(self, new_season: str):
        self.first_kills.clear()
        self.season = new_season

    # bug6 修复：标准并列排名（1,1,3），耗时相同名次相同
    def get_rank(self, duration: float, dungeon_id: str, player_count: int = None) -> int:
        board = self.get_leaderboard(dungeon_id, player_count=player_count)
        return 1 + sum(1 for r in board if r.duration < duration)

    # bug7 修复：记录按赛季分区；season=None 时跨赛季查询
    def get_season_records(self, dungeon_id: str, season: str = None) -> list:
        recs = [r for r in self.records if r.dungeon_id == dungeon_id]
        if season is not None:
            recs = [r for r in recs if r.season == season]
        return recs

    # 跨赛季对比：每个赛季的最快成绩
    def compare_seasons(self, dungeon_id: str, player_count: int = None) -> dict:
        best: dict[str, RunRecord] = {}
        for r in self.get_leaderboard(dungeon_id, player_count=player_count):
            if r.season not in best:
                best[r.season] = r
        return best
