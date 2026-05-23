#!/usr/bin/env bash
set -euo pipefail

SSH_TARGET="lin@192.168.3.56"
SOURCE_DIR="/home/lin/project-src/finance-cli"
DEPLOY_DIR="/home/lin/opt/finance-cli"
CONFIG_PATH="${DEPLOY_DIR}/config.json"

rsync -az --delete \
  --exclude ".git/" \
  --exclude "__pycache__/" \
  --exclude ".pytest_cache/" \
  --exclude ".venv/" \
  --exclude "venv/" \
  --exclude "dist/" \
  --exclude "build/" \
  --exclude "*.egg-info/" \
  ./ "${SSH_TARGET}:${SOURCE_DIR}/"

ssh "${SSH_TARGET}" "mkdir -p '${DEPLOY_DIR}'"
ssh "${SSH_TARGET}" "rm -rf '${DEPLOY_DIR}/site' && mkdir -p '${DEPLOY_DIR}/site' && cd '${SOURCE_DIR}' && python3 -m pip install --target '${DEPLOY_DIR}/site' ."
ssh "${SSH_TARGET}" "cat > '${CONFIG_PATH}'" <<'JSON'
{
  "sqlite_api_host": "http://127.0.0.1:8080",
  "sqlite_db": "finance.db"
}
JSON
ssh "${SSH_TARGET}" "cat > '${DEPLOY_DIR}/finance'" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
export FINANCE_CLI_CONFIG=/home/lin/opt/finance-cli/config.json
export PYTHONPATH=/home/lin/opt/finance-cli/site
exec python3 -m finance_cli "$@"
SH
ssh "${SSH_TARGET}" "chmod +x '${DEPLOY_DIR}/finance'"
ssh "${SSH_TARGET}" "'${DEPLOY_DIR}/finance' --help >/dev/null"

echo "Deployed source to ${SOURCE_DIR}"
echo "Runtime wrapper: ${DEPLOY_DIR}/finance"
