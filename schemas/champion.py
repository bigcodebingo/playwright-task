from pydantic import BaseModel
from typing import Optional, List, Dict

class MetaChampion(BaseModel):
    """Represents summarized statistics for a champion in the current meta."""
    name: Optional[str] = None
    tier: Optional[str] = None
    lane: Optional[str] = None
    win: Optional[float] = None
    pick: Optional[float] = None
    ban: Optional[float] = None
    games: Optional[int] = None

class MetaStats(BaseModel):
    """List of all champions with their meta stats."""
    champions: Optional[List[MetaChampion]] = None

class CounterCard(BaseModel):
    """Performance of the selected champion against a specific opponent."""
    champion: Optional[str] = None
    wr_against: Optional[float] = None
    delta_1: Optional[float] = None
    delta_2: Optional[float] = None
    avg_wr_against: Optional[float] = None
    games: Optional[int] = None

class CounterCardV2(BaseModel):
    """Represents a counter matchup or teammate card with relevant statistics"""
    champion: Optional[str] = None
    wr: Optional[float] = None
    delta_1: Optional[float] = None
    delta_2: Optional[float] = None
    pr: Optional[float] = None
    games: Optional[int] = None

class ChampionCounters(BaseModel):
    """List of counter matchups for a specific champion."""
    champion: Optional[str] = None
    counters: Optional[List[CounterCard]] = None

class ObjectiveInfo(BaseModel):
    """Statistics related to map objectives secured or yielded."""
    secure_percent: Optional[float] = None
    secure_win_percent: Optional[float] = None
    yield_percent: Optional[float] = None
    yield_win_percent: Optional[float] = None

class ChampionStats(BaseModel):
    """Aggregated champion build statistics including matchups, teammates, and objectives."""
    champion: Optional[str] = None
    common_matchup: Optional[List[Dict[str, List[CounterCardV2]]]]
    common_teammates: Optional[List[Dict[str, List[CounterCardV2]]]]
    objectives: Optional[Dict[str, ObjectiveInfo]]