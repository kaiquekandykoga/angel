from nishikihebi.env import load_env_var


def test_load_env_var_reads_from_dotenv_in_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    (tmp_path / ".env").write_text("NVIDIA_API_KEY=from-dotenv\n")
    monkeypatch.chdir(tmp_path)

    assert load_env_var("NVIDIA_API_KEY") == "from-dotenv"


def test_load_env_var_prefers_existing_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("NVIDIA_API_KEY", "from-shell")
    (tmp_path / ".env").write_text("NVIDIA_API_KEY=from-dotenv\n")
    monkeypatch.chdir(tmp_path)

    assert load_env_var("NVIDIA_API_KEY") == "from-shell"
