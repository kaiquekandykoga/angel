from __future__ import annotations

import pytest

import nishikihebi
from nishikihebi.model import MissingApiKeyError


def test_main_exits_when_api_key_missing(monkeypatch):
    def raise_missing_api_key():
        raise MissingApiKeyError("NVIDIA_API_KEY environment variable is not set.")

    monkeypatch.setattr(nishikihebi, "build_model", raise_missing_api_key)

    with pytest.raises(SystemExit, match="NVIDIA_API_KEY environment variable is not set."):
        nishikihebi.main()
