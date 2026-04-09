from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[1]


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if response.status < 500:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
            time.sleep(0.2)
    raise RuntimeError(f"Server did not become ready: {url}") from last_error


@pytest.fixture(scope="session")
def built_dist_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out_dir = tmp_path_factory.mktemp("py2dmol-dist")
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "make_dist.py"), "--out", str(out_dir)],
        cwd=REPO_ROOT,
        check=True,
    )
    return out_dir


@pytest.fixture(scope="session")
def served_dist_url(built_dist_dir: Path) -> str:
    port = _get_free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=built_dist_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_server(f"http://127.0.0.1:{port}/index.html")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context(accept_downloads=True)
    try:
        page = context.new_page()
        yield page
    finally:
        context.close()