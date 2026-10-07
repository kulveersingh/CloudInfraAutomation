#!/usr/bin/env bash
# The locked vault's two identities (§23): the platform (writes and reads, never deletes or bypasses) and the backup
# super users (may delete after the lock, or bypass governance). Safe to run again.
set -euo pipefail
mc alias set vault "${VAULT_URL:-http://vault:9000}" "$VAULT_ADMIN_ACCESS_KEY" "$VAULT_ADMIN_SECRET_KEY" >/dev/null
mc admin policy create vault cloudinfra-platform /setup/platform-policy.json
mc admin policy create vault cloudinfra-backup-super-users /setup/super-user-policy.json
mc admin user add vault cloudinfra-platform "$VAULT_PLATFORM_SECRET_KEY"
mc admin user add vault cloudinfra-backup-super-users "$VAULT_SUPER_USER_SECRET_KEY"
mc admin policy attach vault cloudinfra-platform --user cloudinfra-platform 2>/dev/null || true
mc admin policy attach vault cloudinfra-backup-super-users --user cloudinfra-backup-super-users 2>/dev/null || true
echo "Vault users ready. Create the locked buckets with: uv run python -m app.adapters.minio_backup"
