#!/usr/bin/env python3
"""Build a runtime Design Graph from an Uno App MCP visual-tree snapshot.

`uno_app_visualtree_snapshot` (Uno.UI.App.Mcp >= 1.3.3) returns the running
app's visual tree as an indented text outline, one element per line, two
spaces per nesting level. This script turns that outline into a graph with
the same ontology and ID grammar as a source-backed graph, so that
`diff_graph.py <design> <runtime>` can report drift (references/runtime-source.md).

Line grammar, as documented by the tool's own description (App MCP server).
Whether a nested UserControl prints as one '@' line or as 'Type ^N' followed by
'@ File ^N' is not documented; both shapes are accepted (same handle = same node).

  @ File ^N (Kind, dc:VM)      opens a source-file scope; Kind = Page/UserControl/...
  [lib:]Type ^N                element type + ref handle ('lib:' = framework type)
  #Name                        x:Name or AutomationProperties.Name
  :L or :L:C                   source line[:column], relative to the enclosing @ File
  "text"                       text content
  [i t x s v r c]              automation patterns
  Prop={Path[,mode][|conv]}    a classic {Binding}
  dc:Type                      locally-set DataContext runtime type
  o:.5   xf                    opacity / RenderTransform present
  @@x,y,w,h                    arranged bounds (detail=full only)
  !hidden !offscreen !code !lib   flags

What the snapshot carries and what it does not:
  uno.type   <- Type (verbatim, 'lib:' stripped)
  uno.xName  <- #Name, only when it is a valid XAML identifier
  uno.namespace, uno.styleKey, uno.resourceKey, uno.class: NOT in the snapshot.
  These are never coined here; the diff reports them as drift so the gap is
  visible rather than papered over.

Exit code 1 when the input holds no element lines.
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

GENERATOR_VERSION = "0.1.0"
SCHEMA_VERSION = "0.2.0"
INDENT = 2
SOURCE_LABEL = "uno_app_visualtree_snapshot"

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SCOPE_RE = re.compile(r"^@\s+(?P<file>\S+)\s+\^(?P<ref>\S+)(?P<rest>.*)$")
ELEMENT_RE = re.compile(r"^(?P<lib>lib:)?(?P<type>[A-Za-z_][A-Za-z0-9_]*)\s+\^(?P<ref>\S+)(?P<rest>.*)$")
TOKEN_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\[[^\]]*\]|\([^)]*\)|[A-Za-z_][A-Za-z0-9_.]*=\{[^}]*\}|\S+')
LINE_RE = re.compile(r"^:(?P<line>\d+)(?::(?P<col>\d+))?$")
BINDING_RE = re.compile(r"^(?P<prop>[A-Za-z_][A-Za-z0-9_.]*)=\{(?P<body>[^}]*)\}$")
BOUNDS_RE = re.compile(r"^@@(?P<x>-?\d+(?:\.\d+)?),(?P<y>-?\d+(?:\.\d+)?),(?P<w>-?\d+(?:\.\d+)?),(?P<h>-?\d+(?:\.\d+)?)$")

# Runtime type -> graph node type. Anything not listed: 'region' when it has
# children, 'control' when it is a leaf. Extend as the ontology settles.
CONTROL_TYPES = {
    "Button", "ToggleButton", "RepeatButton", "HyperlinkButton", "AppBarButton", "AppBarToggleButton",
    "CheckBox", "RadioButton", "ToggleSwitch", "TextBox", "PasswordBox", "AutoSuggestBox", "NumberBox",
    "RichEditBox", "ComboBox", "Slider", "ListView", "GridView", "ListBox", "NavigationView", "TabBar",
    "TabView", "Pivot", "DatePicker", "TimePicker", "CalendarDatePicker", "CalendarView", "ColorPicker",
    "RatingControl", "SplitButton", "DropDownButton", "MenuBar", "MenuFlyoutItem", "ProgressRing",
    "ProgressBar", "Expander", "ScrollBar", "TreeView", "FlipView", "SelectorBar", "RadioButtons",
    "SegmentedControl", "Chip", "ChipGroup", "InfoBar", "TeachingTip", "ContentDialog", "WebView2",
    "MediaPlayerElement", "InkCanvas", "NavigationBar", "Card", "Divider",
}
CONTENT_TYPES = {"TextBlock", "RichTextBlock", "Run", "Hyperlink", "Bold", "Italic", "Underline", "Span"}
ASSET_TYPES = {
    "Image", "FontIcon", "PathIcon", "SymbolIcon", "BitmapIcon", "ImageIcon", "AnimatedIcon", "Path",
    "Ellipse", "Rectangle", "Line", "Polygon", "Polyline", "SvgImageSource", "AnimatedVisualPlayer",
    "PersonPicture", "Shape",
}
REGION_TYPES = {
    "Grid", "StackPanel", "Border", "Canvas", "RelativePanel", "ScrollViewer", "WrapPanel", "AutoLayout",
    "Viewbox", "ItemsRepeater", "ItemsControl", "Frame", "SplitView", "ContentPresenter", "ContentControl",
    "ItemsPresenter", "VariableSizedWrapGrid", "SwapChainPanel", "Panel", "UniformGridLayout",
    "ItemsStackPanel", "ItemsWrapGrid", "ExtendedSplashScreen", "SafeArea", "ResponsiveView",
    "LoadingView", "ShadowContainer", "DrawerControl", "DrawerFlyoutPresenter", "Popup", "Flyout",
    "FlyoutPresenter", "Window", "Page", "UserControl",
}


class Node:
    """One parsed snapshot line."""

    def __init__(self, depth: int, ref: str, type_name: str) -> None:
        self.depth = depth
        self.ref = ref
        self.type_name = type_name
        self.is_scope = False
        self.scope_kind: str | None = None
        self.file: str | None = None
        self.name: str | None = None
        self.line: int | None = None
        self.column: int | None = None
        self.text: str | None = None
        self.patterns: list[str] = []
        self.bindings: list[dict] = []
        self.data_context_type: str | None = None
        self.opacity: float | None = None
        self.has_transform = False
        self.bounds: dict | None = None
        self.flags: set[str] = set()
        self.is_lib = False
        self.children: list["Node"] = []
        self.parent: "Node | None" = None
        # Filled during graph build.
        self.graph_type: str | None = None
        self.graph_id: str | None = None


def slug(value: str) -> str:
    """Lowercase hyphenated slug that satisfies the ID grammar (lint_graph.py SEGMENT)."""
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", value)
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value or "node"


def screen_slug_from_file(file: str) -> str:
    stem = Path(file).stem
    stem = re.sub(r"(Page|View)$", "", stem) or stem
    return slug(stem)


def parse_rest(node: Node, rest: str) -> None:
    for token in TOKEN_RE.findall(rest):
        if token.startswith('"') and token.endswith('"'):
            node.text = token[1:-1]
        elif token.startswith("(") and token.endswith(")"):
            for part in (p.strip() for p in token[1:-1].split(",")):
                if part.startswith("dc:"):
                    node.data_context_type = part[3:]
                elif part:
                    node.scope_kind = part
        elif token.startswith("[") and token.endswith("]"):
            node.patterns = token[1:-1].split()
        elif token.startswith("#"):
            node.name = token[1:]
        elif token.startswith("@@"):
            m = BOUNDS_RE.match(token)
            if m:
                node.bounds = {k: float(m.group(k)) for k in ("x", "y", "w", "h")}
        elif token.startswith("dc:"):
            node.data_context_type = token[3:]
        elif token.startswith("o:"):
            try:
                node.opacity = float(token[2:])
            except ValueError:
                pass
        elif token == "xf":
            node.has_transform = True
        elif token.startswith("!"):
            node.flags.add(token[1:])
        elif LINE_RE.match(token):
            m = LINE_RE.match(token)
            node.line = int(m.group("line"))
            node.column = int(m.group("col")) if m.group("col") else None
        else:
            m = BINDING_RE.match(token)
            if m:
                node.bindings.append(parse_binding(m.group("prop"), m.group("body")))


def parse_binding(prop: str, body: str) -> dict:
    converter = "|conv" in body
    body = body.replace("|conv", "")
    path, _, mode = body.partition(",")
    binding = {"property": prop, "path": path}
    if mode:
        binding["mode"] = mode
    if converter:
        binding["converter"] = True
    return binding


def parse_line(raw: str) -> Node | None:
    stripped = raw.lstrip(" ")
    if not stripped.strip():
        return None
    depth = (len(raw) - len(stripped)) // INDENT
    m = SCOPE_RE.match(stripped)
    if m:
        node = Node(depth, m.group("ref"), "")
        node.is_scope = True
        node.file = m.group("file")
        parse_rest(node, m.group("rest"))
        node.type_name = node.scope_kind or "UserControl"
        return node
    m = ELEMENT_RE.match(stripped)
    if m:
        node = Node(depth, m.group("ref"), m.group("type"))
        node.is_lib = bool(m.group("lib"))
        parse_rest(node, m.group("rest"))
        if node.is_lib:
            node.flags.add("lib")
        return node
    return None


def merge_scope_into_element(element: Node, scope: Node) -> None:
    """A UserControl may print as 'Type ^N' followed by '@ File ^N (Kind)' with the same handle; fold the scope line into the element."""
    element.is_scope = True
    element.file = scope.file
    element.scope_kind = scope.scope_kind or element.type_name
    element.type_name = element.scope_kind
    element.data_context_type = element.data_context_type or scope.data_context_type
    element.line = element.line if element.line is not None else scope.line
    element.column = element.column if element.column is not None else scope.column
    element.name = element.name or scope.name
    element.flags |= scope.flags


def parse_snapshot(text: str) -> list[Node]:
    """Returns the root nodes of the parsed forest (normally one)."""
    roots: list[Node] = []
    stack: list[Node] = []
    for raw in text.splitlines():
        node = parse_line(raw)
        if node is None:
            continue
        if node.is_scope and stack and stack[-1].ref == node.ref and not stack[-1].is_scope:
            merge_scope_into_element(stack[-1], node)
            continue
        while stack and stack[-1].depth >= node.depth:
            stack.pop()
        if stack:
            node.parent = stack[-1]
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots


def enclosing_scope(node: Node) -> Node | None:
    current = node.parent
    while current is not None and not current.is_scope:
        current = current.parent
    return current


def classify(node: Node, root: Node) -> str:
    if node is root:
        return "screen"
    if node.is_scope:
        return "component"
    t = node.type_name
    if t in CONTROL_TYPES:
        return "control"
    if t in CONTENT_TYPES:
        return "content"
    if t in ASSET_TYPES:
        return "asset"
    if t in REGION_TYPES:
        return "region"
    return "region" if node.children else "control"


def x_name_of(node: Node) -> str | None:
    """#Name is x:Name only when it is an identifier; an AutomationProperties.Name is not copied into uno.xName."""
    if node.name and IDENT_RE.match(node.name):
        return node.name
    return None


def uno_layer(node: Node, graph_type: str) -> dict:
    uno: dict = {}
    if graph_type == "screen":
        uno["type"] = node.type_name
        return uno
    if graph_type == "component":
        uno["type"] = node.type_name
        x = x_name_of(node)
        if x:
            uno["xName"] = x
        return uno
    uno["type"] = node.type_name
    x = x_name_of(node)
    if x:
        uno["xName"] = x
    return uno


def evidence_for(node: Node, screen: Node) -> dict:
    scope = node if node.is_scope else enclosing_scope(node)
    source: dict = {"type": "runtime", "label": SOURCE_LABEL}
    locator: dict = {"ref": node.ref}
    if scope is not None and scope.file:
        locator["file"] = scope.file
    if node.line is not None:
        locator["line"] = node.line
    if node.column is not None:
        locator["column"] = node.column
    if node.flags:
        locator["flags"] = sorted(node.flags)
    ev = {"kind": "observed", "confidence": 1.0, "source": source, "locator": locator}
    if "code" in node.flags:
        ev["rationale"] = "Created in code; the snapshot reports no source declaration."
    return ev


def build_graph(roots: list[Node], graph_id: str | None, screen_slug: str | None,
                include_lib: bool, design: dict | None) -> dict:
    if not roots:
        raise ValueError("no element lines found in the snapshot")
    root = roots[0]
    if screen_slug is None:
        screen_slug = screen_slug_from_file(root.file) if root.file else slug(root.type_name)
    graph_id = graph_id or f"{screen_slug}-runtime"

    design_by_xname: dict[str, dict] = {}
    if design:
        for n in design.get("nodes", []):
            x = ((n.get("properties") or {}).get("uno") or {}).get("xName")
            if x:
                design_by_xname[x] = n

    nodes: list[dict] = []
    edges: list[dict] = []
    used_ids: set[str] = set()

    def unique(candidate: str) -> str:
        base, i = candidate, 2
        while candidate in used_ids:
            candidate = f"{base}-{i}"
            i += 1
        used_ids.add(candidate)
        return candidate

    def element_slug(node: Node) -> str:
        x = x_name_of(node)
        if x:
            return slug(x)
        if node.line is not None:
            return slug(f"{node.type_name}-{node.line}")
        return slug(f"{node.type_name}-{node.ref}")

    def visit(node: Node, parent_id: str | None) -> None:
        if node.is_lib and not include_lib:
            return
        graph_type = classify(node, root)
        node_id: str
        design_hint = design_by_xname.get(x_name_of(node) or "")
        if graph_type == "screen":
            node_id = f"screen.{screen_slug}"
        elif design_hint is not None and design_hint.get("type") in {"region", "component", "control", "content", "asset"}:
            # Adopt the design node's TYPE only. diff_graph.py keys identity on
            # (type, xName), so that is enough to match. The design id is not
            # adopted: a 3-segment component id means "instance of a canonical",
            # and a runtime tree observes no canonical, so a hinted component
            # takes the 2-segment canonical form like a scope-derived one.
            graph_type = design_hint["type"]
            node_id = (f"component.{element_slug(node)}" if graph_type == "component"
                       else f"{graph_type}.{screen_slug}.{element_slug(node)}")
        elif graph_type == "component":
            node_id = f"component.{screen_slug_from_file(node.file) if node.file else slug(node.type_name)}"
        else:
            node_id = f"{graph_type}.{screen_slug}.{element_slug(node)}"
        node_id = unique(node_id)
        node.graph_type, node.graph_id = graph_type, node_id

        entry: dict = {"id": node_id, "type": graph_type}
        display = node.name or (Path(node.file).stem if node.is_scope and node.file else node.type_name)
        entry["name"] = display
        if node.text is not None:
            entry["text"] = node.text
        props: dict = {"uno": uno_layer(node, graph_type)}
        if node.data_context_type:
            props["dataContextType"] = node.data_context_type
        if node.bindings:
            props["bindings"] = node.bindings
        if node.patterns:
            props["automationPatterns"] = node.patterns
        if node.opacity is not None:
            props["opacity"] = node.opacity
        if node.has_transform:
            props["renderTransform"] = True
        if node.name and not x_name_of(node):
            props["automationName"] = node.name
        entry["properties"] = props
        if node.bounds:
            entry["geometry"] = {"x": node.bounds["x"], "y": node.bounds["y"],
                                 "width": node.bounds["w"], "height": node.bounds["h"], "unit": "px"}
        tags = sorted(node.flags)
        if tags:
            entry["tags"] = tags
        entry["evidence"] = evidence_for(node, root)
        nodes.append(entry)

        if parent_id is not None:
            edges.append({"from": parent_id, "relation": "contains", "to": node_id,
                          "evidence": {"kind": "observed", "confidence": 1.0,
                                       "source": {"type": "runtime", "label": SOURCE_LABEL}}})
        for child in node.children:
            visit(child, node_id)

    visit(root, None)
    for extra_root in roots[1:]:
        visit(extra_root, None)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "graphId": graph_id,
        "name": f"{root.name or (Path(root.file).stem if root.file else root.type_name)} (runtime)",
        "description": "Built mechanically from an Uno App MCP visual-tree snapshot by snapshot_to_graph.py. "
                       "uno.type and uno.xName are copied from the snapshot; namespace, styleKey, resourceKey "
                       "and class are not exposed by the snapshot and are deliberately absent.",
        "sourceSummary": [{"type": "runtime", "label": SOURCE_LABEL}],
        "metadata": {"kind": "screen", "generator": f"snapshot_to_graph.py {GENERATOR_VERSION}",
                     "snapshotFormat": "uno_app_visualtree_snapshot text outline (Uno.UI.App.Mcp 1.3.x)"},
        "nodes": nodes,
        "edges": edges,
        "unresolved": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("snapshot", type=Path, help="Text returned by uno_app_visualtree_snapshot ('-' for stdin)")
    parser.add_argument("-o", "--output", type=Path, help="Write the graph here (default: stdout)")
    parser.add_argument("--graph-id", help="graphId (default: <screen-slug>-runtime)")
    parser.add_argument("--screen-slug", help="Slug for the screen node id (default: derived from the root file name)")
    parser.add_argument("--include-lib", action="store_true", help="Keep 'lib:' / '!lib' template internals (default: drop)")
    parser.add_argument("--design", type=Path,
                        help="Design graph whose node types are adopted for x:Names the runtime confirms "
                             "(never its ids or uno.* values), so diff_graph.py matches semantic nodes across the two graphs")
    args = parser.parse_args()

    text = sys.stdin.read() if str(args.snapshot) == "-" else args.snapshot.read_text(encoding="utf-8")
    design = json.loads(args.design.read_text(encoding="utf-8")) if args.design else None
    roots = parse_snapshot(text)
    if not roots:
        print("snapshot_to_graph: no element lines recognized", file=sys.stderr)
        return 1
    graph = build_graph(roots, args.graph_id, args.screen_slug, args.include_lib, design)
    payload = json.dumps(graph, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
        print(f"wrote {args.output} ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
