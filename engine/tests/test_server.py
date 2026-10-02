import sys

import pytest

from fosas_engine.server import main


def test_host_0_0_0_0_is_rejected(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["fosas_engine.server", "--host", "0.0.0.0"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    assert "0.0.0.0" in capsys.readouterr().err


def test_host_wildcard_ipv6_is_rejected(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["fosas_engine.server", "--host", "::"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
