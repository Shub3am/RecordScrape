"""
Tests for turning a stored proxy URL into Playwright proxy settings.
They pin which URLs are accepted, how env references expand, and which are refused before launch.
"""

import pytest

from recordscrape.proxies import proxy_settings_from_url


def test_http_proxy_with_credentials_splits_them_out():
    assert proxy_settings_from_url("http://ana:s%40cret@proxy.example:8080") == {
        "server": "http://proxy.example:8080",
        "username": "ana",
        "password": "s@cret",
    }


def test_env_references_expand_before_parsing(monkeypatch):
    monkeypatch.setenv("PROXY_USER", "ana")
    monkeypatch.setenv("PROXY_PASS", "hunter2")

    assert proxy_settings_from_url("http://${PROXY_USER}:${PROXY_PASS}@proxy.example:8080") == {
        "server": "http://proxy.example:8080",
        "username": "ana",
        "password": "hunter2",
    }


def test_a_missing_env_variable_is_refused(monkeypatch):
    monkeypatch.delenv("PROXY_PASS", raising=False)

    with pytest.raises(ValueError, match="PROXY_PASS"):
        proxy_settings_from_url("http://ana:${PROXY_PASS}@proxy.example:8080")


def test_socks5_without_credentials_is_accepted():
    assert proxy_settings_from_url("socks5://127.0.0.1:1080") == {
        "server": "socks5://127.0.0.1:1080"
    }


@pytest.mark.parametrize(
    "proxy_url, refusal",
    [
        ("socks5://ana:hunter2@127.0.0.1:1080", "SOCKS5 proxies with a username"),
        ("ftp://proxy.example:21", "must start with one of: http, https, socks5"),
        ("proxy.example:8080", "must start with one of"),
        ("http://", "no host"),
    ],
)
def test_unusable_proxy_urls_are_refused(proxy_url, refusal):
    with pytest.raises(ValueError, match=refusal):
        proxy_settings_from_url(proxy_url)
