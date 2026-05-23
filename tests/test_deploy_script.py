from pathlib import Path


def test_deploy_script_writes_server_sqlite_api_config():
    script = Path("scripts/deploy_to_server.sh")

    content = script.read_text(encoding="utf-8")

    assert "lin@192.168.3.56" in content
    assert "/home/lin/project-src/finance-cli" in content
    assert "/home/lin/opt/finance-cli/config.json" in content
    assert '"sqlite_api_host": "http://127.0.0.1:8080"' in content
    assert '"sqlite_db": "finance.db"' in content
    assert "FINANCE_CLI_CONFIG=/home/lin/opt/finance-cli/config.json" in content
    assert "python3 -m pip install --target '${DEPLOY_DIR}/site'" in content
    assert "PYTHONPATH=/home/lin/opt/finance-cli/site" in content
