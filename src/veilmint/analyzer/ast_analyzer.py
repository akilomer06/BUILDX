"""Small, deliberately conservative syntactic analysis; never run consumer code.

Only literal subscripts and ordinary ``.get`` calls on the configured root
prove use. Other references to the root escape this limited analysis. A single
unconditional local string binding may bound a dynamic key, but is not direct
use evidence. No control-flow, alias or interprocedural proof is attempted.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
import keyword


class Usage(str, Enum):
    USED = "USED"
    CANDIDATE_UNUSED = "CANDIDATE_UNUSED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FieldUsage:
    name: str
    usage: Usage
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class AnalysisResult:
    fields: tuple[FieldUsage, ...]
    warnings: tuple[str, ...]


# Explicitly reviewed node kinds. New Python grammar or syntax outside this
# subset makes the whole scan uncertain rather than silently implying non-use.
_SUPPORTED_NODES = frozenset("""
Module FunctionDef AsyncFunctionDef arguments arg Return Delete Assign AugAssign
AnnAssign For AsyncFor While If With AsyncWith withitem Raise Try TryStar
ExceptHandler Assert Import ImportFrom alias Global Nonlocal Expr Pass Break
Continue BoolOp NamedExpr BinOp UnaryOp Lambda IfExp Dict Set List Tuple ListComp
SetComp DictComp GeneratorExp comprehension Await Yield YieldFrom Compare Call
keyword FormattedValue JoinedStr Constant Attribute Subscript Starred Name Load
Store Del Slice And Or Add Sub Mult MatMult Div Mod Pow LShift RShift BitOr BitXor
BitAnd FloorDiv Invert Not UAdd USub Eq NotEq Lt LtE Gt GtE Is IsNot In NotIn
TypeIgnore
""".split())
_SCOPES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_REFLECTION_NAMES = {"eval", "exec", "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr", "__builtins__"}
_FRAME_ATTRIBUTES = {"currentframe", "_getframe", "f_locals", "f_globals", "__globals__", "__dict__", "__getattribute__"}


def analyze_source(
    source: str,
    fields: Iterable[str],
    *,
    root_name: str = "payload",
    filename: str = "<consumer>",
) -> AnalysisResult:
    """Analyze top-level field access in source text without importing it.

    ``USED`` wins over ambiguous operations, except if the root itself is
    rebound: then even the identity behind a literal access is uncertain.
    Candidates describe only this source and root, never removal permission.
    """
    if not isinstance(root_name, str) or not root_name.isidentifier() or keyword.iskeyword(root_name):
        raise ValueError("root_name must be a valid Python identifier, not a keyword")
    field_names = tuple(fields)
    if any(not isinstance(name, str) for name in field_names):
        raise ValueError("Field names must be strings")
    names = tuple(sorted(set(field_names)))

    used: dict[str, list[str]] = {name: [] for name in names}
    uncertain: dict[str, list[str]] = {name: [] for name in names}
    scope_reasons: list[str] = []
    warnings: set[str] = set()

    def location(node: ast.AST) -> str:
        return f"{filename}:{getattr(node, 'lineno', 1)}:{getattr(node, 'col_offset', 0) + 1}"

    def unknown(reason: str, node: ast.AST | None = None) -> None:
        message = f"{location(node)}: {reason}" if node is not None else reason
        scope_reasons.append(message)
        warnings.add(message)

    def finish() -> AnalysisResult:
        results = []
        for name in names:
            if used[name]:
                usage, reasons = Usage.USED, used[name]
            elif scope_reasons or uncertain[name]:
                usage = Usage.UNKNOWN
                reasons = scope_reasons + uncertain[name]
            else:
                usage = Usage.CANDIDATE_UNUSED
                reasons = [
                    f"No supported access to {name!r} in the scanned source for root "
                    f"{root_name!r}. Candidate only, not proof of non-use; human review "
                    "is required before removal."
                ]
            results.append(FieldUsage(name, usage, tuple(sorted(set(reasons)))))
        return AnalysisResult(tuple(results), tuple(sorted(warnings)))

    try:
        tree = ast.parse(source, filename=filename)
    except (SyntaxError, ValueError, RecursionError) as exc:
        detail = getattr(exc, "msg", str(exc))
        line = getattr(exc, "lineno", None) or 1
        unknown(f"{filename}:{line}: Incomplete analysis: source could not be parsed ({detail}).")
        return finish()

    nodes = tuple(ast.walk(tree))
    parents = {child: parent for parent in nodes for child in ast.iter_child_nodes(parent)}

    def enclosing_scope(node: ast.AST) -> ast.AST:
        current = parents.get(node)
        while current is not None and not isinstance(current, _SCOPES):
            current = parents.get(current)
        return current if current is not None else tree

    # Count all bindings throughout the source. This intentionally rejects even
    # some unrelated same-named bindings to avoid pretending to resolve scopes.
    bindings: Counter[str] = Counter()
    for node in nodes:
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bindings[node.id] += 1
        elif isinstance(node, ast.arg):
            bindings[node.arg] += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings[node.name] += 1
        elif isinstance(node, ast.alias):
            bindings[node.asname or node.name.split(".")[0]] += 1
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bindings[node.name] += 1
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bindings.update(node.names)

    literal_bindings: dict[str, tuple[str, ast.AST, ast.AST]] = {}
    for node in nodes:
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        if (
            isinstance(target, ast.Name)
            and bindings[target.id] == 1
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and isinstance(parents.get(node), (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            literal_bindings[target.id] = (node.value.value, enclosing_scope(node), node)

    root_rebound = False
    for node in nodes:
        if type(node).__name__ not in _SUPPORTED_NODES:
            unknown(f"Unsupported syntax {type(node).__name__}; analysis scope is uncertain.", node)
        is_root_binding = (
            isinstance(node, ast.Name) and node.id == root_name and isinstance(node.ctx, (ast.Store, ast.Del))
            or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == root_name
            or isinstance(node, ast.alias) and (node.asname or node.name.split(".")[0]) == root_name
            or isinstance(node, ast.ExceptHandler) and node.name == root_name
        )
        if is_root_binding:
            root_rebound = True
            unknown(f"Root {root_name!r} is rebound or deleted; payload identity is uncertain.", node)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in _REFLECTION_NAMES | _FRAME_ATTRIBUTES:
            unknown(f"Reflection/dynamic execution reference {node.id!r} may hide payload access.", node)
        if isinstance(node, ast.Attribute) and node.attr in _FRAME_ATTRIBUTES | _REFLECTION_NAMES:
            unknown(f"Frame/reflection attribute {node.attr!r} may hide payload access.", node)
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _REFLECTION_NAMES | _FRAME_ATTRIBUTES:
                    unknown(f"Imported reflection helper {alias.name!r} may hide payload access.", node)
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            root_rebound = True
            unknown("Wildcard import can rebind the payload root; analysis is incomplete.", node)

    def is_root(node: ast.AST) -> bool:
        return isinstance(node, ast.Name) and node.id == root_name

    def access(key: ast.AST, node: ast.AST) -> None:
        if root_rebound:
            return
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            if key.value in used:
                pattern = (
                    f"{root_name}.get({key.value!r})"
                    if isinstance(node, ast.Call) else f"{root_name}[{key.value!r}]"
                )
                used[key.value].append(f"{location(node)}: Direct literal field read via {pattern}.")
            else:
                warnings.add(f"{location(node)}: Literal field {key.value!r} is absent from the schema inventory.")
            return
        if isinstance(key, ast.Name) and key.id in literal_bindings:
            value, scope, assignment = literal_bindings[key.id]
            if scope is enclosing_scope(key) and assignment.lineno < node.lineno:
                reason = (
                    f"{location(node)}: Dynamic key {key.id!r} has one local literal binding "
                    f"to {value!r}; affected field is bounded, but direct use is unproven."
                )
                warnings.add(reason)
                if value in uncertain:
                    uncertain[value].append(reason)
                return
        unknown("Unbounded dynamic field access; any schema field may be read.", node)

    supported_roots: set[ast.Name] = set()
    for node in nodes:
        if isinstance(node, ast.Subscript) and is_root(node.value):
            supported_roots.add(node.value)
            if isinstance(node.ctx, ast.Load):
                access(node.slice, node)
            else:
                unknown("Payload mutation/deletion invalidates read-only analysis assumptions.", node)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and is_root(node.func.value)
            and node.func.attr == "get"
        ):
            supported_roots.add(node.func.value)
            if len(node.args) in (1, 2) and not node.keywords and not any(isinstance(arg, ast.Starred) for arg in node.args):
                access(node.args[0], node)
            else:
                unknown("Unsupported .get call shape; access cannot be resolved safely.", node)

    for node in nodes:
        if is_root(node) and isinstance(node.ctx, ast.Load) and node not in supported_roots:
            context = type(parents.get(node)).__name__
            unknown(
                f"Whole payload reference in {context}: aliasing, forwarding, iteration, "
                "reflection or another unsupported operation may access any field.", node,
            )
    return finish()
