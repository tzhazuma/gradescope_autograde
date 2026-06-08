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

    @staticmethod
    def from_interactive_browser(timeout: int = 120) -> str | None:
        """Open browser for manual Gradescope login, auto-capture cookies on success.

        Launches a visible Chromium browser window to gradescope.com/login.
        The user logs in manually. Once login succeeds (dashboard loads),
        cookies are automatically extracted and the browser closes.

        Args:
            timeout: Maximum seconds to wait for the user to complete login.

        Returns:
            Cookie string compatible with ``GSSession.login_with_cookie()``,
            or ``None`` if login timed out or failed.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        print("\n🔐 Opening browser for Gradescope login...")
        print("   Please log in with your credentials in the browser window.")
        print(f"   Waiting up to {timeout}s for login to complete...\n")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            try:
                page.goto("https://www.gradescope.com/login", wait_until="domcontentloaded")
                print("   Browser opened. Complete your login...")

                page.wait_for_url(
                    "https://www.gradescope.com/**",
                    timeout=timeout * 1000,
                )

                current_url = page.url
                if "login" in current_url.lower():
                    print("   ⚠️  Still on login page. Login may have failed.")
                    return None

                cookies = context.cookies()
                cookie_string = "; ".join(
                    f"{c['name']}={c['value']}"
                    for c in cookies
                    if "gradescope" in c.get("domain", "")
                )

                if not cookie_string:
                    print("   ⚠️  No Gradescope cookies found.")
                    return None

                session_cookie = next(
                    (c for c in cookies if c["name"] == "_gradescope_session"),
                    None,
                )
                if session_cookie:
                    cookie_string = f"_gradescope_session={session_cookie['value']}"

                print(f"   ✅ Login successful! Session cookie captured.")
                return cookie_string

            except Exception as e:
                error_msg = str(e)
                if "Timeout" in error_msg:
                    print(f"\n   ⏰ Login timed out after {timeout}s.")
                else:
                    print(f"\n   ❌ Error: {e}")
                return None

            finally:
                browser.close()
