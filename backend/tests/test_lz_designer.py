from tests.lz_factories import CATALOG, answers, aws_designer


def design(**overrides):
    return aws_designer().design(answers(**overrides), CATALOG)


def top_level(**overrides) -> list[str]:
    return [ou.name for ou in design(**overrides).root_ous]


def accounts_of(ou_name: str, **overrides) -> list[str]:
    return [account.name for account in design(**overrides).ou_named(ou_name).accounts]


def test_default_structure_keeps_every_environment_separate():
    assert top_level() == ["Security", "Infrastructure", "Sandbox", "DEV", "TEST", "STAGE", "PROD",
                           "Policy Staging", "Exceptions", "Suspended"]


def test_security_ou_holds_log_archive_audit_and_tooling():
    assert accounts_of("Security") == ["acme-log-archive", "acme-audit", "acme-security-tooling"]


def test_security_tooling_is_optional():
    assert accounts_of("Security", security_tooling=False) == ["acme-log-archive", "acme-audit"]


def test_security_and_sandbox_ous_are_created_by_control_tower():
    created = [ou.name for ou in design().walk() if ou.created_by_service]
    assert created == ["Security", "Sandbox"]


def test_infrastructure_accounts_follow_the_answers():
    assert accounts_of("Infrastructure", infrastructure=["network", "backup"]) == ["acme-network", "acme-backup"]


def test_one_account_per_portfolio_per_environment():
    assert accounts_of("PROD") == ["acme-payments-prod", "acme-retail-prod"]


def test_one_account_per_environment():
    assert accounts_of("PROD", account_model="environment") == ["acme-prod"]


def test_one_account_per_product_per_environment():
    assert accounts_of("DEV", account_model="product") == ["acme-invoicing-dev", "acme-storefront-dev"]


def test_sandbox_accounts_per_team():
    assert accounts_of("Sandbox") == ["acme-payments-sandbox", "acme-retail-sandbox"]


def test_sandbox_accounts_per_developer_start_with_one_template_account():
    assert accounts_of("Sandbox", sandbox={"model": "developer"}) == ["acme-developer-sandbox-01"]


def test_account_emails_use_plus_addressing():
    assert design().ou_named("PROD").accounts[0].email == "aws-management+payments-prod@acme.example"


def test_renamed_environment_names_its_ou_and_accounts():
    assert accounts_of("QA", environment_names={"stage": "QA"}) == ["acme-payments-qa", "acme-retail-qa"]


def test_prod_and_nonprod_parents_when_chosen():
    assert top_level(grouping="prod_nonprod")[2:5] == ["Sandbox", "NonProd", "Prod"]


def test_parents_hold_the_environment_ous():
    assert [ou.name for ou in design(grouping="prod_nonprod").ou_named("Prod").children] == ["STAGE", "PROD"]


def test_compliance_scope_gets_its_own_ou_with_stage_and_prod():
    assert [ou.name for ou in design(compliance=["PCI"]).ou_named("PCI").children] == ["PCI-STAGE", "PCI-PROD"]


def test_compliance_children_carry_their_environment():
    assert design(compliance=["PCI"]).ou_named("PCI-PROD").environment == "prod"


def test_cicd_gets_an_automations_ou_instead_of_an_infrastructure_account():
    structure = design(infrastructure=["network", "cicd"])
    assert ([account.name for account in structure.ou_named("Automations").accounts],
            [account.name for account in structure.ou_named("Infrastructure").accounts]) == (
        ["acme-cicd"], ["acme-network"])


def test_optional_ous_follow_the_answers():
    assert top_level(optional_ous=["individual_business_users"])[-2:] == ["Policy Staging", "Business Users"]


def test_environment_ous_are_listed_in_order():
    assert [ou.environment for ou in design().environment_ous()] == ["sandbox", "dev", "test", "stage", "prod"]


def test_every_account_is_listed_once():
    names = [account.name for account in design().accounts()]
    assert len(names) == len(set(names))


def test_unknown_ou_name_raises():
    import pytest
    with pytest.raises(KeyError):
        design().ou_named("Nope")


def test_questionnaire_accounts_are_fixed_and_workload_accounts_are_not():
    fixed = {ou.name: [account.fixed for account in ou.accounts] for ou in design(infrastructure=["network", "cicd"]).walk()}
    assert (fixed["Security"], fixed["Infrastructure"], fixed["Sandbox"], fixed["Automations"], fixed["PROD"]) == (
        [True, True, True], [True], [True, True], [True], [False, False])


def test_accounts_record_their_isolation_domain():
    structure = design()
    assert ([account.domain for account in structure.ou_named("PROD").accounts],
            [account.domain for account in structure.ou_named("Security").accounts]) == (["prod", "prod"], [None] * 3)
