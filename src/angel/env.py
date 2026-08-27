import os

from dotenv import find_dotenv, load_dotenv


def load_env_var(name: str) -> str | None:
    load_dotenv(find_dotenv(usecwd=True))
    return os.environ.get(name)
