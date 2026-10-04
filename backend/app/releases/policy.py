from dataclasses import dataclass

from app.errors import ForbiddenError

ANONYMOUS = "local-user"


class Role:
    REVIEWER = "reviewer"
    PLATFORM_ADMIN = "platform-admin"


@dataclass(frozen=True)
class Actor:
    """Who is acting. Comes from SSO in production; from X-Actor / X-Roles headers locally."""

    name: str
    roles: frozenset[str]

    @classmethod
    def from_headers(cls, name: str | None, roles: str | None) -> "Actor":
        parsed = frozenset(role.strip() for role in (roles or "").split(",") if role.strip())
        return cls(name or ANONYMOUS, parsed)

    def has_role(self, role: str) -> bool:
        return role in self.roles


class ApprovalPolicy:
    """Who may decide on a release: reviewers approve, platform admins approve overrides, never your own."""

    def check_reviewer(self, actor: Actor, release) -> None:
        self._require_role(actor, Role.REVIEWER, "Only reviewers can approve or reject releases.")
        self._forbid_self(actor, release)

    def check_override(self, actor: Actor, release) -> None:
        self._require_role(actor, Role.PLATFORM_ADMIN, "Only a platform admin can approve an override.")
        self._forbid_self(actor, release)

    def _require_role(self, actor: Actor, role: str, message: str) -> None:
        if not actor.has_role(role):
            raise ForbiddenError(message)

    def _forbid_self(self, actor: Actor, release) -> None:
        if actor.name == release.requested_by:
            raise ForbiddenError("You requested this release, so you cannot decide on it.")
