import re

import pytest

import nishikihebi.__main__
from nishikihebi.model import MissingApiKeyError


def test_main_exits_when_api_key_missing(monkeypatch):
    message = "NVIDIA_API_KEY environment variable is not set."

    def raise_missing_api_key():
        raise MissingApiKeyError(message)

    monkeypatch.setattr(nishikihebi.__main__, "build_model", raise_missing_api_key)

    with pytest.raises(SystemExit, match=re.escape(message)):
        nishikihebi.__main__.main()
