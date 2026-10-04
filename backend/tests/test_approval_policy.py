from types import SimpleNamespace

import pytest

from app.errors import ForbiddenError
from app.releases.policy import Actor, ApprovalPolicy

POLICY = ApprovalPolicy()
RELEASE = SimpleNamespace(requested_by="jordan")


def test_reviewer_may_decide():
    assert POLICY.check_reviewer(Actor("sam", frozenset({"reviewer"})), RELEASE) is None


def test_non_reviewer_may_not_decide():
    with pytest.raises(ForbiddenError, match="Only reviewers can approve or reject releases."):
        POLICY.check_reviewer(Actor("pat", frozenset({"developer"})), RELEASE)


def test_requester_may_not_decide():
    with pytest.raises(ForbiddenError, match="You requested this release, so you cannot decide on it."):
        POLICY.check_reviewer(Actor("jordan", frozenset({"reviewer"})), RELEASE)


def test_platform_admin_may_approve_override():
    assert POLICY.check_override(Actor("alex", frozenset({"platform-admin"})), RELEASE) is None


def test_reviewer_may_not_approve_override():
    with pytest.raises(ForbiddenError, match="Only a platform admin can approve an override."):
        POLICY.check_override(Actor("sam", frozenset({"reviewer"})), RELEASE)


def test_requester_may_not_approve_own_override():
    with pytest.raises(ForbiddenError, match="cannot decide on it"):
        POLICY.check_override(Actor("jordan", frozenset({"platform-admin"})), RELEASE)


def test_actor_from_headers():
    actor = Actor.from_headers("sam", "reviewer, developer")
    assert (actor.name, actor.roles) == ("sam", frozenset({"reviewer", "developer"}))


def test_anonymous_actor_has_no_roles():
    actor = Actor.from_headers(None, None)
    assert (actor.name, actor.roles) == ("local-user", frozenset())


def test_actor_role_check():
    assert Actor("sam", frozenset({"reviewer"})).has_role("reviewer")
