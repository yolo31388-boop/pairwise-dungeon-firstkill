"""副本首杀与竞速系统。

修复点：
1. 首杀记录保存完整成员快照（名字/职业/装等）与服务器时间戳。
2. 竞速计时从第一个战斗事件开始，进入副本到首战之间为准备期，不计入。
3. 排行榜按队伍人数分段，各段独立排名。
4. 时间一律使用服务器时间，校验异常（改客户端时间等）并自动标记。
5. 首杀成就与赛季绑定，赛季重置清除首杀标记但保留历史记录。
6. 同名次并列（1,1,3），并列时按通关时间戳、记录ID次级排序。
7. 记录按赛季分区，支持跨赛季查询与对比。
"""
import copy
import math
import time
from dataclasses import dataclass, field

MIN_VALID_DURATION = 1.0
MAX_VALID_DURATION = 7 * 24 * 3600.0


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
    flagged: bool = False
    flag_reason: str = ""
    enter_time: float = 0.0
    first_combat_time: float = 0.0


class FirstKillSystem:
    def __init__(self, clock=None):
        self.records: list[RunRecord] = []
        self.first_kills: dict[str, str] = {}  # dungeon_id -> rid（当前赛季标记）
        self._clock = clock or time.time
        self.season = "s1"

    @property
    def season(self) -> str:
        return self._season

    @season.setter
    def season(self, value: str) -> None:
        old = getattr(self, "_season", None)
        if old is not None and value != old:
            # 赛季重置：清除当前赛季的首杀标记，历史记录完整保留
            self.first_kills.clear()
        self._season = str(value)

    def reset_season(self, new_season: str) -> None:
        """切换赛季：首杀标记清空，历史记录保留。"""
        self.season = new_season

    def _now(self) -> float:
        return self._clock()

    def _find_record(self, rid: str):
        for rec in self.records:
            if rec.rid == rid:
                return rec
        return None

    @staticmethod
    def _snapshot_members(members) -> list:
        if not members:
            return []
        return [copy.deepcopy(m) for m in members]

    # ---- 竞速计时（bug2 修复）----

    def get_race_start_time(self, enter_time: float, first_combat_time: float) -> float:
        """竞速起点为第一个战斗事件；进入到首战之间是准备期，不计入。"""
        if first_combat_time is None:
            return enter_time
        return first_combat_time

    def get_preparation_time(self, enter_time: float, first_combat_time: float) -> float:
        """准备期时长（进入副本 -> 第一次战斗），不参与竞速计时。"""
        return max(0.0, first_combat_time - enter_time)

    def calc_race_duration(self, enter_time: float, first_combat_time: float,
                           finish_time: float) -> float:
        """根据进入/首战/通关三个服务器时间点计算竞速用时。"""
        start = self.get_race_start_time(enter_time, first_combat_time)
        return finish_time - start

    # ---- 时间校验（bug4 修复）----

    def _check_time(self, duration, server_time, enter_time=None,
                    first_combat_time=None) -> tuple[bool, str]:
        try:
            dur = float(duration)
        except (TypeError, ValueError):
            return False, "通关时长不是数值"
        if not math.isfinite(dur):
            return False, "通关时长非法（NaN/Inf）"
        if dur < 0:
            return False, "通关时长为负（疑似篡改客户端时间）"
        if dur < MIN_VALID_DURATION:
            return False, f"通关时长 {dur}s 小于物理下限 {MIN_VALID_DURATION}s"
        if dur > MAX_VALID_DURATION:
            return False, f"通关时长 {dur}s 超过副本上限 {MAX_VALID_DURATION}s"
        if enter_time is not None and first_combat_time is not None:
            if first_combat_time < enter_time:
                return False, "首次战斗时间早于进入副本时间"
        if first_combat_time is not None and server_time is not None:
            if server_time < first_combat_time:
                return False, "通关时刻早于首次战斗（疑似篡改客户端时间）"
            if server_time - first_combat_time + 1e-6 < dur:
                return False, "通关时长超过服务器观测到的实际耗时"
        return True, ""

    def validate_time(self, duration: float, server_time: float,
                      enter_time: float = None, first_combat_time: float = None) -> bool:
        ok, _ = self._check_time(duration, server_time, enter_time, first_combat_time)
        return ok

    # ---- 记录写入（bug1 / bug4 修复）----

    def _add_record(self, dungeon_id: str, members: list, duration: float,
                    is_first_kill: bool, season: str,
                    enter_time=None, first_combat_time=None) -> RunRecord:
        now = self._now()
        snapshot = self._snapshot_members(members)
        valid, reason = self._check_time(duration, now, enter_time, first_combat_time)
        rec = RunRecord(
            rid=f"r{len(self.records)}",
            dungeon_id=dungeon_id,
            season=season,
            members=snapshot,
            duration=float(duration),
            player_count=len(snapshot),
            timestamp=now,
            is_first_kill=is_first_kill,
            flagged=not valid,
            flag_reason=reason,
            enter_time=enter_time or 0.0,
            first_combat_time=first_combat_time or 0.0,
        )
        self.records.append(rec)
        return rec

    def record_run(self, dungeon_id: str, members: list, duration: float,
                   enter_time: float = None, first_combat_time: float = None,
                   season: str = None) -> RunRecord:
        """记录一次普通通关；异常时间自动标记 flagged，不进入排行榜。"""
        return self._add_record(dungeon_id, members, duration, False,
                                season or self.season, enter_time, first_combat_time)

    def record_first_kill(self, dungeon_id: str, members: list, duration: float,
                          enter_time: float = None, first_combat_time: float = None,
                          season: str = None) -> RunRecord:
        """记录首杀：完整成员快照（名字/职业/装等）+ 服务器时间戳。

        仅当该副本在目标赛季尚无首杀时才授予首杀成就。
        """
        target_season = season or self.season
        is_first = self.can_claim_first_kill(dungeon_id, target_season)
        rec = self._add_record(dungeon_id, members, duration, is_first, target_season,
                               enter_time, first_combat_time)
        if is_first:
            self.first_kills[dungeon_id] = rec.rid
        return rec

    # ---- 首杀赛季绑定（bug5 修复）----

    def can_claim_first_kill(self, dungeon_id: str, season: str = None) -> bool:
        """同赛季首杀只能拿一次；跨赛季首杀标记已随重置清除。"""
        target_season = season or self.season
        rid = self.first_kills.get(dungeon_id)
        if rid is None:
            return True
        rec = self._find_record(rid)
        if rec is None:
            return False  # 存在当前赛季首杀标记
        return rec.season != target_season

    # ---- 排行榜（bug3 / bug6 修复）----

    def get_leaderboard(self, dungeon_id: str, player_count: int = None,
                        season: str = None) -> list:
        """排行榜按队伍人数分段、按赛季隔离；异常记录不参与排名。

        次级排序：通关时间戳升序、记录ID升序（先达成者靠前）。
        """
        rows = [
            r for r in self.records
            if r.dungeon_id == dungeon_id
            and (player_count is None or r.player_count == player_count)
            and (season is None or r.season == season)
            and not r.flagged
        ]
        return sorted(rows, key=lambda r: (r.duration, r.timestamp, r.rid))

    def get_rank(self, duration: float, dungeon_id: str,
                 player_count: int = None, season: str = None) -> int:
        """并列同名次：1,1,3（严格小于自己的成绩数 + 1，标准竞赛排名）。"""
        board = self.get_leaderboard(dungeon_id, player_count=player_count,
                                     season=season)
        if not any(r.duration == duration for r in board):
            return len(board) + 1
        return sum(1 for r in board if r.duration < duration) + 1

    # ---- 赛季分区与跨赛季查询（bug7 修复）----

    def get_season_records(self, dungeon_id: str, season: str = None) -> list:
        target = season or self.season
        return [r for r in self.records
                if r.dungeon_id == dungeon_id and r.season == target]

    def get_cross_season_records(self, dungeon_id: str) -> dict:
        """按赛季分区返回某副本的全部历史记录，支持跨赛季查询。"""
        partitions: dict[str, list] = {}
        for rec in self.records:
            if rec.dungeon_id == dungeon_id:
                partitions.setdefault(rec.season, []).append(rec)
        return dict(sorted(partitions.items()))

    def get_best_record(self, dungeon_id: str, season: str = None,
                        player_count: int = None):
        board = self.get_leaderboard(dungeon_id, player_count=player_count,
                                     season=season)
        return board[0] if board else None

    def compare_seasons(self, dungeon_id: str, season_a: str, season_b: str,
                        player_count: int = None) -> dict:
        """跨赛季对比：返回各赛季最佳成绩、差值与更快的赛季。"""
        best_a = self.get_best_record(dungeon_id, season_a, player_count)
        best_b = self.get_best_record(dungeon_id, season_b, player_count)
        result = {
            "dungeon_id": dungeon_id,
            "season_a": season_a,
            "season_b": season_b,
            "best_a": best_a,
            "best_b": best_b,
            "delta": None,
            "faster_season": None,
        }
        if best_a is not None and best_b is not None:
            result["delta"] = abs(best_a.duration - best_b.duration)
            result["faster_season"] = (
                season_a if best_a.duration <= best_b.duration else season_b
            )
        return result
