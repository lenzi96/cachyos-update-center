"""
News and manual intervention alert checker for Arch Linux and CachyOS.
"""
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List


@dataclass
class NewsItem:
    title: str
    link: str
    pub_date: str
    summary: str
    is_critical: bool = False


class NewsChecker:
    """Fetches latest distribution announcements to warn of manual interventions."""

    FEED_URL = "https://archlinux.org/feeds/news/"

    @classmethod
    def fetch_latest_news(cls, max_items: int = 5) -> List[NewsItem]:
        """Fetches and parses Arch Linux news RSS feed."""
        items: List[NewsItem] = []
        try:
            req = urllib.request.Request(
                cls.FEED_URL,
                headers={"User-Agent": "CachyOS-Update-Center/1.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            channel = root.find("channel")
            if channel is None:
                return items

            for item in channel.findall("item")[:max_items]:
                title = item.findtext("title", "Kein Titel").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                desc = item.findtext("description", "").strip()

                # Clean basic HTML tags from description
                desc_clean = desc.replace("<p>", "").replace("</p>", "\n").replace("<br>", "\n").strip()
                if len(desc_clean) > 250:
                    desc_clean = desc_clean[:247] + "..."

                # Detect if manual intervention is required
                critical_keywords = ["manual intervention", "erfordert eingriff", "action required", "wichtig"]
                is_crit = any(k in title.lower() or k in desc.lower() for k in critical_keywords)

                items.append(
                    NewsItem(
                        title=title,
                        link=link,
                        pub_date=pub_date,
                        summary=desc_clean,
                        is_critical=is_crit,
                    )
                )
        except Exception:
            pass

        return items
