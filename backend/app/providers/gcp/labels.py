import re

from app.providers.base import TagPolicy

MAX_LENGTH = 63
NOT_ALLOWED = re.compile(r"[^a-z0-9_-]")


class LabelPolicy(TagPolicy):
    """Google Cloud labels: lowercase letters, digits, _ and -, at most 63 characters; keys can't hold ':'."""

    def format(self, tags):
        return {self.key(name): self.value(value) for name, value in tags.items()}

    def key(self, name: str) -> str:
        return NOT_ALLOWED.sub("_", name.lower().replace("-", "_"))[:MAX_LENGTH]

    def value(self, value: str) -> str:
        return NOT_ALLOWED.sub("-", value.lower())[:MAX_LENGTH]
