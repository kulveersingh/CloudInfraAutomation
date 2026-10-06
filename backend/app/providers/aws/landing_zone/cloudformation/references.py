from app.landing_zone.design import LandingZoneDesign, OuNode

CONTROL_TOWER_PARAMETERS = {"security": "SecurityOuId", "sandbox": "SandboxOuId"}
OU_ID_PATTERN = r"^ou-[0-9a-z]{4,32}-[a-z0-9]{8,32}$"


def pascal(key: str) -> str:
    return "".join(part.capitalize() for part in key.replace("-", "_").split("_"))


def ou_logical_id(ou: OuNode) -> str:
    return f"Ou{pascal(ou.key)}"


class Exports:
    """Names of the cross-stack exports, prefixed with the organization name."""

    def __init__(self, organization: str):
        self._prefix = f"{organization}-lz"

    def name(self, suffix: str) -> str:
        return f"{self._prefix}-{suffix}"

    def value(self, suffix: str) -> dict:
        return {"Fn::ImportValue": self.name(suffix)}


class OuReferences:
    """How each OU is referenced: created OUs by logical id, Control Tower OUs through parameters."""

    def __init__(self, design: LandingZoneDesign):
        self._design = design
        self._parents = {child.key: ou for ou in design.walk() for child in ou.children}
        self.exports = Exports(design.answers.organization_name)

    def name_in_template(self, ou: OuNode) -> str:
        """Parameter name for Control Tower OUs, logical id otherwise; both work as ${...} in Fn::Sub."""
        if ou.created_by_service:
            return CONTROL_TOWER_PARAMETERS[ou.kind if ou.kind == "security" else "sandbox"]
        return ou_logical_id(ou)

    def id(self, ou: OuNode) -> dict:
        return {"Ref": self.name_in_template(ou)}

    def imported_id(self, ou: OuNode) -> dict:
        """The OU id from another stack: parameter for Control Tower OUs, export of lz-structure otherwise."""
        if ou.created_by_service:
            return {"Ref": self.name_in_template(ou)}
        return self.exports.value(f"{ou_logical_id(ou)}Id")

    def arn(self, ou: OuNode) -> dict:
        if ou.created_by_service:
            return {"Fn::Sub": [f"arn:aws:organizations::${{AWS::AccountId}}:ou/${{OrgId}}/${{{self.name_in_template(ou)}}}",
                                {"OrgId": self.exports.value("OrganizationId")}]}
        return {"Fn::GetAtt": [ou_logical_id(ou), "Arn"]}

    def parent_id(self, ou: OuNode) -> dict:
        parent = self._parents.get(ou.key)
        return self.id(parent) if parent else self.exports.value("RootId")

    def ancestors(self, ou: OuNode) -> list[OuNode]:
        chain = [ou]
        while chain[0].key in self._parents:
            chain.insert(0, self._parents[chain[0].key])
        return chain

    def path(self, ou: OuNode) -> dict:
        """aws:PrincipalOrgPaths / aws:ResourceOrgPaths pattern for everything at or below the OU."""
        segments = "/".join(f"${{{self.name_in_template(item)}}}" for item in self.ancestors(ou))
        return {"Fn::Sub": [f"${{OrgId}}/${{RootId}}/{segments}/*",
                            {"OrgId": self.exports.value("OrganizationId"), "RootId": self.exports.value("RootId")}]}
