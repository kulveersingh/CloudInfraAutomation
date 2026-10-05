from app.errors import ForbiddenError
from app.releases.policy import Actor, Role

PLATFORM_ADMIN = "platform-admin"
REVIEWER = "reviewer"
ROLE_NAMES = {PLATFORM_ADMIN: "a platform admin", REVIEWER: "a reviewer"}


def approver_role(requires_approval: bool) -> str:
    """STAGE and PROD (environments that need release approval) need a platform admin to tear down (§21.9 TD1)."""
    return PLATFORM_ADMIN if requires_approval else REVIEWER


class TeardownPolicy:
    """Who decides: never the requester; a reviewer or platform admin for most environments, only a platform admin
    for STAGE and PROD."""

    def require_approver(self, actor: Actor, role: str, requested_by: str | None, subject: str,
                         self_message: str) -> None:
        if actor.name == requested_by:
            raise ForbiddenError(self_message)
        allowed = {Role.PLATFORM_ADMIN} if role == PLATFORM_ADMIN else {Role.PLATFORM_ADMIN, Role.REVIEWER}
        if not any(actor.has_role(item) for item in allowed):
            raise ForbiddenError(f"Only {ROLE_NAMES[role]} can approve {subject}.")
