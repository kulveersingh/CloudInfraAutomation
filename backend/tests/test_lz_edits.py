import pytest
from pydantic import ValidationError

from app.landing_zone.edits import EditPermissions, TreeEditor
from tests.lz_factories import account_op, add_account, add_ou, edited

PAYMENTS = add_ou("Payments")
DATA_LAB = add_ou("Data Lab", parent=None)


def names(ous) -> list[str]:
    return [ou.name for ou in ous]


def account_names(design, ou_name: str) -> list[str]:
    return [account.name for account in design.ou_named(ou_name).accounts]


# ---- add_ou ----

def test_add_ou_inside_an_environment():
    design, problems = edited([PAYMENTS])
    assert (names(design.ou_named("PROD").children), problems) == (["Payments"], [])


def test_child_ou_inherits_the_environment():
    payments = edited([PAYMENTS])[0].ou_named("Payments")
    assert (payments.kind, payments.custom, payments.environment, payments.tier, payments.isolation_domain) == (
        "custom", True, "prod", "prod", "prod")


def test_custom_ou_key_is_a_slug_of_its_name():
    assert edited([DATA_LAB])[0].ou_named("Data Lab").key == "custom_data_lab"


def test_add_ou_at_the_root_starts_its_own_isolation_domain():
    data_lab = edited([DATA_LAB])[0].root_ous[-1]
    assert (data_lab.name, data_lab.kind, data_lab.isolation_domain) == ("Data Lab", "custom_domain", "custom_data_lab")


def test_add_ou_under_infrastructure():
    design, _ = edited([add_ou("Networking", parent="infrastructure")])
    assert design.ou_named("Networking").isolation_domain == "infrastructure"


def test_add_ou_under_a_custom_ou():
    design, _ = edited([PAYMENTS, add_ou("Cards", parent="custom_payments")])
    assert names(design.ou_named("Payments").children) == ["Cards"]


@pytest.mark.parametrize("parent, name", [("security", "Security"), ("sandbox", "Sandbox"),
                                          ("policy_staging", "Policy Staging")])
def test_add_ou_refused_under_fixed_ous(parent, name):
    assert edited([add_ou("Extra", parent=parent)])[1] == [
        f"Edit 1 (add OU 'Extra' under '{parent}'): OU '{name}' doesn't allow child OUs."]


def test_add_ou_refused_for_a_used_name():
    assert edited([add_ou("PROD", parent=None)])[1] == ["Edit 1 (add OU 'PROD' under 'root'): OU name 'PROD' is already used."]


def test_add_ou_refused_for_an_invalid_name():
    assert edited([add_ou("x")])[1] == [
        "Edit 1 (add OU 'x' under 'prod'): OU names are 2–40 letters, digits, spaces or hyphens, starting with a letter."]


def test_add_ou_refused_under_an_unknown_parent():
    assert edited([add_ou("Extra", parent="nope")])[1] == ["Edit 1 (add OU 'Extra' under 'nope'): OU 'nope' does not exist."]


# ---- rename_ou ----

def test_rename_a_custom_ou():
    design, _ = edited([PAYMENTS, {"op": "rename_ou", "ou": "custom_payments", "name": "Cards"}])
    assert (names(design.ou_named("PROD").children), design.ou_named("Cards").key) == (["Cards"], "custom_payments")


def test_questionnaire_ous_cannot_be_renamed():
    assert edited([{"op": "rename_ou", "ou": "prod", "name": "LIVE"}])[1] == [
        "Edit 1 (rename 'prod' to 'LIVE'): OU 'PROD' comes from the questionnaire; change it there."]


def test_rename_refused_for_a_used_name():
    problems = edited([PAYMENTS, {"op": "rename_ou", "ou": "custom_payments", "name": "DEV"}])[1]
    assert problems == ["Edit 2 (rename 'custom_payments' to 'DEV'): OU name 'DEV' is already used."]


# ---- move_ou ----

def test_move_a_custom_ou_within_its_environment():
    design, _ = edited([PAYMENTS, add_ou("Cards"), {"op": "move_ou", "ou": "custom_cards", "parent": "custom_payments"}])
    assert (names(design.ou_named("PROD").children), names(design.ou_named("Payments").children)) == (
        ["Payments"], ["Cards"])


def test_move_refused_across_isolation_domains():
    problems = edited([PAYMENTS, {"op": "move_ou", "ou": "custom_payments", "parent": "dev"}])[1]
    assert problems == ["Edit 2 (move 'custom_payments' under 'dev'): OU 'Payments' can only move within 'PROD'."]


def test_move_refused_into_itself():
    problems = edited([PAYMENTS, add_ou("Cards", parent="custom_payments"),
                       {"op": "move_ou", "ou": "custom_payments", "parent": "custom_cards"}])[1]
    assert problems == ["Edit 3 (move 'custom_payments' under 'custom_cards'): OU 'Payments' can't move inside itself."]


def test_root_level_custom_ous_stay_at_the_root():
    problems = edited([DATA_LAB, add_ou("Lab B", parent=None),
                       {"op": "move_ou", "ou": "custom_data_lab", "parent": "custom_lab_b"}])[1]
    assert problems == ["Edit 3 (move 'custom_data_lab' under 'custom_lab_b'): OU 'Data Lab' stays at the root."]


def test_questionnaire_ous_cannot_be_moved():
    assert edited([{"op": "move_ou", "ou": "dev", "parent": "prod"}])[1] == [
        "Edit 1 (move 'dev' under 'prod'): OU 'DEV' comes from the questionnaire; change it there."]


# ---- remove_ou ----

def test_remove_an_empty_custom_ou():
    design, _ = edited([PAYMENTS, {"op": "remove_ou", "ou": "custom_payments"}])
    assert design.ou_named("PROD").children == []


def test_remove_a_root_level_custom_ou():
    design, _ = edited([DATA_LAB, {"op": "remove_ou", "ou": "custom_data_lab"}])
    assert "Data Lab" not in names(design.root_ous)


def test_remove_refused_until_accounts_are_moved_out():
    problems = edited([PAYMENTS, account_op("move_account", "acme-retail-prod", ou="custom_payments"),
                       {"op": "remove_ou", "ou": "custom_payments"}])[1]
    assert problems == [("Edit 3 (remove 'custom_payments'): OU 'Payments' isn't empty. "
                         "Move its accounts and child OUs to another OU first.")]


def test_remove_refused_until_child_ous_are_moved_out():
    problems = edited([PAYMENTS, add_ou("Cards", parent="custom_payments"), {"op": "remove_ou", "ou": "custom_payments"}])[1]
    assert problems[0].endswith("Move its accounts and child OUs to another OU first.")


def test_questionnaire_ous_cannot_be_removed():
    assert edited([{"op": "remove_ou", "ou": "exceptions"}])[1] == [
        "Edit 1 (remove 'exceptions'): OU 'Exceptions' comes from the questionnaire; change it there."]


# ---- add_account ----

def test_add_an_account():
    design, _ = edited([PAYMENTS, add_account("cards-prod", "custom_payments")])
    account = design.ou_named("Payments").accounts[0]
    assert (account.name, account.email, account.added, account.enabled) == (
        "acme-cards-prod", "aws-management+cards-prod@acme.example", True, True)


def test_add_an_account_to_a_root_level_custom_ou():
    design, _ = edited([DATA_LAB, add_account("data-lab", "custom_data_lab")])
    assert account_names(design, "Data Lab") == ["acme-data-lab"]


def test_add_account_refused_in_fixed_ous():
    assert edited([add_account("siem", "security")])[1] == [
        "Edit 1 (add account 'siem' to 'security'): OU 'Security' doesn't allow new accounts."]


def test_add_account_refused_for_an_existing_name():
    assert edited([add_account("retail-prod", "prod")])[1] == [
        "Edit 1 (add account 'retail-prod' to 'prod'): Account 'acme-retail-prod' already exists."]


def test_add_account_refused_for_an_invalid_suffix():
    assert edited([add_account("Bad_Name", "prod")])[1] == [
        "Edit 1 (add account 'Bad_Name' to 'prod'): Account suffixes are 2–40 lowercase letters, digits or hyphens."]


# ---- disable_account / enable_account ----

def test_disable_keeps_the_account_in_its_ou():
    design, _ = edited([account_op("disable_account", "acme-retail-prod")])
    retail = design.ou_named("PROD").accounts[1]
    assert (retail.name, retail.enabled) == ("acme-retail-prod", False)


def test_disabled_accounts_are_not_vended():
    design, _ = edited([account_op("disable_account", "acme-retail-prod")])
    assert "acme-retail-prod" not in [account.name for account in design.accounts()]


def test_fixed_accounts_cannot_be_disabled():
    assert edited([account_op("disable_account", "acme-audit")])[1] == [
        "Edit 1 (disable 'acme-audit'): Account 'acme-audit' is set by the questionnaire."]


def test_disable_refused_twice():
    problems = edited([account_op("disable_account", "acme-retail-prod"), account_op("disable_account", "acme-retail-prod")])[1]
    assert problems == ["Edit 2 (disable 'acme-retail-prod'): Account 'acme-retail-prod' is already disabled."]


def test_enable_a_disabled_account():
    design, _ = edited([account_op("disable_account", "acme-retail-prod"), account_op("enable_account", "acme-retail-prod")])
    assert design.ou_named("PROD").accounts[1].enabled is True


def test_enable_refused_for_an_enabled_account():
    assert edited([account_op("enable_account", "acme-retail-prod")])[1] == [
        "Edit 1 (enable 'acme-retail-prod'): Account 'acme-retail-prod' isn't disabled."]


# ---- remove_account ----

def test_remove_an_added_account():
    design, _ = edited([add_account("cards-prod", "prod"), account_op("remove_account", "acme-cards-prod")])
    assert account_names(design, "PROD") == ["acme-payments-prod", "acme-retail-prod"]


def test_generated_accounts_are_disabled_not_removed():
    assert edited([account_op("remove_account", "acme-retail-prod")])[1] == [
        "Edit 1 (remove 'acme-retail-prod'): Account 'acme-retail-prod' was generated; disable it instead."]


def test_unknown_account():
    assert edited([account_op("remove_account", "acme-nope")])[1] == [
        "Edit 1 (remove 'acme-nope'): Account 'acme-nope' does not exist."]


# ---- move_account ----

def test_move_an_account_into_a_child_ou():
    design, _ = edited([PAYMENTS, account_op("move_account", "acme-payments-prod", ou="custom_payments")])
    assert (account_names(design, "Payments"), account_names(design, "PROD")) == (
        ["acme-payments-prod"], ["acme-retail-prod"])


def test_move_account_refused_across_isolation_domains():
    assert edited([account_op("move_account", "acme-payments-prod", ou="dev")])[1] == [
        "Edit 1 (move 'acme-payments-prod' to 'dev'): Account 'acme-payments-prod' can only move within 'PROD'."]


def test_fixed_accounts_cannot_be_moved():
    problems = edited([add_ou("Networking", parent="infrastructure"),
                       account_op("move_account", "acme-network", ou="custom_networking")])[1]
    assert problems == ["Edit 2 (move 'acme-network' to 'custom_networking'): Account 'acme-network' is set by the questionnaire."]


# ---- replay ----

def test_stale_edits_are_reported_and_the_rest_still_apply():
    design, problems = edited([add_ou("Acceptance", parent="uat"), PAYMENTS])
    assert (problems, names(design.ou_named("PROD").children)) == (
        ["Edit 1 (add OU 'Acceptance' under 'uat'): OU 'uat' does not exist."], ["Payments"])


def test_unknown_operations_are_rejected():
    with pytest.raises(ValidationError):
        TreeEditor.parse([{"op": "explode"}])


def test_edits_serialize_back_to_their_request_shape():
    assert TreeEditor.dump(TreeEditor.parse([PAYMENTS])) == [PAYMENTS]


# ---- what the editor offers ----

def ou_edits(edits: list[dict], name: str) -> tuple[list[str], dict]:
    ou = edited(edits)[0].ou_named(name)
    return EditPermissions().for_ou(ou), EditPermissions().blocked_for_ou(ou)


@pytest.mark.parametrize("name", ["PROD", "Infrastructure"])
def test_environment_and_infrastructure_ous_take_child_ous_and_accounts(name):
    assert ou_edits([], name) == (["add_child", "add_account"], {})


@pytest.mark.parametrize("name", ["Security", "Sandbox", "Policy Staging", "Suspended"])
def test_questionnaire_only_ous_offer_nothing(name):
    assert ou_edits([], name) == ([], {})


def test_an_empty_custom_ou_offers_every_edit():
    assert ou_edits([PAYMENTS], "Payments") == (["add_child", "add_account", "rename", "move", "remove"], {})


def test_a_root_level_custom_ou_cannot_move():
    assert ou_edits([DATA_LAB], "Data Lab")[0] == ["add_child", "add_account", "rename", "remove"]


def test_a_non_empty_custom_ou_explains_why_it_cannot_be_removed():
    assert ou_edits([PAYMENTS, add_account("cards-prod", "custom_payments")], "Payments") == (
        ["add_child", "add_account", "rename", "move"], {"remove": "Move its accounts and child OUs to another OU first."})


def account_edits(edits: list[dict], ou: str, index: int) -> list[str]:
    return EditPermissions().for_account(edited(edits)[0].ou_named(ou).accounts[index])


def test_generated_workload_accounts_can_move_or_be_disabled():
    assert account_edits([], "PROD", 0) == ["move", "disable"]


def test_disabled_accounts_can_be_enabled():
    assert account_edits([account_op("disable_account", "acme-payments-prod")], "PROD", 0) == ["move", "enable"]


def test_added_accounts_can_also_be_removed():
    assert account_edits([add_account("cards-prod", "prod")], "PROD", 2) == ["move", "disable", "remove"]


@pytest.mark.parametrize("ou", ["Security", "Infrastructure", "Sandbox"])
def test_questionnaire_accounts_offer_nothing(ou):
    assert account_edits([], ou, 0) == []
