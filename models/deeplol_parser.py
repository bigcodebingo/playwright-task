"""Deeplol.gg parser implementation."""
import logging
from typing import Optional, List
from backend.workers.parser.schemas.player import PlayerStats, RankInfo, SeasonStats, ChampionStats
from backend.workers.parser.helpers.playwright_browser import PlaywrightBrowser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

class DeepLOLParser:
    """Parser implementation for DeepLOL.gg website using Playwright."""

    def __init__(self):
        """Initialize the parser instance."""
        self.browser = PlaywrightBrowser()
        self.page = None

    async def setup(self):
        await self.browser.setup()

    async def close(self):
        await self.browser.close()

    def normalize_url(self, url: str) -> tuple[str, str]:
        """Normalize DeepLOL.gg URL and generate champions URL."""
        url = url.rstrip('/')
        if not url.startswith('https://'):
            url = f'https://{url}'
        champions_url = f"{url}/champions"

        return url, champions_url

    async def parse_wins_losses(self, selector: str) -> tuple[Optional[int], Optional[int]]:
        """Parses the number of wins and losses from the 'XXXW YYYL' format element'"""
        text = None
        try:
            text = (await self.browser.extract_text(selector) or "").strip()
            if not text:
                return None, None

            wins, losses = map(lambda s: int(s[:-1]), text.split())
            return wins, losses

        except (ValueError, AttributeError, IndexError) as e:
            logging.debug(f"Failed to parse W/L: {text}. Error: {e}")
            return None, None


    async def _parse_champion_data(self, page, mode: str) -> Optional[List[ChampionStats]]:
        """Parse champion stats from current page."""
        try:
            TAB_SELECTORS = {
                'solo': 'div.sc-fnAgPf.iLhZbD > div.sc-bvcFEq.kEzVtI',
                'flex': 'div.sc-fnAgPf.bLYGgq > div.sc-bvcFEq.kEzVtI'
            }

            champions = []
            tab = await page.wait_for_selector(TAB_SELECTORS[mode], timeout=10000, state="visible")
            await tab.click()

            await page.wait_for_selector('tr.close', timeout=10000)
            rows = await page.query_selector_all('tr.close')

            for row in rows[1:]:
                position = await  self.browser.extract_text('td:nth-child(1) > span.normal', parent=row)
                champion = await self.browser.extract_text('span.sc-JkixQ.eZQvao.champName', parent=row)
                champion_wins = await self.browser.extract_number('span.win', parent=row)
                champion_losses = await self.browser.extract_number('span.lose', parent=row)
                champion_wr = await self.browser.extract_number('div.winrate', parent=row)
                champion_kda = await self.browser.extract_text('div.kda > p', parent=row)
                champion_kda_ratio = await self.browser.extract_text('span.kda_color', parent=row)
                champion_dmg_per_min = await self.browser.extract_number('div.sc-jFkmsu.dZiPNg',parent = row)
                champion_dmg_share_ratio = await self.browser.extract_number('td:nth-child(10) > span.normal',parent = row)
                champion_cs_per_min = await self.browser.extract_number('td:nth-child(8) > span.normal', parent=row)

                champions.append(ChampionStats(
                    position=position,
                    champion=champion,
                    champion_wins=champion_wins,
                    champion_losses=champion_losses,
                    champion_wr=champion_wr,
                    champion_kda=champion_kda,
                    champion_kda_ratio=champion_kda_ratio,
                    champion_dmg_per_min=champion_dmg_per_min,
                    champion_dmg_share_ratio=champion_dmg_share_ratio,
                    champion_cs_per_min=champion_cs_per_min
                ))

            return champions if champions else None

        except Exception as e:
            logging.error(f"Error parsing champion data: {e}")
            return None


    def get_selectors_for_mode(self, mode: str) -> dict:
        """Generates CSS selectors for specified ranked queue type (solo/flex)."""
        position = 1 if mode.lower() == "solo" else 2

        return {
            'rank': f'div.sc-iUKqMP.iKKtPF > div:nth-child({position}) span.tier_color',
            'lp': f'div.sc-iUKqMP.iKKtPF > div:nth-child({position}) span.sc-jTYOmA.kvFqjw',
            'wl': f'div.sc-iUKqMP.iKKtPF > div:nth-child({position}) span.sc-lvMlV.cFAxaZ',
            'wr': f'div.sc-iUKqMP.iKKtPF > div:nth-child({position}) div.sc-jcFjpl.dhxdJc span.sc-lvMlV.cFAxaZ'
        }

    async def _parse_main_page(self, url: str):
        """Parse main profile page."""
        await self.page.goto(url, wait_until="domcontentloaded", timeout=10000)
        await self.page.wait_for_selector('span.sc-kTwdzw.iERSzQ', timeout=10000)

        if await self.page.query_selector('div#anti-bot'):
            raise Exception("Anti-bot protection detected")

        SOLO_SELECTORS = self.get_selectors_for_mode("solo")
        FLEX_SELECTORS = self.get_selectors_for_mode("flex")

        self.nickname = await self.browser.extract_text('span.sc-kTwdzw.iERSzQ')
        self.current_rank_solo = await self._parse_rank_section(**SOLO_SELECTORS)
        self.current_rank_flex = await self._parse_rank_section(**FLEX_SELECTORS)


    async def _parse_champions_page(self, url: str) -> Optional[List[ChampionStats]]:
        """Parse champions tab in new page context."""
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=10000)
            await self.page.wait_for_selector('tr.close', timeout=10000)

            self.champions_solo = await self._parse_champion_data(self.page, mode="solo")
            self.champions_flex = await self._parse_champion_data(self.page, mode="flex")

        except Exception as e:
            logging.error(f"Error parsing champions page: {e}")
            return None


    async def _parse_rank_section(self, rank: str, lp: str, wl: str, wr: str) -> Optional[RankInfo]:
        """Helper method to parse rank information from a section."""
        try:
            rank = await self.browser.extract_text(rank)
            lp = await self.browser.extract_number(lp)
            wins, losses = await self.parse_wins_losses(wl)
            win_rate = await self.browser.extract_number(wr)

            return RankInfo(
                rank=rank,
                lp=lp,
                wins=wins,
                losses=losses,
                win_rate=win_rate
            )

        except Exception as e:
            logging.warning(f"Failed to parse rank section: {e}")
            return None


    async def parse_player_stats(self, url: str) -> Optional[PlayerStats]:
        """Parse player stats from main page and champion stats from champions tab."""
        try:
            base_url, champions_url = self.normalize_url(url)
            self.page = await self.browser.new_page()

            await self._parse_main_page(base_url)
            await self._parse_champions_page(champions_url)

            return PlayerStats(
                nickname=self.nickname,
                current_rank_solo=self.current_rank_solo,
                current_rank_flex=self.current_rank_flex,
                champions_solo=self.champions_solo,
                champions_flex=self.champions_flex
            )

        except Exception as e:
            logging.error(f"Error parsing player stats: {e}")
            return None
        finally:
            if self.page:
                await self.page.close()