from dataclasses import dataclass, field
from html import escape

from app.landing_zone.design import LandingZoneDesign, OuNode

ENVIRONMENT_KINDS = frozenset({"environment", "parent", "compliance"})
MAX_ACCOUNTS_SHOWN = 3
COLORS = {"root": "#16222B", "security": "#B3261E", "infrastructure": "#2C5AA0", "automations": "#2C5AA0",
          "parent": "#53636E", "compliance": "#B26A00", "suspended": "#7C8B95"}
TIER_COLORS = {"sandbox": "#2C5AA0", "nonprod": "#0B6E79", "prod": "#B26A00"}
DEFAULT_COLOR = "#7C8B95"
LINE_COLOR = "#B4BFC6"
BOX_WIDTH, GAP, LINE, PAD, VERTICAL_GAP, MARGIN, SIDE_X = 176, 14, 15, 10, 40, 24, 10
FONT = 'font-family="IBM Plex Sans,Arial,sans-serif"'
MONO = 'font-family="IBM Plex Mono,monospace"'


class OuDiagramRenderer:
    """Draws the approved OU structure: Mermaid source and a standalone SVG (root, foundation row, environments row)."""

    def mermaid(self, design: LandingZoneDesign) -> str:
        lines = ["flowchart TD", f'  root["Root · {design.answers.organization_name}<br/>Management / payer account"]']
        for ou in design.root_ous:
            lines += self._mermaid_node(ou, "root")
        return "\n".join(lines) + "\n"

    def _mermaid_node(self, ou: OuNode, parent: str) -> list[str]:
        label = "<br/>".join([ou.label, *(account.name for account in ou.accounts[:MAX_ACCOUNTS_SHOWN])])
        lines = [f'  {ou.key}["{label}"]', f"  {parent} --> {ou.key}"]
        for child in ou.children:
            lines += self._mermaid_node(child, ou.key)
        return lines

    def svg(self, design: LandingZoneDesign) -> str:
        return SvgLayout(design).render()


@dataclass
class _Box:
    ou: OuNode | None
    label: str
    items: list[str]
    color: str
    children: list["_Box"] = field(default_factory=list)
    x: float = 0
    depth: int = 0

    @property
    def height(self) -> int:
        return PAD * 2 + 18 + len(self.items) * LINE


class SvgLayout:
    """Tidy-tree layout per row; parents are centred over their children."""

    def __init__(self, design: LandingZoneDesign):
        self._design = design
        self._parts: list[str] = []

    def render(self) -> str:
        rows = [("FOUNDATION", [ou for ou in self._design.root_ous if ou.kind not in ENVIRONMENT_KINDS]),
                ("ENVIRONMENTS (ISOLATED)", [ou for ou in self._design.root_ous if ou.kind in ENVIRONMENT_KINDS])]
        laid = [(title, *self._layout([self._box(ou) for ou in nodes])) for title, nodes in rows]
        width = max(row_width for _, _, row_width, _ in laid) + MARGIN * 2
        root = _Box(None, f"Root · {self._design.answers.organization_name}",
                    ["Management / payer", f"Control Tower {self._design.answers.home_region}"], COLORS["root"])
        trunk_x, top = width / 2, 20 + root.height
        y, buses = top + VERTICAL_GAP, []
        for title, boxes, row_width, levels in laid:
            bus_y = y + 18
            buses.append(bus_y)
            y = self._row(title, boxes, (width - row_width) / 2, y, bus_y, levels, trunk_x)
        self._line(f"M{trunk_x} {top} V{buses[0]}")
        self._line(f"M{SIDE_X} {buses[0]} V{buses[-1]}")
        self._draw_box(root, (width - BOX_WIDTH) / 2, 20)
        height = y + 8
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
                f'viewBox="0 0 {width:g} {height:g}" role="img" aria-label="OU structure">'
                f'<rect width="100%" height="100%" fill="#F3F5F6"/>{"".join(self._parts)}</svg>')

    def _box(self, ou: OuNode) -> _Box:
        color = TIER_COLORS.get(ou.tier, DEFAULT_COLOR) if ou.kind == "environment" else COLORS.get(ou.kind, DEFAULT_COLOR)
        items = [account.name for account in ou.accounts[:MAX_ACCOUNTS_SHOWN]]
        return _Box(ou, ou.label, items, color, [self._box(child) for child in ou.children])

    def _layout(self, boxes: list[_Box]) -> tuple[list[_Box], float, list[int]]:
        cursor, levels = [0.0], []

        def place(box: _Box, depth: int) -> None:
            box.depth = depth
            levels.extend([0] * (depth + 1 - len(levels)))
            levels[depth] = max(levels[depth], box.height)
            if not box.children:
                box.x, cursor[0] = cursor[0], cursor[0] + BOX_WIDTH + GAP
                return
            for child in box.children:
                place(child, depth + 1)
            box.x = (box.children[0].x + box.children[-1].x) / 2

        for box in boxes:
            place(box, 0)
        return boxes, max(cursor[0] - GAP, BOX_WIDTH), levels

    def _row(self, title, boxes, offset, y, bus_y, levels, trunk_x) -> float:
        def level_y(depth: int) -> float:
            return bus_y + 16 + sum(height + VERTICAL_GAP for height in levels[:depth])

        self._parts.append(f'<text x="{MARGIN}" y="{y + 6:g}" {FONT} font-size="11" font-weight="600" '
                           f'letter-spacing="1" fill="#7C8B95">{title}</text>')
        centers = [offset + box.x + BOX_WIDTH / 2 for box in boxes]
        self._line(f"M{SIDE_X} {bus_y:g} H{max(trunk_x, *centers):g}")

        def draw(box: _Box) -> None:
            x, top = offset + box.x, level_y(box.depth)
            if box.depth == 0:
                self._line(f"M{x + BOX_WIDTH / 2:g} {bus_y:g} V{top:g}")
            for child in box.children:
                middle = top + levels[box.depth] + VERTICAL_GAP / 2
                self._line(f"M{x + BOX_WIDTH / 2:g} {top + box.height:g} V{middle:g} "
                           f"H{offset + child.x + BOX_WIDTH / 2:g} V{level_y(child.depth):g}")
                draw(child)
            self._draw_box(box, x, top)

        for box in boxes:
            draw(box)
        return level_y(len(levels)) + 12

    def _line(self, path: str) -> None:
        self._parts.append(f'<path d="{path}" fill="none" stroke="{LINE_COLOR}" stroke-width="1.5"/>')

    def _draw_box(self, box: _Box, x: float, y: float) -> None:
        dash = ' stroke-dasharray="5 3"' if box.ou is not None and box.ou.kind == "parent" else ""
        texts = "".join(f'<text x="{x + PAD + 2:g}" y="{y + PAD + 12 + LINE * (index + 1):g}" {MONO} font-size="10.5" '
                        f'fill="#53636E">{escape(item)}</text>' for index, item in enumerate(box.items))
        self._parts.append(
            f'<g><rect x="{x:g}" y="{y:g}" width="{BOX_WIDTH}" height="{box.height}" rx="6" fill="#FFFFFF" '
            f'stroke="{box.color}" stroke-width="1.5"{dash}/>'
            f'<rect x="{x:g}" y="{y:g}" width="5" height="{box.height}" rx="2" fill="{box.color}"/>'
            f'<text x="{x + PAD + 2:g}" y="{y + PAD + 12:g}" {FONT} font-size="12.5" font-weight="600" '
            f'fill="#16222B">{escape(box.label)}</text>{texts}</g>')
