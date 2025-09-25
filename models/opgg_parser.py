"""OP.GG parser implementation."""
import aiohttp
from lxml import html
from typing import Optional, List
from backend.workers.parser.schemas.player import PlayerStats, RankInfo, SeasonStats, ChampionStats

class OPGGParser:
    """Parser implementation for OP.GG website."""

    def is_valid_url(self, url: str) -> bool:
        """Check if URL is a valid OP.GG URL."""
        return "op.gg" in url.lower()


    def normalize_url(self, url: str) -> str:
        """
        Normalize OP.GG URL to English version.
        Converts to: https://op.gg/en/lol/{region}/{summoners}/{name}
        """
        parts = url.rstrip('/').split('/')
        # Take last 3 parts
        last3 = parts[-3:]
        return f"https://op.gg/en/lol/{last3[0]}/{last3[1]}/{last3[2]}"
    

    def normalize_url_champions_solo(self, url: str) -> str:
        """
        Normalize OP.GG URL to English version and append /champions if not present.
        Example: https://op.gg/en/lol/euw/summonerName -> https://op.gg/en/lol/euw/summonerName/champions?queue_type=SOLORANKED
        """
        base_url = self.normalize_url(url)
        if not base_url.endswith('/champions?queue_type=SOLORANKED'):
            base_url += '/champions?queue_type=SOLORANKED'
        return base_url


    def normalize_url_champions_flex(self, url: str) -> str:
        """
        Normalize OP.GG URL to English version and append /champions if not present.
        Example: https://op.gg/en/lol/euw/summonerName -> https://op.gg/en/lol/euw/summonerName/champions?queue_type=FLEXRANKED
        """
        base_url = self.normalize_url(url)
        if not base_url.endswith('/champions?queue_type=FLEXRANKED'):
            base_url += '/champions?queue_type=FLEXRANKED'
        return base_url


    async def _fetch_html(self, session: aiohttp.ClientSession, url: str) -> str:
        """Fetch HTML content from URL."""
        async with session.get(url) as response:
            return await response.text()


    def _parse_win_loss(self, wl_data: List[str]) -> tuple[Optional[int], Optional[int]]:
        """Parse win/loss data from XPath results."""
        if not wl_data or len(wl_data) < 2:
            return None, None
        
        try:
            # Usually format is like ["123W", "45L"]
            wins_str = wl_data[0]
            losses_str = wl_data[2]
            return int(wins_str) if wins_str else None, int(losses_str) if losses_str else None
        except (ValueError, IndexError):
            return None, None
    
    def _parse_previous_seasons(self, seasons: List[Optional[str]], ranks: List[Optional[str]], lps: List[Optional[str]]) -> List[SeasonStats]:
        """Parse previous seasons data."""
        previous_seasons = []
        for i, season in enumerate(seasons):
            rank = ranks[i] if i < len(ranks) else ""
            lp = lps[i] if i < len(lps) else None
            previous_seasons.append(SeasonStats(season=season, rank=rank, lp=lp))
        return previous_seasons


    def _parse_kda_ratio(self, val):
        if val is None:
            return None
        val = val.strip()
        if val.lower() == 'perfect':
            return None
        try:
            return float(val.split(':')[0])
        except Exception:
            return None


    def _parse_per_min(self, val):
        if val is None:
            return None
        val = val.strip()
        try:
            return float(val.replace('/m', '').replace(',', '').strip())
        except Exception:
            return None


    def _parse_wards_control(self, val):
        if val is None:
            return None, None
        val = val.strip()
        import re
        match = re.search(r'\((\d+)/(\d+)\)', val)
        if match:
            try:
                placed = int(match.group(1))
                destroyed = int(match.group(2))
                return placed, destroyed
            except Exception:
                return None, None
        return None, None


    def parse_champions(self, raw_data: dict) -> list:
        """Преобразует словарь с данными по чемпионам в список ChampionStats."""
        champions = []
        num_champions = len(raw_data.get('champion', []))
        for i in range(num_champions):
            def get_val(key, cast=None, custom_parser=None):
                val_list = raw_data.get(key, [])
                val = val_list[i] if i < len(val_list) else None
                if val is None:
                    return None
                if custom_parser:
                    return custom_parser(val)
                if cast:
                    try:
                        return cast(val.replace('%','').replace(',','').replace('W','').replace('L','').strip())
                    except Exception:
                        return None
                return val
            wards_placed, wards_destroyed = self._parse_wards_control(get_val('champion_wards_control', str))
            champions.append(ChampionStats(
                position=get_val('position', str),
                champion=get_val('champion', str),
                champion_wins=get_val('champion_wins', int),
                champion_losses=get_val('champion_losses', int),
                champion_wr=get_val('champion_wr', float),
                champion_kda_ratio=get_val('champion_kda_ratio', custom_parser=self._parse_kda_ratio),
                champion_kda=get_val('champion_kda', str),
                champion_laning=get_val('champion_laning', float),
                champion_dmg_per_min=get_val('champion_dmg_per_min', custom_parser=self._parse_per_min),
                champion_dmg_share_ratio=get_val('champion_dmg_share_ratio', float),
                champion_wards_score=get_val('champion_wards_score', float),
                champion_wards_placed=wards_placed,
                champion_wards_destroyed=wards_destroyed,
                champion_cs=get_val('champion_cs', float),
                champion_cs_per_min=get_val('champion_cs_per_min', custom_parser=self._parse_per_min),
                champion_gold=get_val('champion_gold', int),
                champion_gold_per_min=get_val('champion_gold_per_min', custom_parser=self._parse_per_min),
                champion_double=get_val('champion_double', int),
                champion_triple=get_val('champion_triple', int),
                champion_quadra=get_val('champion_quadra', int),
                champion_penta=get_val('champion_penta', int),
            ))
        return champions


    async def parse_player_stats(self, url: str) -> Optional[PlayerStats]:
        """Parse player statistics from OP.GG URL."""
        try:
            normalized_url_stats = self.normalize_url(url)
            normalized_url_champions_solo = self.normalize_url_champions_solo(normalized_url_stats)
            normalized_url_champions_flex = self.normalize_url_champions_flex(normalized_url_stats)
            
            async with aiohttp.ClientSession() as session:
                html_content_stats = await self._fetch_html(session, normalized_url_stats)
                tree_stats = html.fromstring(html_content_stats)

                html_content_champions_solo = await self._fetch_html(session, normalized_url_champions_solo)
                tree_champions_solo = html.fromstring(html_content_champions_solo)

                html_content_champions_flex = await self._fetch_html(session, normalized_url_champions_flex)
                tree_champions_flex = html.fromstring(html_content_champions_flex)
                
                # Define XPath conditions
                solo_cond = 'count(/html/body/div[5]/div/div/div[2]/aside/section[1]/div[1]/div//span[text()="Ranked Solo/Duo"]) > 0'
                flex_cond = 'count(/html/body/div[5]/div/div/div[2]/aside/section[2]/div[1]/div//span[text()="Ranked Flex"]) > 0'
                
                # Define XPath paths
                paths_stats = {
                    # Solo queue
                    "curr_rank_solo": f"/html/body/div[5]/div/div/div[2]/aside/section[1]/div[2]/div/div[1]/div[1]/div/strong[{solo_cond}]/text()",
                    "curr_lp_solo": f"/html/body/div[5]/div/div/div[2]/aside/section[1]/div[2]/div/div[1]/div[1]/div/span[{solo_cond}]/text()[1]",
                    "wl_solo": f"/html/body/div[5]/div/div/div[2]/aside/section[1]/div[2]/div/div[1]/div[2]/span[1][{solo_cond}]/text()[not(position()=3)]",
                    "wr_solo": f"/html/body/div[5]/div/div/div[2]/aside/section[1]/div[2]/div/div[1]/div[2]/span[2][{solo_cond}]/text()[3]",
                    "best_rank_solo": f"/html/body/div[5]/div/div/div[2]/aside/section[1]/div[2]/div/div[2]/div/div[2]/strong[{solo_cond}]/text()",
                    "best_lp_solo": f"/html/body/div[5]/div/div/div[2]/aside/section[1]/div[2]/div/div[2]/div/div[2]/span[{solo_cond}]/text()[1]",
                    "prev_seasons_solo": f"/html/body/div[5]/div/div/div[2]/aside/section[1]/div[2]/table/tbody/tr/td[1]/strong[{solo_cond}]/text()",
                    "prev_ranks_solo": f"/html/body/div[5]/div/div/div[2]/aside/section[1]/div[2]/table/tbody/tr/td[2]/div/div/span[{solo_cond}]/text()",
                    "prev_lps_solo": f"/html/body/div[5]/div/div/div[2]/aside/section[1]/div[2]/table/tbody/tr/td[3][{solo_cond}]/text()",
                    
                    # Flex queue
                    "curr_rank_flex": f"/html/body/div[5]/div/div/div[2]/aside/section[2]/div[2]/div/div[1]/div[1]/div/strong[{flex_cond}]/text()",
                    "curr_lp_flex": f"/html/body/div[5]/div/div/div[2]/aside/section[2]/div[2]/div/div[1]/div[1]/div/span[{flex_cond}]/text()[1]",
                    "wl_flex": f"/html/body/div[5]/div/div/div[2]/aside/section[2]/div[2]/div/div[1]/div[2]/span[1][{flex_cond}]/text()[not(position()=3)]",
                    "wr_flex": f"/html/body/div[5]/div/div/div[2]/aside/section[2]/div[2]/div/div[1]/div[2]/span[2][{flex_cond}]/text()[3]",
                    "best_rank_flex": f"/html/body/div[5]/div/div/div[2]/aside/section[2]/div[2]/div/div[2]/div/div[2]/strong[{flex_cond}]/text()",
                    "best_lp_flex": f"/html/body/div[5]/div/div/div[2]/aside/section[2]/div[2]/div/div[2]/div/div[2]/span[{flex_cond}]/text()[1]",
                    "prev_seasons_flex": f"/html/body/div[5]/div/div/div[2]/aside/section[2]/div[2]/table/tbody/tr/td[1]/strong[{flex_cond}]/text()",
                    "prev_ranks_flex": f"/html/body/div[5]/div/div/div[2]/aside/section[2]/div[2]/table/tbody/tr/td[2]/div/div/span[{flex_cond}]/text()",
                    "prev_lps_flex": f"/html/body/div[5]/div/div/div[2]/aside/section[2]/div[2]/table/tbody/tr/td[3][{flex_cond}]/text()"

                }
                
                paths_champions = {
                    # Champion stats table
                    "position":      '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td/text()',
                    "champion":      '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[2]/div/strong/text()',
                    "champion_wins": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[3]/div/div/div[1]/span/text()[1]',
                    "champion_losses": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[3]/div/div/div[2]/span/text()[1]',
                    "champion_wr":   '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[3]/div/span/text()',
                    "champion_kda_ratio": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[4]/span/div/text()',
                    "champion_kda":  '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[4]/span/span/text()',
                    "champion_laning": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[6]/span/span[1]/span[1]/text()',
                    "champion_dmg_per_min": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[7]/span/span[1]/text()',
                    "champion_dmg_share_ratio": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[7]/span/span[2]/text()',
                    "champion_wards_score": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[8]/span/span[1]/text()',
                    "champion_wards_control": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[8]/span/span[2]/text()',
                    "champion_cs":   '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[9]/span/span[1]/text()',
                    "champion_cs_per_min": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[9]/span/span[2]/text()',
                    "champion_gold": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[10]/span/span[1]/text()',
                    "champion_gold_per_min": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[10]/span/span[2]/text()',
                    "champion_double": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[11]/span/span/text()',
                    "champion_triple": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[12]/span/span/text()',
                    "champion_quadra": '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[13]/span/span/text()',
                    "champion_penta":  '/html/body/div[5]/div/section[2]/div/table/tbody/tr/td[14]/span/span/text()'
                }

                # Extract data using XPath
                raw_data_stats = {}
                raw_data_champions_solo = {}
                raw_data_champions_flex = {}
                for key, xpath in paths_stats.items():
                    raw_data_stats[key] = tree_stats.xpath(xpath) if tree_stats.xpath(xpath) else [None]

                for key, xpath in paths_champions.items():
                    raw_data_champions_solo[key] = tree_champions_solo.xpath(xpath) if tree_champions_solo.xpath(xpath) else [None]

                for key, xpath in paths_champions.items():
                    raw_data_champions_flex[key] = tree_champions_flex.xpath(xpath) if tree_champions_flex.xpath(xpath) else [None]
                
                # Parse solo queue data
                wins_solo, losses_solo = self._parse_win_loss(raw_data_stats.get("wl_solo", []))
                
                current_rank_solo = RankInfo(
                    rank=raw_data_stats.get("curr_rank_solo", [None])[0],
                    lp=raw_data_stats.get("curr_lp_solo", [None])[0],
                    wins=wins_solo,
                    losses=losses_solo,
                    win_rate=raw_data_stats.get("wr_solo", [None])[0]
                )
                
                best_rank_solo = RankInfo(
                    rank=raw_data_stats.get("best_rank_solo", [None])[0],
                    lp=raw_data_stats.get("best_lp_solo", [None])[0]
                )
                
                previous_seasons_solo = self._parse_previous_seasons(
                    raw_data_stats.get("prev_seasons_solo", None),
                    raw_data_stats.get("prev_ranks_solo", None),
                    raw_data_stats.get("prev_lps_solo", None)
                )
                
                # Parse flex queue data
                wins_flex, losses_flex = self._parse_win_loss(raw_data_stats.get("wl_flex", []))
               

                current_rank_flex = RankInfo(
                    rank=raw_data_stats.get("curr_rank_flex", [None])[0],
                    lp=raw_data_stats.get("curr_lp_flex", [None])[0],
                    wins=wins_flex,
                    losses=losses_flex,
                    win_rate=raw_data_stats.get("wr_flex", [None])[0]
                )
                
                best_rank_flex = RankInfo(
                    rank=raw_data_stats.get("best_rank_flex", [None])[0],
                    lp=raw_data_stats.get("best_lp_flex", [None])[0]
                )
                
                previous_seasons_flex = self._parse_previous_seasons(
                    raw_data_stats.get("prev_seasons_flex", []),
                    raw_data_stats.get("prev_ranks_flex", []),
                    raw_data_stats.get("prev_lps_flex", [])
                )
                
                # --- Champion stats processing ---
                champions_solo = self.parse_champions(raw_data_champions_solo)
                champions_flex = self.parse_champions(raw_data_champions_flex)
                
                return PlayerStats(
                    current_rank_solo=current_rank_solo,
                    best_rank_solo=best_rank_solo,
                    previous_seasons_solo=previous_seasons_solo,
                    current_rank_flex=current_rank_flex,
                    best_rank_flex=best_rank_flex,
                    previous_seasons_flex=previous_seasons_flex,
                    champions_solo=champions_solo,
                    champions_flex=champions_flex
                )
                
        except Exception as e:
            print(f"Error parsing OP.GG data: {e}")
            return None 
