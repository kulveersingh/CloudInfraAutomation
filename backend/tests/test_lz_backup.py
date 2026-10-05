import yaml

from tests.test_lz_stacks import bundle, policy_named, properties, resources, stack

SUPER_USER = "arn:aws:iam::*:role/CloudInfraBackupSuperUser"


def vault() -> dict:
    return properties(stack("lz-backup"), "TeardownVault")


def test_central_vault_is_locked_for_sixty_days_in_compliance_mode():
    assert vault()["LockConfiguration"] == {"MinRetentionDays": 60, "ChangeableForDays": 3}


def test_central_vault_is_named_per_region_and_retained():
    body = stack("lz-backup")["Resources"]["TeardownVault"]
    assert (body["Properties"]["BackupVaultName"], body["DeletionPolicy"]) == (
        {"Fn::Sub": "cloudinfra-teardown-${AWS::Region}"}, "Retain")


def test_central_vault_accepts_copies_from_the_organization():
    statement = next(item for item in vault()["AccessPolicy"]["Statement"] if item["Sid"] == "AllowOrganizationCopies")
    assert (statement["Action"], statement["Condition"]) == (
        "backup:CopyIntoBackupVault", {"StringEquals": {"aws:PrincipalOrgID": {"Ref": "OrganizationId"}}})


def test_only_the_super_user_can_delete_recovery_points():
    statement = next(item for item in vault()["AccessPolicy"]["Statement"] if item["Sid"] == "OnlySuperUsersDelete")
    assert (statement["Effect"], "backup:DeleteRecoveryPoint" in statement["Action"], statement["Condition"]) == (
        "Deny", True, {"ArnNotLike": {"aws:PrincipalArn": SUPER_USER}})


def test_vault_is_encrypted_with_its_own_rotating_key():
    template = stack("lz-backup")
    assert (vault()["EncryptionKeyArn"], properties(template, "VaultKey")["EnableKeyRotation"]) == (
        {"Fn::GetAtt": ["VaultKey", "Arn"]}, True)


def test_super_user_role_needs_mfa_and_exists_once():
    role = stack("lz-backup")["Resources"]["BackupSuperUserRole"]
    trust = role["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
    assert (role["Condition"], role["Properties"]["RoleName"], trust["Condition"]) == (
        "IsHomeRegion", "CloudInfraBackupSuperUser", {"Bool": {"aws:MultiFactorAuthPresent": "true"}})


def test_apply_script_deploys_the_backup_stack_into_the_backup_account_in_every_region():
    script = bundle()["scripts/apply.sh"]
    assert ('BACKUP_ACCOUNT_ID="$(output "$REGION" lz-accounts BackupAccountId)"' in script,
            "--stack-name lz-backup" in script, script.index("lz-network") < script.index("lz-backup")) == (
        True, True, True)


def test_without_a_backup_account_the_backup_stack_is_skipped():
    script = bundle(infrastructure=["network"])["scripts/apply.sh"]
    assert ("--stack-name lz-backup" not in script, "No Backup account: teardowns are disabled." in script) == (True, True)


def test_accounts_stack_exports_the_backup_account():
    assert "BackupAccountId" in stack("lz-accounts")["Outputs"]


def test_workload_accounts_get_a_local_teardown_vault_in_every_governed_region():
    stack_sets = resources(stack("lz-bootstrap"), "AWS::CloudFormation::StackSet")
    vaults = stack_sets["TeardownVaults"]["Properties"]
    template = yaml.safe_load(vaults["TemplateBody"])
    assert (vaults["StackInstancesGroup"][0]["Regions"], template["Resources"]["TeardownVault"]["Properties"][
        "BackupVaultName"]) == (["us-east-1", "us-east-2"], "cloudinfra-teardown")


def test_baseline_scp_denies_recovery_point_deletion_except_super_users():
    statement = next(item for item in policy_named(stack("lz-structure"), "acme-workload-baseline")["Content"]["Statement"]
                     if item["Sid"] == "DenyRecoveryPointDeletion")
    assert (statement["Action"], statement["Condition"]) == (
        ["backup:DeleteRecoveryPoint", "backup:DeleteBackupVaultLockConfiguration"],
        {"ArnNotLike": {"aws:PrincipalARN": [SUPER_USER]}})


def test_infrastructure_scp_also_denies_recovery_point_deletion():
    content = policy_named(stack("lz-structure"), "acme-network-admin-only")["Content"]
    assert "DenyRecoveryPointDeletion" in [statement["Sid"] for statement in content["Statement"]]


def test_production_protection_no_longer_lets_the_release_executor_delete_backups():
    content = policy_named(stack("lz-structure"), "acme-production-protection")["Content"]
    assert "backup:DeleteRecoveryPoint" not in content["Statement"][0]["Action"]


def test_scps_stay_under_the_aws_size_limit():
    template = stack("lz-structure", infrastructure=["network", "shared_services", "identity", "backup", "monitoring"])
    sizes = [len(json_text(body["Properties"]["Content"]))
             for body in resources(template, "AWS::Organizations::Policy").values()
             if body["Properties"]["Type"] == "SERVICE_CONTROL_POLICY"]
    assert max(sizes) <= 5120


def json_text(content: dict) -> str:
    import json
    return json.dumps(content, separators=(",", ":"))
