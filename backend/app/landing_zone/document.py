from app.landing_zone.design import LandingZoneDesign, OuNode
from app.landing_zone.edits import TreeEditor


def design_document(design: LandingZoneDesign) -> dict:
    """`design.json` in a landing-zone repository: the answers, the tree editor's changes and the resulting tree,
    which read-back (§21) starts from."""
    return {"answers": design.answers.model_dump(mode="json"), "edits": TreeEditor.dump(design.edits),
            "ous": [_node(ou) for ou in design.root_ous]}


def _node(ou: OuNode) -> dict:
    return {"name": ou.name, "kind": ou.kind, "environment": ou.environment,
            "accounts": [account.name for account in ou.accounts], "children": [_node(child) for child in ou.children]}
