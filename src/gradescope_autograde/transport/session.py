import time
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from .exceptions import AuthenticationError


@dataclass
class GSSession:
    """Authenticated HTTP session for Gradescope.

    Handles login, cookie persistence, and rate-limited requests.
    """

    base_url: str = "https://www.gradescope.com"
    request_delay: float = 1.0
    max_retries: int = 3

    _session: requests.Session = field(default_factory=requests.Session, init=False)
    _authenticated: bool = field(default=False, init=False)

    def login(self, email: str, password: str) -> bool:
        login_page = self._session.get(f"{self.base_url}/login")
        login_page.raise_for_status()

        soup = BeautifulSoup(login_page.text, "html.parser")
        token_input = soup.find("input", {"name": "authenticity_token"})
        if token_input is None or not token_input.get("value"):
            raise AuthenticationError(
                "Could not extract CSRF authenticity_token from Gradescope login page"
            )

        csrf_token = token_input["value"]
        time.sleep(self.request_delay)

        response = self._session.post(
            f"{self.base_url}/login",
            data={
                "session[email]": email,
                "session[password]": password,
                "authenticity_token": csrf_token,
                "commit": "Sign In",
            },
            allow_redirects=False,
        )
        self._authenticated = response.status_code == 302
        return self._authenticated

    def login_with_cookie(self, cookie_string: str) -> None:
        for part in cookie_string.split("; "):
            if "=" in part:
                name, value = part.split("=", 1)
                self._session.cookies.set(name, value)
        self._authenticated = True

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def get(self, path: str, **kwargs) -> requests.Response:
        response = self._session.get(f"{self.base_url}{path}", **kwargs)
        response.raise_for_status()
        return response

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def post(self, path: str, **kwargs) -> requests.Response:
        response = self._session.post(f"{self.base_url}{path}", **kwargs)
        response.raise_for_status()
        return response

    @property
    def cookies(self) -> CookieJar:
        return self._session.cookies

    def save_cookies(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "; ".join(f"{c.name}={c.value}" for c in self._session.cookies)
        )

    def load_cookies(self, path: Path) -> None:
        self.login_with_cookie(path.read_text().strip())
