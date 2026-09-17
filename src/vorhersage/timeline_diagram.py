"""Offline dependency diagrams from the same validated models used in calculations."""

from html import escape
from pathlib import Path
from textwrap import wrap

from . import timeline, timeline_plan
from .common import require


def mermaid(spec):
    timeline.validate(spec)
    # Labels are encoded as Mermaid character entities. IDs never enter syntax.
    def label(value):
        return "".join(f"#{ord(c)};" if c in '&<>"#{}[]`\\\n\r' else c for c in value)
    ids = {n["id"]: f"n{i}" for i, n in enumerate(spec["nodes"])}
    lines = ["flowchart TD"]
    for node in spec["nodes"]:
        suffix = " (any prerequisite)" if node["kind"] == "any" else ""
        lines.append(f'    {ids[node["id"]]}["{label(node["completion_condition"] + suffix)}"]')
    for node in spec["nodes"]:
        lines.extend(f"    {ids[parent]} --> {ids[node['id']]}" for parent in node["parents"])
    lines += ["    classDef target fill:#e8f4ee,stroke:#287454,stroke-width:3px,color:#173d2c",
              f"    class {ids[spec['target']]} target"]
    return "\n".join(lines) + "\n"


def svg(spec):
    nodes, _, order = timeline.validate(spec)
    rank = {}
    for id in order:
        rank[id] = max((rank[parent] + 1 for parent in nodes[id]["parents"]), default=0)
    levels = [[n for n in spec["nodes"] if rank[n["id"]] == level] for level in range(max(rank.values()) + 1)]
    labels = {n["id"]: wrap(n["completion_condition"], 30) +
              (["(any prerequisite)"] if n["kind"] == "any" else []) for n in spec["nodes"]}
    box_height = max(76, max(map(len, labels.values())) * 20 + 28)
    width = max(660, max(map(len, levels)) * 300 + 40)
    title_lines = wrap(spec["description"], max(40, int((width - 60) / 11)))
    top = 40 + len(title_lines) * 26 + 40
    pitch = box_height + 64
    height = top + len(levels) * pitch + 50
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
             '<title id="title">' + escape(spec["description"]) + '</title>',
             '<desc id="description">Dependency diagram. Arrows run from prerequisites to dependent steps. The green box satisfies the forecasting question.</desc>',
             '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#61766d"/></marker></defs>',
             '<rect width="100%" height="100%" fill="#f6f9f6"/>',
             '<g font-family="system-ui, sans-serif" fill="#193d2d">']
    for i, line in enumerate(title_lines):
        parts.append(f'<text x="30" y="{36 + i * 26}" font-size="21" font-weight="600">{escape(line)}</text>')
    parts.append(f'<text x="30" y="{top - 20}" font-size="14">Declared prerequisites · Green marks the step satisfying the question</text>')
    positions = {}
    for level, rows in enumerate(levels):
        start = (width - len(rows) * 300) / 2 + 20
        for index, node in enumerate(rows):
            positions[node["id"]] = (start + index * 300, top + level * pitch)
    for node in spec["nodes"]:
        x, y = positions[node["id"]]
        for parent in node["parents"]:
            px, py = positions[parent]
            start_y = py + box_height
            if rank[node["id"]] == rank[parent] + 1:
                middle = (start_y + y) / 2
                path = f'M {px + 130} {start_y} C {px + 130} {middle}, {x + 130} {middle}, {x + 130} {y - 2}'
            else:
                # Route edges spanning levels outside the boxes in between.
                path = f'M {px + 130} {start_y} V {start_y + 20} H {width - 12} V {y - 32} H {x + 130} V {y - 2}'
            parts.append(f'<path d="{path}" fill="none" stroke="#61766d" stroke-width="2" marker-end="url(#arrow)"/>')
    for node in spec["nodes"]:
        x, y = positions[node["id"]]
        target = node["id"] == spec["target"]
        parts.append(f'<rect x="{x}" y="{y}" width="260" height="{box_height}" rx="10" fill="{"#e8f4ee" if target else "white"}" stroke="#287454" stroke-width="{3 if target else 1}"/>')
        first_line = y + (box_height - len(labels[node["id"]]) * 20) / 2 + 15
        for index, line in enumerate(labels[node["id"]]):
            parts.append(f'<text x="{x + 130}" y="{first_line + index * 20}" text-anchor="middle" font-size="15">{escape(line)}</text>')
    parts += [f'<text x="30" y="{height - 24}" font-size="13">Structure only. Dates, durations, and probabilities require scenario inputs.</text>', '</g></svg>']
    return "\n".join(parts) + "\n"


def export(store, reference, output=None):
    if reference.endswith(".toml"):
        spec = timeline_plan.compile(timeline_plan.read(reference))
    else:
        with store.connect() as c:
            spec = timeline.read(c, timeline.resolve(c, reference))["specification"]
    if output is None:
        return {"diagram": mermaid(spec), "diagram_format": "mermaid"}
    path = Path(output)
    require(path.suffix in (".svg", ".mmd", ".md"), "Diagram output must end in .svg, .mmd, or .md.")
    if path.suffix == ".svg":
        content = svg(spec)
    else:
        content = mermaid(spec)
        if path.suffix == ".md":
            content = "```mermaid\n" + content + "```\n"
    path.write_text(content, encoding="utf-8")
    return {"path": str(path.resolve()), "diagram_format": path.suffix[1:]}
