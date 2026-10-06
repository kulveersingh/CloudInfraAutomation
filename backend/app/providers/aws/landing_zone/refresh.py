"""Refreshes the control catalog snapshot from the AWS Control Catalog API (read-only):

    uv run --with boto3 python -m app.providers.aws.landing_zone.refresh

Updates names and severities (ListControls), records each control's framework mappings (ListControlMappings) and
resolves the CloudFormation-hooks prerequisite that proactive controls need, by its CT.CLOUDFORMATION.PR.1 alias.
"""

from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

from app.landing_zone.catalog.controls import CatalogControl, ControlCatalogSnapshot, renamed
from app.providers.aws.landing_zone.controls import SNAPSHOT_PATH, aws_snapshot, control_identifier

HOOKS_ALIAS = "CT.CLOUDFORMATION.PR.1"
HEADER = ("# Control Catalog snapshot: the controls the AWS pack mappings use. Refresh with\n"
          "#   uv run --with boto3 python -m app.providers.aws.landing_zone.refresh\n"
          "# which also fills each control's framework mappings (ListControlMappings) and the id of the\n"
          "# CloudFormation-hooks prerequisite (CT.CLOUDFORMATION.PR.1) that proactive controls need.\n")
SOURCE = "AWS Control Catalog: ListControls and ListControlMappings"


class ControlCatalogRefresher:
    def __init__(self, client, today: str):
        self._client = client
        self._today = today

    def refresh(self, snapshot: ControlCatalogSnapshot, path: Path) -> None:
        catalog = {summary["Arn"]: summary for summary in self._pages(self._client.list_controls, "Controls")}
        frameworks = self._frameworks([control_identifier(control.id) for control in snapshot.controls.values()])
        controls = {control.id: renamed(control, catalog[control_identifier(control.id)], frameworks[control_identifier(control.id)])
                    for control in snapshot.controls.values() if control_identifier(control.id) in catalog}
        snapshot.refreshed(controls, self._hooks_prerequisite(catalog), self._today, SOURCE).write(path, HEADER)

    def _frameworks(self, arns: list[str]) -> dict[str, set[str]]:
        found: dict[str, set[str]] = defaultdict(set)
        mappings = self._pages(lambda **token: self._client.list_control_mappings(
            Filter={"ControlArns": arns, "MappingTypes": ["FRAMEWORK"]}, **token), "ControlMappings")
        for mapping in mappings:
            found[mapping["ControlArn"]].add(mapping["Mapping"]["Framework"]["Name"])
        return found

    def _hooks_prerequisite(self, catalog: dict[str, dict]) -> CatalogControl | None:
        for arn, summary in catalog.items():
            if HOOKS_ALIAS in summary.get("Aliases", []):
                return CatalogControl(id=arn.rsplit("/", 1)[1], name=summary["Name"], behavior=summary["Behavior"],
                                      severity=summary["Severity"], implementation="SCP")
        return None

    @staticmethod
    def _pages(call: Callable[..., dict], key: str) -> Iterator[dict]:
        token: dict = {}
        while True:
            page = call(**token)
            yield from page[key]
            if "NextToken" not in page:
                return
            token = {"NextToken": page["NextToken"]}


if __name__ == "__main__":
    import boto3

    ControlCatalogRefresher(boto3.client("controlcatalog"), datetime.now(UTC).date().isoformat()).refresh(
        aws_snapshot(), SNAPSHOT_PATH)
