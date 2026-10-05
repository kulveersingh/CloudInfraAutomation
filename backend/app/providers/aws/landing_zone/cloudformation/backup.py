from app.providers.aws.landing_zone.cloudformation.base import StackContext, StackRenderer

POLICY_VERSION = "2012-10-17"
RETENTION_DAYS = 60
LOCK_COOLING_OFF_DAYS = 3
SUPER_USER_ROLE = "CloudInfraBackupSuperUser"
SUPER_USER = f"arn:aws:iam::*:role/{SUPER_USER_ROLE}"
ACCOUNT_ROOT = {"Fn::Sub": "arn:${AWS::Partition}:iam::${AWS::AccountId}:root"}
IN_ORGANIZATION = {"StringEquals": {"aws:PrincipalOrgID": {"Ref": "OrganizationId"}}}
PROTECTED_ACTIONS = ["backup:DeleteRecoveryPoint", "backup:UpdateRecoveryPointLifecycle", "backup:DeleteBackupVault",
                     "backup:DeleteBackupVaultAccessPolicy", "backup:DeleteBackupVaultLockConfiguration"]
RETAIN = {"DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain"}


class BackupStack(StackRenderer):
    """The central vault that keeps teardown backups (§21.9.1), deployed into the Backup account in every governed
    region: Vault Lock in compliance mode for 60 days, and only the MFA-protected super-user role can delete."""

    name = "lz-backup"
    description = "Locked central vault for teardown backups, its key, and the backup super-user role."

    def sections(self, context: StackContext) -> dict:
        return {
            "Parameters": {"OrganizationId": {"Type": "String", "AllowedPattern": r"^o-[a-z0-9]{10,32}$"},
                           "HomeRegion": {"Type": "String", "Default": context.design.answers.home_region}},
            "Conditions": {"IsHomeRegion": {"Fn::Equals": [{"Ref": "AWS::Region"}, {"Ref": "HomeRegion"}]}},
            "Resources": {"VaultKey": self._key(), "TeardownVault": self._vault(),
                          "BackupSuperUserRole": self._super_user()},
            "Outputs": {"TeardownVaultArn": {"Value": {"Fn::GetAtt": ["TeardownVault", "BackupVaultArn"]}}},
        }

    def _key(self) -> dict:
        return {"Type": "AWS::KMS::Key", **RETAIN, "Properties": {
            "Description": "Encrypts the locked teardown backup vault",
            "EnableKeyRotation": True,
            "KeyPolicy": {"Version": POLICY_VERSION, "Statement": [
                {"Sid": "AdministerKey", "Effect": "Allow", "Principal": {"AWS": ACCOUNT_ROOT}, "Action": "kms:*",
                 "Resource": "*"},
                {"Sid": "AllowOrganizationBackupCopies", "Effect": "Allow", "Principal": {"AWS": "*"},
                 "Action": ["kms:Decrypt", "kms:GenerateDataKey*", "kms:ReEncrypt*", "kms:CreateGrant",
                            "kms:DescribeKey"], "Resource": "*", "Condition": IN_ORGANIZATION}]}}}

    def _vault(self) -> dict:
        return {"Type": "AWS::Backup::BackupVault", **RETAIN, "Properties": {
            "BackupVaultName": {"Fn::Sub": "cloudinfra-teardown-${AWS::Region}"},
            "EncryptionKeyArn": {"Fn::GetAtt": ["VaultKey", "Arn"]},
            "LockConfiguration": {"MinRetentionDays": RETENTION_DAYS, "ChangeableForDays": LOCK_COOLING_OFF_DAYS},
            "AccessPolicy": {"Version": POLICY_VERSION, "Statement": [
                {"Sid": "AllowOrganizationCopies", "Effect": "Allow", "Principal": {"AWS": "*"},
                 "Action": "backup:CopyIntoBackupVault", "Resource": "*", "Condition": IN_ORGANIZATION},
                {"Sid": "OnlySuperUsersDelete", "Effect": "Deny", "Principal": {"AWS": "*"},
                 "Action": PROTECTED_ACTIONS, "Resource": "*",
                 "Condition": {"ArnNotLike": {"aws:PrincipalArn": SUPER_USER}}}]}}}

    def _super_user(self) -> dict:
        trust = {"Version": POLICY_VERSION, "Statement": [{
            "Effect": "Allow", "Principal": {"AWS": ACCOUNT_ROOT}, "Action": "sts:AssumeRole",
            "Condition": {"Bool": {"aws:MultiFactorAuthPresent": "true"}}}]}
        permissions = {"Version": POLICY_VERSION, "Statement": [{
            "Effect": "Allow", "Resource": "*",
            "Action": ["backup:DeleteRecoveryPoint", "backup:DescribeRecoveryPoint", "backup:ListBackupVaults",
                       "backup:ListRecoveryPointsByBackupVault"]}]}
        return {"Type": "AWS::IAM::Role", "Condition": "IsHomeRegion", "Properties": {
            "RoleName": SUPER_USER_ROLE, "AssumeRolePolicyDocument": trust, "MaxSessionDuration": 3600,
            "Policies": [{"PolicyName": "DeleteExpiredRecoveryPoints", "PolicyDocument": permissions}]}}
