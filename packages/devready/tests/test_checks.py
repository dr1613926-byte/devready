import json

from devready.checks import collect, check_config_files, check_tools


def test_check_config_files_metadata_only(tmp_path, monkeypatch):
    config = tmp_path / ".mcp.json"
    config.write_text('{"mcpServers": {}}')
    monkeypatch.setenv("DEVREADY_EXTRA_FILES", str(config))

    records = check_config_files()
    assert records, "expected the extra file to be included"
    rec = next(r for r in records if r["path"].endswith(".mcp.json"))
    assert rec["path"].endswith(".mcp.json")
    assert rec["bytes"] > 0
    assert rec["mode"].startswith("0o")
    assert len(rec["sha256_16"]) == 16
    assert "mcpServers" not in json.dumps(rec)


def test_check_tools_shape():
    records = check_tools()
    names = {r["name"] for r in records}
    assert {"node", "npm", "python3", "git", "claude", "code", "docker"} <= names
    for rec in records:
        assert isinstance(rec["present"], bool)
        if rec["present"]:
            assert "version" in rec


def test_collect_shape_and_no_values(tmp_path, monkeypatch):
    config = tmp_path / ".env"
    config.write_text("ANTHROPIC_API_KEY=sk-ant-secret-value")
    monkeypatch.setenv("DEVREADY_EXTRA_FILES", str(config))

    report = collect(stage="test", pkg="devready")
    assert report["schema"] == "devready/v1"
    assert report["stage"] == "test"
    assert report["pkg"] == "devready"
    assert isinstance(report["tools"], list) and report["tools"]
    assert isinstance(report["files"], list) and report["files"]
    assert report["config_count"] >= 1
    assert "sk-ant-secret-value" not in json.dumps(report)
