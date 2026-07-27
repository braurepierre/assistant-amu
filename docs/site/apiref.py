"""Static API reference extracted from the source of ``assistant_amu``.

Read the Docs builds this site without the project's runtime dependencies
(torch, chromadb, sentence-transformers): an importing documenter such as
``pdoc`` or ``sphinx.ext.autodoc`` would need all of them on the build server.
So nothing is imported here — signatures and docstrings are read from the
source with :mod:`ast`, and rendered as Markdown pages Pelican composes like
any other page.

The trade-off is the usual one for static analysis: dynamically built members
(anything created at import time rather than written as a ``def`` or ``class``)
are invisible. This package declares its API in the source, so the loss is nil
today; it would show up if a module started generating attributes.
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

# Sphinx roles used in the docstrings (:class:`Embedder`, :func:`x`, :mod:`y`).
# Markdown has no equivalent, so the target is kept and shown as code. A leading
# "~" (short form) and a "module.path." prefix are dropped, as Sphinx does.
_ROLE = re.compile(r":[a-zA-Z:+-]+:`([^`]+)`")
# reST literal block marker: "text::" opens an indented block. The indentation
# already reads as a Markdown code block, only the doubled colon must go.
_LITERAL_BLOCK = re.compile(r"(\S)::$", re.MULTILINE)


def _is_indented(line: str) -> bool:
    return bool(line.strip()) and line[:1].isspace()


def _reflow_indented_blocks(text: str) -> str:
    """Give indented runs the blank line or the fence Markdown requires.

    reST reads an indented run under a line of text as a block of its own;
    Markdown reads it as the lazy continuation of the paragraph above, which
    collapses the aligned command tables of the CLI modules into a single
    sentence. Such a run becomes a fenced code block, so its alignment holds.
    A run of bullets means an actual list, and only needs the blank line.
    """
    lines = text.split("\n")
    output: list[str] = []
    index = 0
    while index < len(lines):
        previous = output[-1] if output else ""
        if not (_is_indented(lines[index]) and previous.strip() and not _is_indented(previous)):
            output.append(lines[index])
            index += 1
            continue

        end = index
        while end < len(lines) and (not lines[end].strip() or _is_indented(lines[end])):
            end += 1
        block = lines[index:end]
        while block and not block[-1].strip():
            block.pop()

        output.append("")
        if any(line.lstrip().startswith(("* ", "- ", "+ ")) for line in block):
            output.extend(block)
        else:
            output += ["```", *textwrap.dedent("\n".join(block)).split("\n"), "```"]
        index += len(block)
    return "\n".join(output)


def rst_to_markdown(text: str) -> str:
    """Convert the reST idioms actually used in this codebase to Markdown.

    Double backticks, ``*emphasis*`` and ``**strong**`` already mean the same
    thing in both syntaxes and are left alone.
    """
    text = _ROLE.sub(lambda m: f"`{m.group(1).lstrip('~').rsplit('.', 1)[-1]}`", text)
    return _reflow_indented_blocks(_LITERAL_BLOCK.sub(r"\1:", text))


def _format_annotation(node: ast.expr | None) -> str:
    return "" if node is None else ast.unparse(node)


def _format_arg(arg: ast.arg, default: ast.expr | None) -> str:
    out = arg.arg
    annotation = _format_annotation(arg.annotation)
    if annotation:
        out += f": {annotation}"
    if default is not None:
        out += f" = {ast.unparse(default)}" if annotation else f"={ast.unparse(default)}"
    return out


def format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Render the call signature of a function, ``self`` and ``cls`` included."""
    args = node.args
    positional = list(args.posonlyargs) + list(args.args)
    # Defaults bind to the *last* positional parameters; pad the rest with None.
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    defaults += list(args.defaults)

    parts: list[str] = []
    for index, arg in enumerate(positional):
        parts.append(_format_arg(arg, defaults[index]))
        if args.posonlyargs and index == len(args.posonlyargs) - 1:
            parts.append("/")
    if args.vararg is not None:
        parts.append("*" + _format_arg(args.vararg, None))
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        parts.append(_format_arg(arg, default))
    if args.kwarg is not None:
        parts.append("**" + _format_arg(args.kwarg, None))

    signature = "(" + ", ".join(parts) + ")"
    returns = _format_annotation(node.returns)
    return f"{signature} -> {returns}" if returns else signature


def _decorators(node: ast.AST) -> list[str]:
    """Names of the decorators applied, without their arguments."""
    names = []
    for decorator in getattr(node, "decorator_list", []):
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        names.append(ast.unparse(target))
    return names


def _is_public(name: str) -> bool:
    return not name.startswith("_") or name == "__init__"


@dataclass
class Member:
    """A documented function, method or class found in the source."""

    kind: str  # "function" | "class" | "method"
    name: str
    signature: str
    docstring: str
    decorators: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    members: list["Member"] = field(default_factory=list)


@dataclass
class Module:
    """A parsed module: its docstring and its public members."""

    name: str
    path: Path
    docstring: str
    members: list[Member] = field(default_factory=list)


def _parse_body(body: list[ast.stmt], *, kind: str) -> list[Member]:
    members: list[Member] = []
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not _is_public(node.name):
                continue
            members.append(
                Member(
                    kind=kind,
                    name=node.name,
                    signature=format_signature(node),
                    docstring=ast.get_docstring(node) or "",
                    decorators=_decorators(node),
                )
            )
        elif isinstance(node, ast.ClassDef):
            if not _is_public(node.name):
                continue
            members.append(
                Member(
                    kind="class",
                    name=node.name,
                    signature="",
                    docstring=ast.get_docstring(node) or "",
                    decorators=_decorators(node),
                    bases=[ast.unparse(base) for base in node.bases],
                    members=_parse_body(node.body, kind="method"),
                )
            )
    return members


def parse_module(path: Path, name: str) -> Module:
    """Read one source file and return its docstring and public members."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return Module(
        name=name,
        path=path,
        docstring=ast.get_docstring(tree) or "",
        members=_parse_body(tree.body, kind="function"),
    )


def iter_modules(package_dir: Path, package_name: str) -> list[Module]:
    """Parse every module of a package directory, ``__init__`` first."""
    modules = []
    for path in sorted(package_dir.glob("*.py")):
        stem = path.stem
        name = package_name if stem == "__init__" else f"{package_name}.{stem}"
        modules.append(parse_module(path, name))
    modules.sort(key=lambda m: (m.name.count("."), m.name))
    return modules


def _render_member(member: Member, *, level: int) -> list[str]:
    heading = "#" * level
    prefix = "class " if member.kind == "class" else ""
    decorators = "".join(f"`@{d}` " for d in member.decorators if d != "dataclass")
    lines = [f"{heading} `{prefix}{member.name}{member.signature}`", ""]
    if member.bases:
        lines += [f"Hérite de {', '.join(f'`{b}`' for b in member.bases)}.", ""]
    if decorators:
        lines += [decorators.strip(), ""]
    if member.docstring:
        lines += [rst_to_markdown(member.docstring), ""]
    for sub in member.members:
        lines += _render_member(sub, level=level + 1)
    return lines


def render_page(modules: list[Module], *, source_root: Path, source_url: str) -> str:
    """Render a group of modules as the Markdown body of one page."""
    lines: list[str] = []
    for module in modules:
        relative = module.path.relative_to(source_root).as_posix()
        lines += [f"## `{module.name}`", ""]
        # The path goes in backticks: Markdown would otherwise read the double
        # underscores of "__init__.py" as emphasis.
        lines += [f"[`{relative}`]({source_url}/{relative})", ""]
        if module.docstring:
            lines += [rst_to_markdown(module.docstring), ""]
        if not module.members:
            continue
        for member in module.members:
            lines += _render_member(member, level=3)
    return "\n".join(lines).rstrip() + "\n"
