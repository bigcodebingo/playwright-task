from pydantic import BaseModel
from typing import Optional, List

class RankInfo(BaseModel):
    rank: Optional[str] = None
    lp: Optional[int] = None
    wins: Optional[int] = None
    losses: Optional[int] = None
    win_rate: Optional[float] = None


class SeasonStats(BaseModel):
    """Represents statistics for a specific season."""
    season:Optional[str]
    rank: Optional[str]
    lp: Optional[int] = None

class ChampionStats(BaseModel):
    position: Optional[str] = None
    champion: Optional[str] = None
    champion_wins: Optional[int] = None
    champion_losses: Optional[int] = None
    champion_wr: Optional[float] = None
    champion_kda_ratio: Optional[float] = None
    champion_kda: Optional[str] = None
    champion_laning: Optional[float] = None
    champion_dmg_per_min: Optional[float] = None
    champion_dmg_share_ratio: Optional[float] = None
    champion_wards_score: Optional[float] = None
    champion_wards_placed: Optional[int] = None
    champion_wards_destroyed: Optional[int] = None
    champion_cs: Optional[float] = None
    champion_cs_per_min: Optional[float] = None
    champion_gold: Optional[int] = None
    champion_gold_per_min: Optional[float] = None
    champion_double: Optional[int] = None
    champion_triple: Optional[int] = None
    champion_quadra: Optional[int] = None
    champion_penta: Optional[int] = None    


class PlayerStats(BaseModel):
    """Complete player statistics from a parser."""
    nickname: Optional[str] = None
    # Solo queue stats
    current_rank_solo: Optional[RankInfo] = None
    best_rank_solo: Optional[RankInfo] = None
    previous_seasons_solo: Optional[List[SeasonStats]] = None
    
    # Flex queue stats  
    current_rank_flex: Optional[RankInfo] = None
    best_rank_flex: Optional[RankInfo] = None
    previous_seasons_flex: Optional[List[SeasonStats]] = None

    champions_solo: Optional[List[ChampionStats]] = None
    champions_flex: Optional[List[ChampionStats]] = None



    