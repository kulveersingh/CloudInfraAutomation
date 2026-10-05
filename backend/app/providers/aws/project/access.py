from app.synth.access import READ_LEVELS, WRITE_LEVELS

SAME_TAG_RESOURCE_CONDITION = {"StringEquals": {
    "aws:ResourceTag/org:project": "${aws:PrincipalTag/org:project}",
    "aws:ResourceTag/org:environment": "${aws:PrincipalTag/org:environment}",
}}


class AccessActions:
    """The IAM actions a service grants for read and write access levels."""

    def __init__(self, read: list[str], write: list[str]):
        self._read = read
        self._write = write

    def for_level(self, level: str) -> list[str]:
        actions = self._levelled(self._read, READ_LEVELS, level) + self._levelled(self._write, WRITE_LEVELS, level)
        return list(dict.fromkeys(actions))

    def _levelled(self, actions: list[str], levels: frozenset, level: str) -> list[str]:
        return list(actions) if level in levels else []
