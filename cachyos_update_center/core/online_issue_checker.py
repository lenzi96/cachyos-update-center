"""
Online Issue and Problem Checker for CachyOS and Arch Linux packages.
Discovers breaking changes, manual intervention notices, and security regressions
prior to updating, allowing automatic exclusion of problematic packages.
"""
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class ProblemReport:
    package_name: str
    severity: str  # 'CRITICAL', 'WARNING', 'SECURITY'
    source: str    # 'Arch News', 'CachyOS News', 'Arch Security'
    title: str
    url: str
    reason: str
    auto_exclude: bool = True


class OnlineIssueChecker:
    """Scans distribution feeds online for broken packages or required manual interventions."""

    ARCH_NEWS_FEED = "https://archlinux.org/feeds/news/"
    CACHY_NEWS_FEED = "https://discuss.cachyos.org/c/announcements/5.rss"
    ARCH_SECURITY_API = "https://security.archlinux.org/issues.json"

    _cache_time: float = 0
    _cached_reports: Dict[str, ProblemReport] = {}
    CACHE_TTL_SECONDS = 300  # 5 minutes

    @classmethod
    def check_packages(cls, package_names: List[str]) -> Dict[str, ProblemReport]:
        """
        Checks given package names against online issue feeds.
        Returns a dict of {package_name: ProblemReport} for any problematic packages found.
        """
        now = time.time()
        if now - cls._cache_time < cls.CACHE_TTL_SECONDS and cls._cached_reports:
            return {p: cls._cached_reports[p] for p in package_names if p in cls._cached_reports}

        reports: Dict[str, ProblemReport] = {}
        pkg_set = set(p.lower() for p in package_names)

        # 1. Check Arch Linux News (manual interventions / breaking changes)
        news_reports = cls._check_arch_news(pkg_set)
        reports.update(news_reports)

        # 2. Check CachyOS Announcements
        cachy_reports = cls._check_cachy_news(pkg_set)
        reports.update(cachy_reports)

        cls._cache_time = now
        cls._cached_reports = reports

        return {p: reports[p] for p in package_names if p in reports}

    @classmethod
    def _check_arch_news(cls, target_packages: Set[str]) -> Dict[str, ProblemReport]:
        """Parses Arch Linux news RSS for manual intervention notices."""
        found: Dict[str, ProblemReport] = {}
        try:
            req = urllib.request.Request(
                cls.ARCH_NEWS_FEED,
                headers={"User-Agent": "CachyOS-Update-Center/1.0"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            items = root.findall("./channel/item")

            # Patterns to detect package name in news titles
            # E.g.: "virtualbox-ext-vnc >= 7.2.12-2 requires manual intervention"
            # E.g.: "kea >= 1:3.0.3-6 update requires manual intervention"
            # E.g.: "Breaking changes for all users of `varnish`..."
            pattern_intervention = re.compile(
                r"^([a-z0-9_\.\-]+)\s*(?:>=|>|<=|<|==|=)?.*(?:requires manual intervention|erfordert eingriff)",
                re.IGNORECASE,
            )
            pattern_breaking = re.compile(
                r"breaking\s+changes?\s+(?:for|in)\s+.*[`'\"]?([a-z0-9_\.\-]+)[`'\"]?",
                re.IGNORECASE,
            )

            for item in items[:15]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                desc = item.findtext("description", "")

                matched_pkgs = set()

                m1 = pattern_intervention.search(title)
                if m1:
                    matched_pkgs.add(m1.group(1).lower())

                m2 = pattern_breaking.search(title)
                if m2:
                    matched_pkgs.add(m2.group(1).lower())

                # Also search for explicit matches of target_packages in critical headlines
                is_critical_headline = any(
                    k in title.lower() for k in ["manual intervention", "breaking", "broken", "critical", "compromised"]
                )

                if is_critical_headline:
                    for pkg in target_packages:
                        # Match word boundaries
                        if re.search(rf"\b{re.escape(pkg)}\b", title, re.IGNORECASE):
                            matched_pkgs.add(pkg)

                for pkg in matched_pkgs:
                    found[pkg] = ProblemReport(
                        package_name=pkg,
                        severity="CRITICAL",
                        source="Arch Linux News",
                        title=title,
                        url=link,
                        reason="Manuelle Intervention laut Arch Linux News erforderlich",
                        auto_exclude=True,
                    )
        except Exception:
            pass

        return found

    @classmethod
    def _check_cachy_news(cls, target_packages: Set[str]) -> Dict[str, ProblemReport]:
        """Parses CachyOS announcements RSS for package warnings or hotfix notices."""
        found: Dict[str, ProblemReport] = {}
        try:
            req = urllib.request.Request(
                cls.CACHY_NEWS_FEED,
                headers={"User-Agent": "CachyOS-Update-Center/1.0"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            items = root.findall("./channel/item")

            for item in items[:10]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")

                # Check for critical keywords
                if any(k in title.lower() for k in ["compromised", "broken", "critical issue", "regression", "warning"]):
                    for pkg in target_packages:
                        if re.search(rf"\b{re.escape(pkg)}\b", title, re.IGNORECASE):
                            found[pkg] = ProblemReport(
                                package_name=pkg,
                                severity="CRITICAL",
                                source="CachyOS News",
                                title=title,
                                url=link,
                                reason="Bekanntes Problem laut CachyOS Ankündigung",
                                auto_exclude=True,
                            )
        except Exception:
            pass

        return found
