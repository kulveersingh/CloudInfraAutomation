from app.providers.aws.releases import CloudFormationResourceClassifier
from app.releases.risk import ChangeRiskClassifier, RiskLevel, RiskRule
from tests.release_factories import change

CLASSIFIER = ChangeRiskClassifier.for_resources(CloudFormationResourceClassifier())


def test_code_change_is_low_risk():
    assert CLASSIFIER.risk_of(change()) == RiskLevel.LOW


def test_replacing_stateful_resource_is_high_risk():
    assert CLASSIFIER.risk_of(change("Modify", "AWS::DynamoDB::Table", replacement=True)) == RiskLevel.HIGH


def test_removing_stateful_resource_is_high_risk():
    assert CLASSIFIER.risk_of(change("Remove", "AWS::S3::Bucket")) == RiskLevel.HIGH


def test_adding_stateful_resource_is_low_risk():
    assert CLASSIFIER.risk_of(change("Add", "AWS::S3::Bucket")) == RiskLevel.LOW


def test_iam_change_is_medium_risk():
    assert CLASSIFIER.risk_of(change("Modify", "AWS::IAM::Role")) == RiskLevel.MEDIUM


def test_resource_policy_change_is_medium_risk():
    assert CLASSIFIER.risk_of(change("Modify", "AWS::S3::BucketPolicy")) == RiskLevel.MEDIUM


def test_removing_stateless_resource_is_medium_risk():
    assert CLASSIFIER.risk_of(change("Remove", "AWS::Lambda::Function")) == RiskLevel.MEDIUM


def test_overall_risk_is_the_highest():
    assert CLASSIFIER.overall([change(), change("Remove", "AWS::S3::Bucket")]) == RiskLevel.HIGH


def test_overall_risk_of_no_changes_is_low():
    assert CLASSIFIER.overall([]) == RiskLevel.LOW


def test_classified_changes_carry_their_risk():
    assert CLASSIFIER.classify([change()]) == [{
        "action": "Modify", "logical_id": "ProcessorFunction", "resource_type": "AWS::Lambda::Function",
        "replacement": False, "risk": "low"}]


def test_custom_rule_extends_classifier():
    class Everything(RiskRule):
        def risk_of(self, item):
            return RiskLevel.HIGH

    assert ChangeRiskClassifier([Everything()]).risk_of(change()) == RiskLevel.HIGH
