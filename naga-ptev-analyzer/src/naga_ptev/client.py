from __future__ import annotations

import asyncio
from datetime import datetime
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from naga_ptev.models import KyokuState
from naga_ptev.probe import (
    EXPECTED_FORM_FIELDS,
    NAGA_ANALYZER_PATH,
    build_target_url,
    find_analyzer_result_call,
    resolve_endpoint_url,
    sanitize_fetch_calls,
)
from naga_ptev.storage import save_raw_json, timestamped_artifact_path

try:
    import keyring as _keyring
    from keyring.errors import KeyringError as _KeyringError
except ImportError:  # pragma: no cover - exercised only when keyring is missing at runtime.
    _keyring = None

    class _KeyringError(Exception):
        """Fallback keyring error type when keyring is unavailable."""


try:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
except ImportError:  # pragma: no cover - exercised only when Playwright is missing at runtime.
    Browser = BrowserContext = Page = Playwright = Any  # type: ignore[assignment]
    async_playwright = None


FETCH_MONKEY_PATCH = """
(() => {
  const originalFetch = window.fetch;
  window.__nagaFetchCalls = [];
  window.fetch = async (...args) => {
    const input = args[0];
    const init = args[1] || {};
    const url = typeof input === "string" ? input : input.url;
    const method = init.method || "GET";
    const call = { url, method, bodyFields: [], json: null, status: null };

    try {
      if (init.body instanceof FormData) {
        for (const [k, v] of init.body.entries()) {
          call.bodyFields.push([k, String(v)]);
        }
      }
    } catch (e) {}

    window.__nagaFetchCalls.push(call);
    const response = await originalFetch(...args);
    call.status = response.status;

    try {
      const clone = response.clone();
      call.json = await clone.json();
    } catch (e) {}

    return response;
  };
})();
"""

LOGIN_ENTRY_URLS = (
    "https://naga.dmv.nico/naga_report/top/?next=/naga_report/kyoku_bop/",
    "https://naga.dmv.nico/naga_report/top/",
    "https://naga.dmv.nico/",
)
NICONICO_LOGIN_URL = "https://naga.dmv.nico/niconico/niconico_login/"
NAGA_KEYRING_SERVICE = "tenhou_hojo.naga_ptev"
NAGA_KEYRING_LOGIN_KEY = "niconico_mail_tel"
NAGA_KEYRING_PASSWORD_KEY = "niconico_password"
NAGA_NICONICO_ID_ENV_KEYS = ("NAGA_NICONICO_MAIL_TEL", "NAGA_LOGIN_ID", "NICONICO_LOGIN_ID")
NAGA_NICONICO_PASSWORD_ENV_KEYS = ("NAGA_NICONICO_PASSWORD", "NAGA_LOGIN_PASSWORD", "NICONICO_PASSWORD")


def _is_analyzer_auth_redirect(page_url: str) -> bool:
    parsed = urlparse(page_url)
    if parsed.netloc != "naga.dmv.nico":
        return False
    if parsed.path != "/naga_report/top/":
        return False
    return "next=/naga_report/kyoku_bop/" in (parsed.query or "")


def _load_simple_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return values
    for raw_line in raw_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip()
        if not normalized_key:
            continue
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {"'", '"'}
        ):
            normalized_value = normalized_value[1:-1]
        values[normalized_key] = normalized_value
    return values


def _dotenv_candidate_paths(storage_state_path: Path | None = None) -> tuple[Path, ...]:
    candidate_paths: list[Path] = []
    cwd = Path.cwd()
    candidate_paths.append(cwd / ".env")
    candidate_paths.append(cwd.parent / ".env")
    current_file = Path(__file__).resolve()
    candidate_paths.append(current_file.parents[2] / ".env")
    candidate_paths.append(current_file.parents[3] / ".env")
    candidate_paths.append(current_file.parents[3] / "src" / ".env")
    if storage_state_path is not None:
        candidate_paths.append(storage_state_path.parent / ".env")
        if storage_state_path.parent.name == ".secrets":
            candidate_paths.append(storage_state_path.parent.parent / ".env")
    unique_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for path in candidate_paths:
        normalized_path = path.resolve()
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        unique_paths.append(normalized_path)
    return tuple(unique_paths)


def _first_mapping_value(keys: tuple[str, ...], values: dict[str, str]) -> str | None:
    for key in keys:
        raw_value = values.get(key)
        if raw_value is not None and str(raw_value).strip():
            return str(raw_value).strip()
    return None


def _first_process_env_value(keys: tuple[str, ...]) -> str | None:
    for key in keys:
        raw_value = os.environ.get(key)
        if raw_value is not None and str(raw_value).strip():
            return str(raw_value).strip()
    return None


def _keyring_available() -> bool:
    return _keyring is not None


def _load_niconico_credentials_from_keyring() -> tuple[str, str] | None:
    if _keyring is None:
        return None
    try:
        login_id = _keyring.get_password(NAGA_KEYRING_SERVICE, NAGA_KEYRING_LOGIN_KEY)
        password = _keyring.get_password(NAGA_KEYRING_SERVICE, NAGA_KEYRING_PASSWORD_KEY)
    except Exception:
        return None
    normalized_login_id = str(login_id or "").strip()
    normalized_password = str(password or "").strip()
    if not normalized_login_id or not normalized_password:
        return None
    return normalized_login_id, normalized_password


def _store_niconico_credentials_in_keyring(login_id: str, password: str) -> None:
    if _keyring is None:
        raise RuntimeError(
            "keyring is not installed. Run `pip install -e naga-ptev-analyzer` or `pip install keyring` first."
        )
    normalized_login_id = str(login_id or "").strip()
    normalized_password = str(password or "").strip()
    if not normalized_login_id or not normalized_password:
        raise RuntimeError("Both NicoNico login ID and password are required.")
    try:
        _keyring.set_password(NAGA_KEYRING_SERVICE, NAGA_KEYRING_LOGIN_KEY, normalized_login_id)
        _keyring.set_password(NAGA_KEYRING_SERVICE, NAGA_KEYRING_PASSWORD_KEY, normalized_password)
    except _KeyringError as exc:
        raise RuntimeError(f"Could not store NAGA credentials in the OS credential store: {exc}") from exc


def _clear_niconico_credentials_in_keyring() -> bool:
    if _keyring is None:
        raise RuntimeError(
            "keyring is not installed. Run `pip install -e naga-ptev-analyzer` or `pip install keyring` first."
        )
    removed_any = False
    for account_name in (NAGA_KEYRING_LOGIN_KEY, NAGA_KEYRING_PASSWORD_KEY):
        try:
            _keyring.delete_password(NAGA_KEYRING_SERVICE, account_name)
            removed_any = True
        except Exception:
            continue
    return removed_any


def _resolve_niconico_credentials(
    storage_state_path: Path | None = None,
) -> tuple[str, str] | None:
    dotenv_values: dict[str, str] = {}
    for dotenv_path in _dotenv_candidate_paths(storage_state_path):
        if not dotenv_path.exists():
            continue
        for key, value in _load_simple_dotenv(dotenv_path).items():
            normalized_value = str(value or "").strip()
            if normalized_value or key not in dotenv_values:
                dotenv_values[key] = value
    login_id = _first_process_env_value(NAGA_NICONICO_ID_ENV_KEYS)
    password = _first_process_env_value(NAGA_NICONICO_PASSWORD_ENV_KEYS)
    if login_id and password:
        return login_id, password
    keyring_credentials = _load_niconico_credentials_from_keyring()
    if keyring_credentials is not None:
        return keyring_credentials
    login_id = _first_mapping_value(NAGA_NICONICO_ID_ENV_KEYS, dotenv_values)
    password = _first_mapping_value(NAGA_NICONICO_PASSWORD_ENV_KEYS, dotenv_values)
    if not login_id or not password:
        return None
    return login_id, password


class NagaPtevClient:
    def __init__(
        self,
        *,
        sleep_seconds: float = 0.8,
        raw_output_dir: str | Path = "out/raw",
    ) -> None:
        self.sleep_seconds = float(sleep_seconds)
        self.raw_output_dir = Path(raw_output_dir)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._storage_state_path: Path | None = None
        self._probed_endpoint: str | None = None
        self._csrf_token: str | None = None
        self._last_probe_result: dict[str, Any] | None = None
        self.last_raw_path: Path | None = None

    async def _try_login_with_env_credentials(self) -> bool:
        credentials = _resolve_niconico_credentials(self._storage_state_path)
        if credentials is None:
            return False
        if self._page is None or self._context is None:
            raise RuntimeError("Browser page was not created")
        login_id, password = credentials
        await self._page.goto(NICONICO_LOGIN_URL, wait_until="domcontentloaded")
        mail_tel = self._page.locator("input[name='mail_tel']")
        password_input = self._page.locator("input[name='password']")
        if not await mail_tel.count() or not await password_input.count():
            return False
        await mail_tel.first.fill(login_id)
        await password_input.first.fill(password)
        submit_button = self._page.locator("#login__submit, input[type='submit'], button[type='submit']")
        if not await submit_button.count():
            return False
        await submit_button.first.click()
        try:
            await self._page.wait_for_url("**naga.dmv.nico/**", timeout=60000)
        except Exception:
            return False
        if self._storage_state_path is not None:
            await self._context.storage_state(path=str(self._storage_state_path))
        return "naga.dmv.nico" in self._page.url

    async def _ensure_playwright_started(self, *, headless: bool) -> None:
        if async_playwright is None:
            raise RuntimeError(
                "Playwright is not installed. Run `pip install -e .` and `python -m playwright install chromium`."
            )
        if self._playwright is not None and self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=headless)

    async def _open_context(self, *, storage_state_path: Path | None = None) -> None:
        if self._browser is None:
            raise RuntimeError("Browser is not started")
        if self._context is not None:
            await self._context.close()
        context_kwargs: dict[str, Any] = {}
        if storage_state_path is not None and storage_state_path.exists():
            context_kwargs["storage_state"] = str(storage_state_path)
        self._context = await self._browser.new_context(**context_kwargs)
        self._page = await self._context.new_page()
        self._probed_endpoint = None
        self._csrf_token = None
        self._last_probe_result = None

    async def _bootstrap_storage_state_with_saved_credentials(self, target: Path) -> bool:
        target.parent.mkdir(parents=True, exist_ok=True)
        await self._ensure_playwright_started(headless=True)
        await self._open_context()
        self._storage_state_path = target
        return await self._try_login_with_env_credentials()

    async def login_and_save_state(self, storage_state_path: str) -> None:
        target = Path(storage_state_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        await self._ensure_playwright_started(headless=False)
        await self._open_context()
        self._storage_state_path = target
        if self._page is None or self._context is None:
            raise RuntimeError("Browser page was not created")
        last_error: Exception | None = None
        for login_url in LOGIN_ENTRY_URLS:
            try:
                response = await self._page.goto(login_url, wait_until="domcontentloaded")
            except Exception as exc:
                last_error = exc
                continue
            if response is None or response.status != 404:
                break
        else:
            raise RuntimeError(
                "Could not open a NAGA login entry page. "
                f"Tried: {', '.join(LOGIN_ENTRY_URLS)}"
            ) from last_error
        logged_in_with_env = await self._try_login_with_env_credentials()
        if logged_in_with_env:
            await self._context.storage_state(path=str(target))
            return
        await asyncio.to_thread(
            input,
            "Log in in the opened browser window, then press Enter here to save the storage state...",
        )
        await self._context.storage_state(path=str(target))

    async def open_with_state(self, storage_state_path: str) -> None:
        target = Path(storage_state_path)
        if not target.exists():
            bootstrapped = await self._bootstrap_storage_state_with_saved_credentials(target)
            if not bootstrapped or not target.exists():
                has_credentials = _resolve_niconico_credentials(target) is not None
                if has_credentials:
                    raise RuntimeError(
                        "Saved NAGA login state does not exist yet, and automatic credential login did not "
                        "finish creating it. Additional verification may be required. Re-run "
                        "`python -m naga_ptev.cli login --storage ...` and complete login manually once."
                    )
                raise FileNotFoundError(
                    f"Storage state not found: {target}. "
                    "Store credentials with `python -m naga_ptev.cli store-login` or run "
                    "`python -m naga_ptev.cli login --storage ...` once."
                )
            return
        await self._ensure_playwright_started(headless=True)
        await self._open_context(storage_state_path=target)
        self._storage_state_path = target

    async def probe_endpoint(self, state: KyokuState) -> dict[str, Any]:
        if self._page is None:
            raise RuntimeError("Call open_with_state() or login_and_save_state() first")

        self._probed_endpoint = None
        self._csrf_token = None
        await self._page.add_init_script(FETCH_MONKEY_PATCH)
        await asyncio.sleep(self.sleep_seconds)
        target_url = build_target_url(state)
        await self._page.goto(target_url, wait_until="networkidle")
        await self._page.wait_for_timeout(int(self.sleep_seconds * 1000))
        page_url = self._page.url
        auth_redirected = _is_analyzer_auth_redirect(page_url)

        csrf_token: str | None = None
        csrf_locator = self._page.locator("input[name='csrfmiddlewaretoken']")
        if await csrf_locator.count():
            try:
                csrf_token = await csrf_locator.first.input_value()
            except Exception:
                csrf_token = await csrf_locator.first.get_attribute("value")

        from_scores_url = await self._page.evaluate(
            """() => {
                if (typeof window.from_scores_url === "string") {
                    return window.from_scores_url;
                }
                return null;
            }"""
        )
        html = await self._page.content()
        if not from_scores_url:
            match = re.search(r"from_scores_url\\s*=\\s*['\\\"]([^'\\\"]+)['\\\"]", html)
            if match:
                from_scores_url = match.group(1)

        captured_calls = await self._page.evaluate("() => window.__nagaFetchCalls || []")
        sanitized_calls = sanitize_fetch_calls(captured_calls)
        inferred_endpoint, sample_json = find_analyzer_result_call(sanitized_calls)
        endpoint = resolve_endpoint_url(page_url, str(from_scores_url or "")) if from_scores_url else None
        if not endpoint and inferred_endpoint:
            endpoint = resolve_endpoint_url(page_url, inferred_endpoint)
        if not endpoint and not auth_redirected and csrf_token and NAGA_ANALYZER_PATH in page_url:
            endpoint = page_url

        self._probed_endpoint = endpoint
        self._csrf_token = csrf_token
        probe_result = {
            "page_url": page_url,
            "endpoint": endpoint,
            "csrf_token": csrf_token,
            "captured_calls": sanitized_calls,
            "sample_json": sample_json,
            "from_scores_url": from_scores_url,
            "auth_redirected": auth_redirected,
        }
        self._last_probe_result = probe_result
        return probe_result

    async def _request_context(self) -> Any:
        if self._context is None and self._page is None:
            raise RuntimeError("No page or browser context is open")
        if self._context is not None and getattr(self._context, "request", None) is not None:
            return self._context.request
        if self._page is not None and getattr(self._page, "request", None) is not None:
            return self._page.request
        raise RuntimeError("Playwright API request context is unavailable")

    async def query(self, state: KyokuState) -> dict[str, Any]:
        if self._page is None:
            raise RuntimeError("Call open_with_state() first")
        if not self._probed_endpoint or not self._csrf_token:
            await self.probe_endpoint(state)
        if self._last_probe_result and self._last_probe_result.get("auth_redirected"):
            relogin_succeeded = await self._try_login_with_env_credentials()
            if relogin_succeeded:
                await self.probe_endpoint(state)
            else:
                has_credentials = _resolve_niconico_credentials(self._storage_state_path) is not None
                if has_credentials:
                    raise RuntimeError(
                        "Saved NAGA session expired and automatic credential login did not complete. "
                        "Additional verification may be required. Re-run "
                        "`python -m naga_ptev.cli login --storage ...` and complete login manually."
                    )
                raise RuntimeError(
                    "Saved NAGA session is not authenticated anymore. "
                    "Re-run `python -m naga_ptev.cli login --storage ...` and log in again, "
                    "or store NAGA_NICONICO_MAIL_TEL and NAGA_NICONICO_PASSWORD with "
                    "`python -m naga_ptev.cli store-login`."
                )
        if not self._probed_endpoint:
            raise RuntimeError(
                "Could not determine analyzer endpoint during probe. "
                "Run `python -m naga_ptev.cli probe ...` and confirm the page is reachable while logged in."
            )
        if not self._csrf_token:
            raise RuntimeError(
                "Could not determine csrfmiddlewaretoken during probe. "
                "The analyzer page may not be loaded in an authenticated session."
            )

        await asyncio.sleep(self.sleep_seconds)
        request_context = await self._request_context()
        multipart_data = {
            "kyoku": str(int(state.kyoku)),
            "honba": str(int(state.honba)),
            "kyotaku": str(int(state.kyotaku)),
            "score0": str(int(state.scores[0])),
            "score1": str(int(state.scores[1])),
            "score2": str(int(state.scores[2])),
            "score3": str(int(state.scores[3])),
            "csrfmiddlewaretoken": self._csrf_token,
        }
        response = await request_context.post(
            self._probed_endpoint,
            multipart=multipart_data,
            headers={
                "Referer": self._page.url,
                "X-CSRFToken": self._csrf_token,
            },
        )
        if response.status != 200:
            raise RuntimeError(f"Analyzer request failed with HTTP {response.status}")
        payload = await response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Analyzer response is not a JSON object: {payload!r}")
        if int(payload.get("status", 0)) != 200:
            raise RuntimeError(f"Analyzer JSON status is not 200: {payload!r}")

        artifact = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "state": state.model_dump(),
            "endpoint": self._probed_endpoint,
            "expected_fields": list(EXPECTED_FORM_FIELDS),
            "probe_page_url": self._last_probe_result.get("page_url") if self._last_probe_result else None,
            "probe_from_scores_url": self._last_probe_result.get("from_scores_url") if self._last_probe_result else None,
            "probe_captured_calls": self._last_probe_result.get("captured_calls") if self._last_probe_result else [],
            "probe_sample_json": self._last_probe_result.get("sample_json") if self._last_probe_result else None,
            "response": payload,
        }
        artifact_path = timestamped_artifact_path(self.raw_output_dir, "naga_query", ".json")
        self.last_raw_path = save_raw_json(artifact, artifact_path)
        return payload

    async def close(self) -> None:
        if self._page is not None:
            await self._page.close()
            self._page = None
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
