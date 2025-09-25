"""Lolalytics.сom parser implementation."""
import logging
from playwright.async_api import Page
from typing import Optional, Callable, Any
from backend.workers.parser.schemas.champion import *
from backend.workers.parser.helpers.playwright_browser import PlaywrightBrowser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

class LolalyticsParser:
    """Parser implementation for Lolalytics.сom website using Playwright."""

    def __init__(self):
        """Initialize the parser instance."""
        self.browser = PlaywrightBrowser()
        self.page = None

    async def setup(self):
        await self.browser.setup()

    async def close(self):
        await self.browser.close()

    async def parse_element(self, element, schema_cls, fields: dict[str, tuple[str, str, Optional[Callable[[Any], Any]]]]) -> Optional[Any]:
        """Parses a given HTML element into an instance of the specified schema class"""
        try:
            values = {}

            for field_name, (selector, value_type, transform) in fields.items():
                if not selector: value = transform(None) if transform else None
                elif value_type == "text": value = await self.browser.extract_text(selector, parent=element)
                elif value_type == "number": value = await self.browser.extract_number(selector, parent=element)
                else: raise ValueError(f"Unsupported value_type: {value_type}")

                if transform: value = transform(value)
                values[field_name] = value

            return schema_cls(**values)

        except Exception as e:
            logging.warning(f"Failed to parse element into {schema_cls.__name__}: {e}")
            return None

    async def parse_meta_stats(self, tier: str) -> Optional[MetaStats]:
        """Parse champion stats from Lolalytics."""
        url = f"https://lolalytics.com/lol/tierlist/?tier={tier.lower()}"

        fields = {
            "name": ('div:nth-of-type(3)', 'text', None),
            "tier": ('div:nth-of-type(4)', 'text', None),
            "lane": ('div:nth-of-type(5)', 'text', None),
            "win": ('div:nth-child(6) > div > span:nth-child(1)', 'number', None),
            "pick": ('div:nth-of-type(7)', 'number', None),
            "ban": ('div:nth-of-type(8)', 'number', None),
            "games": ('div:nth-of-type(10)', 'number', None),
        }

        try:
            self.page = await self.browser.new_page()
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.browser.auto_scroll()

            rows = await self.page.query_selector_all('body > main > div:nth-of-type(6) > div')
            if not rows: logging.error("Row selector not found")

            champions = []

            for row in rows[2:]:
                stat = await self.parse_element(row, MetaChampion, fields)
                if stat: champions.append(stat)

            return MetaStats(champions=champions)

        except Exception as e:
            logging.error(f"Error parsing meta stats: {e}")
            return None
        finally:
            if self.page:
                await self.page.close()

    async def parse_counters_stats(self, champion: str, tier: str) -> Optional[ChampionCounters]:
        """Parse counter stats for specific champion stats from Lolalytics."""
        url = f'https://lolalytics.com/lol/{champion.lower()}/counters/?tier={tier.lower()}'

        fields = {
            "champion": ('div > a > div > div:nth-of-type(1)', 'text', None),
            "wr_against": ('div > a > div > div:nth-of-type(2)', 'number', None),
            "delta_1": ('div > a > div > div:nth-of-type(3) > span:nth-of-type(1)', 'text', lambda s: float(s[2:])),
            "delta_2": ('div > a > div > div:nth-of-type(3) > span:nth-of-type(2)', 'text', lambda s: float(s[2:])),
            "avg_wr_against": ('div > a > div > div:nth-of-type(4)', 'number', None),
            "games": ('div > a > div > div:nth-of-type(5)', 'number', None),
        }

        try:
            self.page = await self.browser.new_page()
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

            cards = await self.page.query_selector_all('div.flex.flex-wrap.justify-between > span')
            if not cards: logging.error("Card selector not found")

            champion = champion
            counters = []

            for card in cards:
                stat = await self.parse_element(card, CounterCard, fields)
                if stat: counters.append(stat)

            return ChampionCounters(champion=champion, counters=counters)

        except Exception as e:
            logging.error(f"Error parsing counter stats: {e}")
            return None
        finally:
            if self.page:
                await self.page.close()

    async def parse_common_section(self, page: Page, flag: str, counter_fields: dict, parse_element_func: Callable) -> list[dict[str, list]]:
        """Parses a scrolling section of champion cards (e.g., common matchups or teammates) from the page."""
        await self.page.wait_for_selector('div.cursor-grab', timeout=10000)
        scroll_containers = await self.page.query_selector_all('div.cursor-grab')
        positions = await self.page.query_selector_all('body > main > div.m-auto > div > div > div > img')

        common_data = []

        for i in range(len(positions)):
            curr_lane = await positions[i].get_attribute("alt")
            seen_champions = set()
            counters = []

            while True:
                await scroll_containers[i].evaluate('(el) => el.scrollLeft += (el.clientWidth - 100)')
                cards = await self.page.query_selector_all(f'div.m-auto.w-\[98\%\] > div.w-\[100\%\] > div:nth-child({2 + i}) > div.cursor-grab > div > div')

                for card in cards:
                    link = await (await card.query_selector("a")).get_attribute("href")
                    champ = None
                    if flag == 'teammates': champ = link.split("/")[2].capitalize()
                    elif flag == 'matchup': champ = link.split("/")[4].capitalize()

                    if champ in seen_champions: continue

                    seen_champions.add(champ)
                    counter_fields['champion'] = (None, None, lambda _: champ)
                    parsed = await parse_element_func(card, CounterCardV2, counter_fields)
                    counters.append(parsed)

                if await page.evaluate('(el) => el.scrollLeft + el.clientWidth >= el.scrollWidth - 5', scroll_containers[i]): break

            common_data.append({curr_lane: counters})

        return common_data

    async def parse_champion_build(self, champion: str, tier: str) -> Optional[ChampionStats]:
        """Parses detailed champion build statistics from Lolalytics."""
        url = f'https://lolalytics.com/lol/{champion.lower()}/build/?tier={tier.lower()}'

        counter_fields = {
            "wr": ('div.my-1:nth-child(2)', 'text', None),
            "delta_1": ('div.my-1:nth-child(3)', 'text', None),
            "delta_2": ('div.my-1:nth-child(4)', 'text', None),
            "pr": ('div.my-1:nth-child(5)', 'text', None),
            "games": ('div.text-\\[9px\\].text-\\[\\#bbb\\]', 'text', None)
        }

        try:
            self.page = await self.browser.new_page()
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.browser.auto_scroll(max_scrolls=5)

            common_matchup = await self.parse_common_section(page=self.page, flag='matchup', counter_fields=counter_fields, parse_element_func=self.parse_element)
            await self.page.wait_for_selector('body > main > div.m-auto > div > div:nth-child(2) > div.cursor-grab.overflow-y-hidden.overflow-x-scroll > div > div:nth-child(1) > a', timeout=10000)
            old_check = await (await self.page.query_selector('body > main > div.m-auto > div > div:nth-child(2) > div.cursor-grab.overflow-y-hidden.overflow-x-scroll > div > div:nth-child(1) > a')).text_content()

            await self.page.click("body > main > div > div > div:nth-child(1) > div:nth-child(2) > div.flex.flex-auto.justify-items-stretch > div:nth-child(1)")

            await self.page.wait_for_function(
                """(args) => {
                    const el = document.querySelector(args.selector);
                    return el && el.textContent.trim() !== args.oldCheck;
                }""",
                arg={
                    "selector": "body > main > div.m-auto > div > div:nth-child(2) > div.cursor-grab.overflow-y-hidden.overflow-x-scroll > div > div:nth-child(1) > a",
                    "oldCheck": old_check.strip() if old_check else ""
                },
                timeout=10000
            )

            common_teammates = await self.parse_common_section(page=self.page, flag = 'teammates', counter_fields=counter_fields, parse_element_func=self.parse_element)

            rows = await self.page.query_selector_all('div.mb-2.break-inside-avoid > table > tbody > tr')
            if not rows: logging.error("Objective selector not found")

            objectives = {}

            for row in rows:
                tds = await row.query_selector_all("td")

                name = (await tds[0].text_content()).lower()
                secure_percent = await tds[1].text_content()
                secure_win_percent = await tds[2].text_content()
                yield_percent = await tds[3].text_content() if len(tds) > 3 else None
                yield_win_percent = await tds[4].text_content() if len(tds) > 4 else None

                objectives[name] = ObjectiveInfo(secure_percent=secure_percent, secure_win_percent=secure_win_percent, yield_percent=yield_percent, yield_win_percent=yield_win_percent)

            return ChampionStats(champion=champion, objectives=objectives, common_matchup=common_matchup, common_teammates=common_teammates)

        except Exception as e:
            logging.error(f"Error parsing build stats: {e}")
            return None
        finally:
            if self.page:
                await self.page.close()