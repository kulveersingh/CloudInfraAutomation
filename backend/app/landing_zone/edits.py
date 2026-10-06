"""The OU tree editor: manual changes recorded as ordered edits and replayed on top of the designer's proposal."""

import re
from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from app.landing_zone.design import AccountPlan, LandingZoneDesign, OuNode

OU_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9 -]{1,39}$")
ACCOUNT_SUFFIX_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
CUSTOM_KEY_PREFIX = "custom_"
MOVE_OUT_FIRST = "Move its accounts and child OUs to another OU first."


class EditRefused(Exception):
    """An edit that doesn't fit the current tree; reported as a problem, never dropped silently."""


class EditPermissions:
    """Which edits each OU and account allows. The API publishes them so the UI shows only valid actions."""

    def for_ou(self, ou: OuNode) -> list[str]:
        edits = ["add_child", "add_account"] if self.takes_children(ou) else []
        edits += ["rename"] if ou.custom else []
        edits += ["move"] if ou.kind == "custom" else []
        edits += ["remove"] if ou.custom and ou.is_empty() else []
        return edits

    def blocked_for_ou(self, ou: OuNode) -> dict[str, str]:
        return {"remove": MOVE_OUT_FIRST} if ou.custom and not ou.is_empty() else {}

    def for_account(self, account: AccountPlan) -> list[str]:
        if account.fixed:
            return []
        return ["move", "disable" if account.enabled else "enable", *(["remove"] if account.added else [])]

    def takes_children(self, ou: OuNode) -> bool:
        return ou.custom or ou.kind == "infrastructure" or (ou.kind == "environment" and ou.tier != "sandbox")


class EditableTree:
    """The design being edited, with lookups that refuse unknown or protected targets."""

    def __init__(self, design: LandingZoneDesign):
        self.design = design
        self.namer = design.namer
        self.permissions = EditPermissions()

    def ou(self, key: str) -> OuNode:
        for ou in self.design.walk():
            if ou.key == key:
                return ou
        raise EditRefused(f"OU '{key}' does not exist.")

    def custom_ou(self, key: str) -> OuNode:
        ou = self.ou(key)
        if not ou.custom:
            raise EditRefused(f"OU '{ou.name}' comes from the questionnaire; change it there.")
        return ou

    def account(self, name: str) -> tuple[OuNode, AccountPlan]:
        for ou in self.design.walk():
            for account in ou.accounts:
                if account.name == name:
                    return ou, account
        raise EditRefused(f"Account '{name}' does not exist.")

    def editable_account(self, name: str) -> tuple[OuNode, AccountPlan]:
        ou, account = self.account(name)
        if account.fixed:
            raise EditRefused(f"Account '{name}' is set by the questionnaire.")
        return ou, account

    def swap_account(self, ou: OuNode, old: AccountPlan, new: AccountPlan) -> None:
        ou.accounts[ou.accounts.index(old)] = new

    def require_new_ou_name(self, name: str) -> None:
        if not OU_NAME_PATTERN.fullmatch(name):
            raise EditRefused("OU names are 2–40 letters, digits, spaces or hyphens, starting with a letter.")
        if any(ou.name == name or ou.key == custom_key(name) for ou in self.design.walk()):
            raise EditRefused(f"OU name '{name}' is already used.")

    def require_same_domain(self, subject: str, current: OuNode, target: OuNode) -> None:
        if current.isolation_domain != target.isolation_domain:
            home = self.ou(current.isolation_domain)
            raise EditRefused(f"{subject} can only move within '{home.name}'.")

    def siblings(self, ou: OuNode) -> list[OuNode]:
        """The list that holds the OU: its parent's children, or the root OUs."""
        for parent in self.design.walk():
            if ou in parent.children:
                return parent.children
        return self.design.root_ous


def custom_key(name: str) -> str:
    return CUSTOM_KEY_PREFIX + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


class TreeEdit(BaseModel, ABC):
    """One manual change. A new kind of change adds a subclass and registers it in AnyTreeEdit."""

    @abstractmethod
    def apply(self, tree: EditableTree) -> None:
        ...

    @abstractmethod
    def describe(self) -> str:
        ...


class AddOu(TreeEdit):
    op: Literal["add_ou"]
    parent: str | None
    name: str

    def describe(self) -> str:
        return f"add OU '{self.name}' under '{self.parent or 'root'}'"

    def apply(self, tree: EditableTree) -> None:
        tree.require_new_ou_name(self.name)
        if self.parent is None:
            tree.design.root_ous.append(OuNode(key=custom_key(self.name), name=self.name, kind="custom_domain", custom=True))
            return
        parent = tree.ou(self.parent)
        if not tree.permissions.takes_children(parent):
            raise EditRefused(f"OU '{parent.name}' doesn't allow child OUs.")
        parent.children.append(OuNode(key=custom_key(self.name), name=self.name, kind="custom", custom=True,
                                      environment=parent.environment, tier=parent.tier,
                                      domain=parent.isolation_domain))


class RenameOu(TreeEdit):
    op: Literal["rename_ou"]
    ou: str
    name: str

    def describe(self) -> str:
        return f"rename '{self.ou}' to '{self.name}'"

    def apply(self, tree: EditableTree) -> None:
        ou = tree.custom_ou(self.ou)
        tree.require_new_ou_name(self.name)
        ou.name = self.name


class MoveOu(TreeEdit):
    op: Literal["move_ou"]
    ou: str
    parent: str

    def describe(self) -> str:
        return f"move '{self.ou}' under '{self.parent}'"

    def apply(self, tree: EditableTree) -> None:
        ou = tree.custom_ou(self.ou)
        if "move" not in tree.permissions.for_ou(ou):
            raise EditRefused(f"OU '{ou.name}' stays at the root.")
        target = tree.ou(self.parent)
        tree.require_same_domain(f"OU '{ou.name}'", ou, target)
        if target is ou or target in ou.descendants():
            raise EditRefused(f"OU '{ou.name}' can't move inside itself.")
        tree.siblings(ou).remove(ou)
        target.children.append(ou)


class RemoveOu(TreeEdit):
    op: Literal["remove_ou"]
    ou: str

    def describe(self) -> str:
        return f"remove '{self.ou}'"

    def apply(self, tree: EditableTree) -> None:
        ou = tree.custom_ou(self.ou)
        if not ou.is_empty():
            raise EditRefused(f"OU '{ou.name}' isn't empty. {MOVE_OUT_FIRST}")
        tree.siblings(ou).remove(ou)


class AddAccount(TreeEdit):
    op: Literal["add_account"]
    ou: str
    suffix: str

    def describe(self) -> str:
        return f"add account '{self.suffix}' to '{self.ou}'"

    def apply(self, tree: EditableTree) -> None:
        if not ACCOUNT_SUFFIX_PATTERN.fullmatch(self.suffix):
            raise EditRefused("Account suffixes are 2–40 lowercase letters, digits or hyphens.")
        ou = tree.ou(self.ou)
        if "add_account" not in tree.permissions.for_ou(ou):
            raise EditRefused(f"OU '{ou.name}' doesn't allow new accounts.")
        account = replace(tree.namer.added(self.suffix), domain=ou.isolation_domain)
        if any(existing.name == account.name for existing in tree.design.walk_accounts()):
            raise EditRefused(f"Account '{account.name}' already exists.")
        ou.accounts.append(account)


class DisableAccount(TreeEdit):
    op: Literal["disable_account"]
    account: str

    def describe(self) -> str:
        return f"disable '{self.account}'"

    def apply(self, tree: EditableTree) -> None:
        ou, account = tree.editable_account(self.account)
        if not account.enabled:
            raise EditRefused(f"Account '{account.name}' is already disabled.")
        tree.swap_account(ou, account, replace(account, enabled=False))


class EnableAccount(TreeEdit):
    op: Literal["enable_account"]
    account: str

    def describe(self) -> str:
        return f"enable '{self.account}'"

    def apply(self, tree: EditableTree) -> None:
        ou, account = tree.account(self.account)
        if account.enabled:
            raise EditRefused(f"Account '{account.name}' isn't disabled.")
        tree.swap_account(ou, account, replace(account, enabled=True))


class RemoveAccount(TreeEdit):
    op: Literal["remove_account"]
    account: str

    def describe(self) -> str:
        return f"remove '{self.account}'"

    def apply(self, tree: EditableTree) -> None:
        ou, account = tree.account(self.account)
        if not account.added:
            raise EditRefused(f"Account '{account.name}' was generated; disable it instead.")
        ou.accounts.remove(account)


class MoveAccount(TreeEdit):
    op: Literal["move_account"]
    account: str
    ou: str

    def describe(self) -> str:
        return f"move '{self.account}' to '{self.ou}'"

    def apply(self, tree: EditableTree) -> None:
        current, account = tree.editable_account(self.account)
        target = tree.ou(self.ou)
        tree.require_same_domain(f"Account '{account.name}'", current, target)
        current.accounts.remove(account)
        target.accounts.append(account)


# The registry of edits, keyed by "op": a new kind of change joins this union.
AnyTreeEdit = Annotated[AddOu | RenameOu | MoveOu | RemoveOu | AddAccount | DisableAccount | EnableAccount | RemoveAccount
                        | MoveAccount, Field(discriminator="op")]


class TreeEditor:
    """Replays the edits in order; each one that no longer fits becomes a numbered problem."""

    _edits = TypeAdapter(list[AnyTreeEdit])

    @classmethod
    def parse(cls, raw: list[dict]) -> list[TreeEdit]:
        return cls._edits.validate_python(raw)

    @classmethod
    def dump(cls, edits: list[TreeEdit]) -> list[dict]:
        return cls._edits.dump_python(edits, mode="json")

    def apply(self, design: LandingZoneDesign, edits: list[TreeEdit]) -> list[str]:
        tree = EditableTree(design)
        problems = []
        for position, edit in enumerate(edits, start=1):
            try:
                edit.apply(tree)
            except EditRefused as refusal:
                problems.append(f"Edit {position} ({edit.describe()}): {refusal}")
        return problems
