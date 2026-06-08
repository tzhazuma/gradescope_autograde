"""Browser-based fallback for cookie extraction when HTTP login fails."""

from __future__ import annotations

import subprocess
from pathlib import Path


class BrowserCookieExtractor:
    """Extract Gradescope session cookies from browser profiles.

    Provides three extraction strategies in order of reliability:
    1. :meth:`from_playwright_login` — full browser login (most reliable)
    2. :meth:`from_chrome` — read Chrome's cookie DB directly
    3. :meth:`from_macos_keychain` — read a stored cookie from Keychain

    All methods return a cookie string compatible with
    ``GSSession.login_with_cookie()`` (``"name=value; name=value"``),
    or ``None`` on failure.
    """

    @staticmethod
    def from_chrome(domain: str = "gradescope.com") -> str | None:
        """Extract cookies from Chrome's cookie database (macOS).

        Uses Python's sqlite3 to query Chrome's cookie store.
        Requires Full Disk Access permission for Terminal/Python.
        """
        import shutil
        import sqlite3
        import tempfile

        cookie_db = Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"
        if not cookie_db.exists():
            return None

        # Chrome locks the DB, so copy it first
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            shutil.copy2(cookie_db, tmp.name)

        try:
            conn = sqlite3.connect(tmp.name)
            cursor = conn.execute(
                "SELECT name, value FROM cookies WHERE host_key LIKE ?",
                (f"%{domain}%",),
            )
            cookies = "; ".join(f"{name}={value}" for name, value in cursor.fetchall())
            conn.close()
            return cookies or None
        except Exception:
            return None

    @staticmethod
    def from_playwright_login(email: str, password: str) -> str | None:
        """Use Playwright to perform a real browser login and extract cookies.

        This is the most reliable fallback — it mimics real human login.
        Requires the ``browser`` extra (``pip install -e ".[browser]"``).
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            page.goto("https://www.gradescope.com/login")
            page.fill("input[name='session[email]']", email)
            page.fill("input[name='session[password]']", password)
            page.click("input[type='submit']")
            page.wait_for_url("https://www.gradescope.com/**", timeout=10000)

            cookies = page.context.cookies()
            browser.close()

            return "; ".join(f"{c['name']}={c['value']}" for c in cookies)

    @staticmethod
    def from_macos_keychain(service: str = "gradescope") -> dict | None:
        """Extract stored credentials from macOS Keychain."""
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-w"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return {"cookie": result.stdout.strip()}
            return None
        except Exception:
            return None
