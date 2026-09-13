import pytest

from recordscrape.server_settings import ServerSettings, server_settings_from_env


def test_no_environment_listens_on_loopback_without_a_token():
    assert server_settings_from_env({}) == ServerSettings(
        host="127.0.0.1", port=5001, data_dir=".", api_token=None
    )


def test_every_setting_is_read_from_its_variable():
    server_settings = server_settings_from_env(
        {
            "RECORDSCRAPE_HOST": "0.0.0.0",
            "RECORDSCRAPE_PORT": "8080",
            "RECORDSCRAPE_DATA_DIR": "/data",
            "RECORDSCRAPE_TOKEN": "s3cret",
        }
    )

    assert server_settings == ServerSettings(
        host="0.0.0.0", port=8080, data_dir="/data", api_token="s3cret"
    )


@pytest.mark.parametrize("loopback_host", ["127.0.0.1", "::1", "localhost"])
def test_a_loopback_host_needs_no_token(loopback_host):
    assert server_settings_from_env({"RECORDSCRAPE_HOST": loopback_host}).api_token is None


@pytest.mark.parametrize("reachable_host", ["0.0.0.0", "192.168.1.20", "scraper.lan"])
@pytest.mark.parametrize("unset_token", [{}, {"RECORDSCRAPE_TOKEN": ""}])
def test_a_host_other_machines_reach_is_refused_without_a_token(reachable_host, unset_token):
    with pytest.raises(ValueError, match="RECORDSCRAPE_TOKEN"):
        server_settings_from_env({"RECORDSCRAPE_HOST": reachable_host, **unset_token})


def test_a_port_that_is_not_a_number_is_refused():
    with pytest.raises(ValueError):
        server_settings_from_env({"RECORDSCRAPE_PORT": "web"})
