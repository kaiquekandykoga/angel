from angel.env import load_env_var


def test_load_env_var_reads_from_dotenv_in_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("ANGEL_NVIDIA_API_KEY", raising=False)
    (tmp_path / ".env").write_text("ANGEL_NVIDIA_API_KEY=from-dotenv\n")
    monkeypatch.chdir(tmp_path)

    assert load_env_var("ANGEL_NVIDIA_API_KEY") == "from-dotenv"


def test_load_env_var_prefers_existing_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("ANGEL_NVIDIA_API_KEY", "from-shell")
    (tmp_path / ".env").write_text("ANGEL_NVIDIA_API_KEY=from-dotenv\n")
    monkeypatch.chdir(tmp_path)

    assert load_env_var("ANGEL_NVIDIA_API_KEY") == "from-shell"
