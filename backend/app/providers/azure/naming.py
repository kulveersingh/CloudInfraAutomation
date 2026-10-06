"""Names the platform gives an Azure project outside its templates."""


def resource_group(project: str, environment: str) -> str:
    return f"rg-{project}-{environment}"


def resource_group_id(subscription: str, project: str, environment: str) -> str:
    return f"/subscriptions/{subscription}/resourceGroups/{resource_group(project, environment)}"
