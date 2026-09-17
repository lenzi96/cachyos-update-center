"""
Online Issue and Problem Checker for CachyOS and Arch Linux packages.
Discovers breaking changes, manual intervention notices, CVE security advisories,
and AUR package health status prior to updating, allowing automatic exclusion
and deep diagnostic inspection of problematic packages.
"""
import datetime
import html
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


def compare_package_versions(v1: str, v2: str) -> int:
    """
    Compares two Arch/CachyOS package version strings using pyalpm or vercmp.
    Returns:
        < 0 if v1 < v2
        = 0 if v1 == v2
        > 0 if v1 > v2
    """
    if not v1 or not v2:
        return 0
    if v1 == v2:
        return 0
    try:
        import pyalpm
        return pyalpm.vercmp(v1, v2)
    except Exception:
        pass

    try:
        res = subprocess.run(["vercmp", v1, v2], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return int(res.stdout.strip())
    except Exception:
        pass

    # Numeric/alphanumeric fallback
    p1 = [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", v1) if x]
    p2 = [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", v2) if x]
    try:
        return (p1 > p2) - (p1 < p2)
    except Exception:
        return 0


def version_matches_constraint(version: str, op: str, target: str) -> bool:
    """Checks if a given package version satisfies an operator constraint (e.g. >= 1.5.4-3)."""
    cmp = compare_package_versions(version, target)
    if op in (">=", "=>"):
        return cmp >= 0
    elif op == ">":
        return cmp > 0
    elif op in ("<=", "=<"):
        return cmp <= 0
    elif op == "<":
        return cmp < 0
    elif op in ("=", "=="):
        return cmp == 0
    return False


@dataclass
class ProblemReport:
    package_name: str
    severity: str  # 'CRITICAL', 'SECURITY_FIX', 'VULNERABILITY', 'WARNING', 'INFO'
    source: str    # 'Arch Linux News', 'Arch Security Tracker', 'CachyOS Forum', 'AUR Health'
    title: str
    url: str
    reason: str
    description: str = ""
    cves: List[str] = field(default_factory=list)
    advisory_id: Optional[str] = None       # e.g. 'AVG-2881'
    remediation_cmd: Optional[str] = None   # e.g. 'pacman -Syu --overwrite ...'
    is_security_fix: bool = False
    auto_exclude: bool = False
    affected_version: str = ""
    pub_date: str = ""


class OnlineIssueChecker:
    """
    Deep online intelligence engine for CachyOS and Arch Linux packages.
    Inspects:
    1. Arch Linux News RSS (Full text, package lists, version constraints, manual intervention commands)
    2. Arch Linux Security Tracker (AVG / CVE database, detects security fixes and open vulnerabilities)
    3. CachyOS Announcements & Forum RSS (Regressions, kernel notices, driver hotfixes)
    4. AUR Health via RPC API v5 (Flags out-of-date, orphaned packages, maintainer status)
    """

    ARCH_NEWS_FEED = "https://archlinux.org/feeds/news/"
    ARCH_SECURITY_API = "https://security.archlinux.org/issues/all.json"
    CACHY_NEWS_FEED = "https://discuss.cachyos.org/c/announcements/5.rss"
    AUR_RPC_API = "https://aur.archlinux.org/rpc/v5/info"

    _cache_time: float = 0
    _cached_reports: Dict[str, List[ProblemReport]] = {}
    CACHE_TTL_SECONDS = 300  # 5 minutes

    @classmethod
    def check_packages(cls, package_names: List[str]) -> Dict[str, ProblemReport]:
        """
        Backward-compatible check returning a single highest-priority ProblemReport per package.
        """
        detailed = cls.check_packages_detailed(package_names)
        result: Dict[str, ProblemReport] = {}
        for pkg, reports in detailed.items():
            if reports:
                # Prioritize CRITICAL > VULNERABILITY > WARNING > SECURITY_FIX
                priority = {"CRITICAL": 4, "VULNERABILITY": 3, "WARNING": 2, "SECURITY_FIX": 1, "INFO": 0}
                sorted_reps = sorted(reports, key=lambda r: priority.get(r.severity, 0), reverse=True)
                result[pkg] = sorted_reps[0]
        return result

    @classmethod
    def check_packages_detailed(
        cls,
        packages: List[Any],
    ) -> Dict[str, List[ProblemReport]]:
        """
        Comprehensive check returning all ProblemReport objects per package.
        Accepts either a list of package name strings or a list of PackageUpdate objects.
        """
        now = time.time()

        # Build target package metadata lookup: name -> {current_version, new_version, is_aur}
        pkg_map: Dict[str, Dict[str, Any]] = {}
        for p in packages:
            if hasattr(p, "name"):
                pkg_map[p.name.lower()] = {
                    "name": p.name,
                    "current_version": getattr(p, "current_version", ""),
                    "new_version": getattr(p, "new_version", ""),
                    "is_aur": getattr(p, "is_aur", False),
                }
            elif isinstance(p, str):
                pkg_map[p.lower()] = {
                    "name": p,
                    "current_version": "",
                    "new_version": "",
                    "is_aur": False,
                }

        if not pkg_map:
            return {}

        reports: Dict[str, List[ProblemReport]] = {pkg: [] for pkg in pkg_map}

        # 1. Arch Linux News (Full-text, version-aware, command extraction)
        news_reports = cls._check_arch_news(pkg_map)
        for pkg, rep_list in news_reports.items():
            if pkg in reports:
                reports[pkg].extend(rep_list)

        # 2. Arch Linux Security Tracker (AVG / CVE / Security Fixes)
        sec_reports = cls._check_arch_security(pkg_map)
        for pkg, rep_list in sec_reports.items():
            if pkg in reports:
                reports[pkg].extend(rep_list)

        # 3. CachyOS Announcements
        cachy_reports = cls._check_cachy_news(pkg_map)
        for pkg, rep_list in cachy_reports.items():
            if pkg in reports:
                reports[pkg].extend(rep_list)

        # 4. AUR Health Check (for AUR packages)
        aur_pkgs = [meta["name"] for meta in pkg_map.values() if meta["is_aur"]]
        if aur_pkgs:
            aur_reports = cls._check_aur_health(aur_pkgs)
            for pkg, rep_list in aur_reports.items():
                if pkg in reports:
                    reports[pkg].extend(rep_list)

        # Filter out empty report entries
        return {k: v for k, v in reports.items() if v}

    @classmethod
    def fetch_all_issues(cls) -> List[ProblemReport]:
        """
        Fetches all current active security advisories and news warnings across Arch & CachyOS.
        Used by the Updater component card to display the status shield.
        """
        all_issues: List[ProblemReport] = []
        try:
            # Check Arch News items
            req = urllib.request.Request(cls.ARCH_NEWS_FEED, headers={"User-Agent": "CachyOS-Update-Center/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall("./channel/item")[:10]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                if any(k in title.lower() for k in ["manual intervention", "breaking", "critical", "compromised"]):
                    all_issues.append(ProblemReport(
                        package_name="system",
                        severity="CRITICAL",
                        source="Arch Linux News",
                        title=title,
                        url=link,
                        reason=title,
                    ))
        except Exception:
            pass

        try:
            # Check CachyOS News items
            req = urllib.request.Request(cls.CACHY_NEWS_FEED, headers={"User-Agent": "CachyOS-Update-Center/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall("./channel/item")[:5]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                all_issues.append(ProblemReport(
                    package_name="cachyos",
                    severity="INFO",
                    source="CachyOS Forum",
                    title=title,
                    url=link,
                    reason=title,
                ))
        except Exception:
            pass

        return all_issues

    # --------------------------------------------------------------------------
    # Sub-Engine 1: Arch Linux News Full-Text & Version Engine
    # --------------------------------------------------------------------------
    @classmethod
    def _check_arch_news(cls, pkg_map: Dict[str, Dict[str, Any]]) -> Dict[str, List[ProblemReport]]:
        """
        Parses Arch Linux News RSS. Inspects both titles and HTML body descriptions.
        Detects:
        - Manual intervention headlines and notices
        - Explicit package lists (<ul><li>...</li></ul>)
        - Version constraints (e.g. >= 1.5.4-3) evaluated with pyalpm.vercmp
        - Remediation commands (e.g. pacman -Syu --overwrite ...)
        """
        results: Dict[str, List[ProblemReport]] = {pkg: [] for pkg in pkg_map}
        try:
            req = urllib.request.Request(
                cls.ARCH_NEWS_FEED,
                headers={"User-Agent": "CachyOS-Update-Center/1.0"},
            )
            with urllib.request.urlopen(req, timeout=7) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            items = root.findall("./channel/item")

            # Regex patterns
            # Detect title constraints like "waydroid >= 1.5.4-3 update may require manual intervention"
            pat_title_constraint = re.compile(
                r"^([a-z0-9_\.\-]+)\s*(>=|>|<=|<|==|=)\s*([a-z0-9_\.\-:]+)\s*.*(?:manual intervention|eingriff)",
                re.IGNORECASE,
            )
            # General intervention title
            pat_intervention_title = re.compile(
                r"(?:manual intervention|breaking change|manuelle intervention|erfordert eingriff)",
                re.IGNORECASE,
            )
            # Remediation commands in <code> or <pre>
            pat_pacman_cmd = re.compile(r"<code>\s*(pacman\s+-[A-Za-z]+[^<]*)</code>", re.IGNORECASE)

            for item in items[:25]:
                title = html.unescape(item.findtext("title", ""))
                link = item.findtext("link", "")
                desc = html.unescape(item.findtext("description", ""))
                pub_date = item.findtext("pubDate", "")

                is_intervention = bool(pat_intervention_title.search(title)) or ("manual intervention" in desc.lower())

                # Extract potential remediation command
                remediation_cmd = None
                cmd_match = pat_pacman_cmd.search(desc)
                if cmd_match:
                    remediation_cmd = cmd_match.group(1).strip()

                # Clean text description (strip html tags for readable modal presentation)
                clean_desc = re.sub(r"<[^>]+>", " ", desc)
                clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

                # Check 1: Title constraint match (e.g. "kea >= 1:3.0.3-6 update requires manual intervention")
                m_tc = pat_title_constraint.search(title)
                if m_tc:
                    p_name = m_tc.group(1).lower()
                    op = m_tc.group(2)
                    target_ver = m_tc.group(3)

                    if p_name in pkg_map:
                        meta = pkg_map[p_name]
                        new_ver = meta.get("new_version", "")
                        # If we have the target version, check constraint; if version satisfies, alert!
                        is_affected = True
                        if new_ver:
                            is_affected = version_matches_constraint(new_ver, op, target_ver)

                        if is_affected:
                            results[p_name].append(ProblemReport(
                                package_name=meta["name"],
                                severity="CRITICAL",
                                source="Arch Linux News",
                                title=title,
                                url=link,
                                reason=f"Manuelle Intervention erforderlich ({title})",
                                description=clean_desc,
                                remediation_cmd=remediation_cmd,
                                auto_exclude=True,
                                affected_version=f"{op} {target_ver}",
                                pub_date=pub_date,
                            ))

                # Check 2: Lists of packages inside description (e.g. .NET packages, dovecot modules)
                # Matches <li>packagename</li>
                li_packages = [
                    p.lower().strip()
                    for p in re.findall(r"<li>\s*<code>?([a-z0-9_\.\-]+)</code>?\s*</li>", desc, re.IGNORECASE)
                ]
                for li_pkg in li_packages:
                    if li_pkg in pkg_map:
                        meta = pkg_map[li_pkg]
                        # Avoid duplicates for same news article
                        if not any(r.url == link for r in results[li_pkg]):
                            results[li_pkg].append(ProblemReport(
                                package_name=meta["name"],
                                severity="CRITICAL" if is_intervention else "WARNING",
                                source="Arch Linux News",
                                title=title,
                                url=link,
                                reason="Im Arch Linux News-Artikel als betroffenes Paket aufgeführt",
                                description=clean_desc,
                                remediation_cmd=remediation_cmd,
                                auto_exclude=is_intervention,
                                pub_date=pub_date,
                            ))

                # Check 3: Check each candidate package against critical headlines with word boundaries
                if is_intervention:
                    for p_name, meta in pkg_map.items():
                        if re.search(rf"\b{re.escape(p_name)}\b", title, re.IGNORECASE):
                            if not any(r.url == link for r in results[p_name]):
                                results[p_name].append(ProblemReport(
                                    package_name=meta["name"],
                                    severity="CRITICAL",
                                    source="Arch Linux News",
                                    title=title,
                                    url=link,
                                    reason=f"Manuelle Intervention erforderlich laut Arch News",
                                    description=clean_desc,
                                    remediation_cmd=remediation_cmd,
                                    auto_exclude=True,
                                    pub_date=pub_date,
                                ))
        except Exception:
            pass

        return results

    # --------------------------------------------------------------------------
    # Sub-Engine 2: Arch Linux Security Tracker (CVEs & Security Fixes)
    # --------------------------------------------------------------------------
    @classmethod
    def _check_arch_security(cls, pkg_map: Dict[str, Dict[str, Any]]) -> Dict[str, List[ProblemReport]]:
        """
        Queries official Arch Linux Security Tracker (security.archlinux.org).
        Identifies:
        - Security fixes (Package update resolves open CVEs: installed < fixed <= new) -> Highly Recommended!
        - Open vulnerabilities (Target package version is currently tracked as vulnerable)
        """
        results: Dict[str, List[ProblemReport]] = {pkg: [] for pkg in pkg_map}
        try:
            req = urllib.request.Request(
                cls.ARCH_SECURITY_API,
                headers={
                    "User-Agent": "CachyOS-Update-Center/1.0",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=9) as resp:
                data = json.loads(resp.read().decode())

            for item in data:
                avg_name = item.get("name", "")
                packages = [p.lower() for p in item.get("packages", [])]
                status = item.get("status", "")        # "Fixed", "Vulnerable", "Not affected"
                severity = item.get("severity", "Medium").upper()
                cves = item.get("issues", [])
                fixed_version = item.get("fixed")
                avg_url = f"https://security.archlinux.org/{avg_name}"

                for p_name in packages:
                    if p_name in pkg_map:
                        meta = pkg_map[p_name]
                        curr_ver = meta.get("current_version", "")
                        new_ver = meta.get("new_version", "")

                        # Scenario A: Security Fix Update!
                        # The user has an older version that is vulnerable, and the new version fixes it!
                        if fixed_version and curr_ver and new_ver:
                            is_curr_vulnerable = compare_package_versions(curr_ver, fixed_version) < 0
                            is_new_fixed = compare_package_versions(new_ver, fixed_version) >= 0

                            if is_curr_vulnerable and is_new_fixed:
                                cve_summary = ", ".join(cves[:3])
                                if len(cves) > 3:
                                    cve_summary += f" (+{len(cves) - 3} weitere)"

                                results[p_name].append(ProblemReport(
                                    package_name=meta["name"],
                                    severity="SECURITY_FIX",
                                    source="Arch Security Tracker",
                                    title=f"Sicherheits-Fix: {avg_name} ({len(cves)} CVEs)",
                                    url=avg_url,
                                    reason=f"Behebt {len(cves)} Schwachstelle(n) [{cve_summary}] ab v{fixed_version}",
                                    description=(
                                        f"Dieses Update schließt bekannte Sicherheitslücken ({avg_name}):\n"
                                        f"• Betroffene CVEs: {', '.join(cves)}\n"
                                        f"• Schweregrad laut Arch Security: {severity}\n"
                                        f"• Behoben in Version: {fixed_version}\n"
                                        f"Aktualisierung wird dringend empfohlen!"
                                    ),
                                    cves=cves,
                                    advisory_id=avg_name,
                                    is_security_fix=True,
                                    auto_exclude=False,
                                    affected_version=f"< {fixed_version}",
                                ))
                                continue

                        # Scenario B: Target version is still known to be Vulnerable
                        if status.lower() == "vulnerable":
                            # Check if the new version is still lower than fixed
                            is_still_vulnerable = True
                            if fixed_version and new_ver:
                                is_still_vulnerable = compare_package_versions(new_ver, fixed_version) < 0

                            if is_still_vulnerable:
                                cve_summary = ", ".join(cves[:3])
                                results[p_name].append(ProblemReport(
                                    package_name=meta["name"],
                                    severity="VULNERABILITY",
                                    source="Arch Security Tracker",
                                    title=f"Bekannte Sicherheitslücke: {avg_name}",
                                    url=avg_url,
                                    reason=f"Bekannte Sicherheitslücke ({cve_summary}) im Zielpaket vorhanden",
                                    description=(
                                        f"Für dieses Paket ist eine aktive Sicherheitswarnung verzeichnet ({avg_name}):\n"
                                        f"• CVEs: {', '.join(cves)}\n"
                                        f"• Schweregrad: {severity}\n"
                                        f"• Status: {status}"
                                    ),
                                    cves=cves,
                                    advisory_id=avg_name,
                                    is_security_fix=False,
                                    auto_exclude=False,
                                ))
        except Exception:
            pass

        return results

    # --------------------------------------------------------------------------
    # Sub-Engine 3: CachyOS Announcements & Forum Engine
    # --------------------------------------------------------------------------
    @classmethod
    def _check_cachy_news(cls, pkg_map: Dict[str, Dict[str, Any]]) -> Dict[str, List[ProblemReport]]:
        """
        Parses CachyOS announcements RSS feed for known driver issues, kernel regressions,
        or hotfixes.
        """
        results: Dict[str, List[ProblemReport]] = {pkg: [] for pkg in pkg_map}
        try:
            req = urllib.request.Request(
                cls.CACHY_NEWS_FEED,
                headers={"User-Agent": "CachyOS-Update-Center/1.0"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            items = root.findall("./channel/item")

            crit_keywords = ["breaking", "regression", "broken", "issue", "warning", "panic", "hotfix"]

            for item in items[:15]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                desc = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")

                is_problem_title = any(k in title.lower() for k in ["issue", "regression", "warning", "broken", "hotfix", "problem", "panic"])
                for p_name, meta in pkg_map.items():
                    matches = list(re.finditer(rf"\b{re.escape(p_name)}\b", combined, re.IGNORECASE))
                    if not matches:
                        continue

                    is_context_issue = False
                    if is_problem_title:
                        is_context_issue = True
                    else:
                        for m in matches:
                            start = max(0, m.start() - 100)
                            end = min(len(combined), m.end() + 100)
                            context = combined[start:end]
                            if any(k in context for k in ["issue", "problem", "broken", "regression", "fails", "fail", "crash", "panic", "bug", "revert"]):
                                is_context_issue = True
                                break

                    if is_context_issue:
                        clean_desc = re.sub(r"<[^>]+>", " ", desc)
                        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
                        results[p_name].append(ProblemReport(
                            package_name=meta["name"],
                            severity="WARNING",
                            source="CachyOS Forum",
                            title=title,
                            url=link,
                            reason=f"Thematisiert in CachyOS Ankündigung: {title}",
                            description=clean_desc,
                            auto_exclude=False,
                            pub_date=pub_date,
                        ))
        except Exception:
            pass

        return results

    # --------------------------------------------------------------------------
    # Sub-Engine 4: AUR Package Health & Maintenance Status
    # --------------------------------------------------------------------------
    @classmethod
    def _check_aur_health(cls, aur_package_names: List[str]) -> Dict[str, List[ProblemReport]]:
        """
        Queries AUR RPC API v5 to check for:
        - Orphaned packages (Maintainer is None -> unmaintained, risk of build failures)
        - Flagged out-of-date packages (OutOfDate timestamp set by community)
        """
        results: Dict[str, List[ProblemReport]] = {pkg.lower(): [] for pkg in aur_package_names}
        if not aur_package_names:
            return results

        try:
            # Query in batches of 30 to stay within query string limits
            batch_size = 30
            for i in range(0, len(aur_package_names), batch_size):
                batch = aur_package_names[i:i + batch_size]
                args = "&".join(f"arg[]={urllib.parse.quote(p)}" for p in batch)
                url = f"{cls.AUR_RPC_API}?{args}"

                req = urllib.request.Request(url, headers={"User-Agent": "CachyOS-Update-Center/1.0"})
                with urllib.request.urlopen(req, timeout=7) as resp:
                    data = json.loads(resp.read().decode())

                for item in data.get("results", []):
                    name = item.get("Name", "")
                    p_lower = name.lower()
                    maintainer = item.get("Maintainer")
                    out_of_date = item.get("OutOfDate")
                    aur_url = f"https://aur.archlinux.org/packages/{name}"

                    # 1. Orphan check
                    if maintainer is None:
                        results[p_lower].append(ProblemReport(
                            package_name=name,
                            severity="WARNING",
                            source="AUR Health",
                            title="AUR-Paket ist verwaist (Kein Maintainer)",
                            url=aur_url,
                            reason="Paket hat im AUR keinen Maintainer. Mögliche Build- oder Abhängigkeitsfehler.",
                            description=(
                                f"Das AUR-Paket '{name}' ist verwaist (Orphaned).\n"
                                f"Es gibt keinen zuständigen Betreuer mehr im Arch User Repository.\n"
                                f"Prüfe vor dem Bauen, ob das Paket noch aktuell ist oder durch eine offizielle Alternative ersetzt werden kann."
                            ),
                            auto_exclude=False,
                        ))

                    # 2. Out-of-date check
                    if out_of_date:
                        try:
                            ood_date = datetime.datetime.fromtimestamp(out_of_date).strftime("%d.%m.%Y")
                        except Exception:
                            ood_date = str(out_of_date)

                        results[p_lower].append(ProblemReport(
                            package_name=name,
                            severity="WARNING",
                            source="AUR Health",
                            title=f"AUR-Paket als veraltet gemeldet ({ood_date})",
                            url=aur_url,
                            reason=f"In der AUR-Community seit {ood_date} als veraltet markiert.",
                            description=(
                                f"Das AUR-Paket '{name}' wurde am {ood_date} als 'Out-of-date' gemeldet.\n"
                                f"Der Upstream-Quellcode hat möglicherweise neuere Versionen, die noch nicht im PKGBUILD gepflegt wurden."
                            ),
                            auto_exclude=False,
                        ))
        except Exception:
            pass

        return results
