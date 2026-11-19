# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=line-too-long,try-except-raise

"""Bounded zero-eval AST diagnostic interpreter for hermetic Python sandboxes."""

from __future__ import annotations

import ast
import copy
import json
from collections.abc import Callable, Mapping
from typing import Any, Final

from agents.sandbox.models import SandboxBackendExecutionResult

_MAX_AST_STEPS: Final[int] = 10_000
_MAX_AST_COLLECTION_SIZE: Final[int] = 10_000
_MAX_AST_EXPONENT: Final[int] = 1_000


class _LoopBreakSignal(Exception):
    """Internal control-flow signal for `break` inside the restricted AST interpreter."""


class _LoopContinueSignal(Exception):
    """Internal control-flow signal for `continue` inside the restricted AST interpreter."""


def _json_safe_value(value: object) -> object:
    """Converts Python container values (sets, tuples, ranges) into JSON-serializable objects."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple, range)):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, set):
        return [_json_safe_value(item) for item in sorted(value, key=str)]
    if isinstance(value, Mapping):
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    return str(value)


class _RestrictedAstInterpreter:
    """Bounded, zero-`eval`/`exec` AST interpreter for hermetic Python diagnostics."""

    def __init__(self, input_payload: Mapping[str, object]) -> None:
        payload_copy = copy.deepcopy(dict(input_payload))
        incidents_copy = (
            copy.deepcopy(payload_copy["incidents"])
            if "incidents" in payload_copy
            else []
        )
        runbooks_copy = (
            copy.deepcopy(payload_copy["runbooks"])
            if "runbooks" in payload_copy
            else []
        )
        self.env: dict[str, Any] = {
            "input_data": payload_copy,
            "readonly_input": copy.deepcopy(payload_copy),
            "incidents": incidents_copy,
            "runbooks": runbooks_copy,
        }
        self.assigned_names: set[str] = set()
        self.print_chunks: list[str] = []
        self._steps: int = 0
        self._builtins: dict[str, Callable[..., Any]] = {
            "len": len,
            "min": self._builtin_min,
            "max": self._builtin_max,
            "sum": self._builtin_sum,
            "sorted": self._builtin_sorted,
            "print": self._builtin_print,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "dict": dict,
            "list": self._builtin_list,
            "range": self._builtin_range,
        }

    def _tick(self) -> None:
        self._steps += 1
        if self._steps > _MAX_AST_STEPS:
            raise RuntimeError(
                f"Execution step limit exceeded (max {_MAX_AST_STEPS} AST steps)."
            )

    def _builtin_min(self, *args: Any, **kwargs: Any) -> Any:
        unknown = set(kwargs) - {"default"}
        if unknown:
            raise TypeError(
                f"min() got unexpected keyword arguments: {sorted(unknown)}"
            )
        return min(*args, **kwargs)

    def _builtin_max(self, *args: Any, **kwargs: Any) -> Any:
        unknown = set(kwargs) - {"default"}
        if unknown:
            raise TypeError(
                f"max() got unexpected keyword arguments: {sorted(unknown)}"
            )
        return max(*args, **kwargs)

    def _builtin_sum(self, iterable: Any, start: Any = 0) -> Any:
        return sum(iterable, start)

    def _builtin_sorted(
        self, iterable: Any, *, reverse: bool = False
    ) -> list[Any]:
        return sorted(iterable, reverse=bool(reverse))

    def _builtin_print(
        self, *args: Any, sep: str = " ", end: str = "\n"
    ) -> None:
        if not isinstance(sep, str) or not isinstance(end, str):
            raise TypeError("print() sep and end must be strings.")
        self.print_chunks.append(sep.join(str(item) for item in args) + end)

    def _builtin_list(self, iterable: Any = ()) -> list[Any]:
        out: list[Any] = []
        for item in iterable:
            self._tick()
            if len(out) >= _MAX_AST_COLLECTION_SIZE:
                raise ValueError(
                    f"list() exceeded maximum element limit ({_MAX_AST_COLLECTION_SIZE})."
                )
            out.append(item)
        return out

    def _builtin_range(self, *args: Any) -> range:
        r = range(*args)
        if len(r) > _MAX_AST_COLLECTION_SIZE:
            raise ValueError(
                f"range() exceeded maximum element limit ({_MAX_AST_COLLECTION_SIZE})."
            )
        return r

    def run(self, statements: list[ast.stmt]) -> None:
        for stmt in statements:
            self._exec_stmt(stmt)

    def _exec_stmt(self, stmt: ast.stmt) -> None:
        self._tick()
        if isinstance(stmt, ast.Pass):
            return
        if isinstance(stmt, ast.Break):
            raise _LoopBreakSignal()
        if isinstance(stmt, ast.Continue):
            raise _LoopContinueSignal()
        if isinstance(stmt, ast.Expr):
            self._eval_expr(stmt.value)
            return
        if isinstance(stmt, ast.Assign):
            value = self._eval_expr(stmt.value)
            for target in stmt.targets:
                self._assign_target(
                    target, value, self.env, track_assigned=True
                )
            return
        if isinstance(stmt, ast.AnnAssign):
            if stmt.value is not None:
                value = self._eval_expr(stmt.value)
                self._assign_target(
                    stmt.target, value, self.env, track_assigned=True
                )
            return
        if isinstance(stmt, ast.AugAssign):
            current = self._read_target(stmt.target)
            rhs = self._eval_expr(stmt.value)
            updated = self._apply_binary_op(stmt.op, current, rhs)
            self._assign_target(
                stmt.target, updated, self.env, track_assigned=True
            )
            return
        if isinstance(stmt, ast.If):
            branch = stmt.body if self._eval_expr(stmt.test) else stmt.orelse
            for sub_stmt in branch:
                self._exec_stmt(sub_stmt)
            return
        if isinstance(stmt, ast.For):
            iterable = self._eval_expr(stmt.iter)
            loop_count = 0
            completed_without_break = True
            for item in iterable:
                loop_count += 1
                self._tick()
                if loop_count > _MAX_AST_COLLECTION_SIZE:
                    raise RuntimeError(
                        f"Loop iteration limit exceeded (max {_MAX_AST_COLLECTION_SIZE})."
                    )
                self._assign_target(
                    stmt.target, item, self.env, track_assigned=True
                )
                try:
                    for sub_stmt in stmt.body:
                        self._exec_stmt(sub_stmt)
                except _LoopContinueSignal:
                    continue
                except _LoopBreakSignal:
                    completed_without_break = False
                    break
            if completed_without_break:
                for sub_stmt in stmt.orelse:
                    self._exec_stmt(sub_stmt)
            return
        if isinstance(stmt, ast.Assert):
            if not self._eval_expr(stmt.test):
                msg = self._eval_expr(stmt.msg) if stmt.msg is not None else ""
                raise AssertionError(msg)
            return
        raise TypeError(
            f"Unsupported Python statement in diagnostic AST: {type(stmt).__name__}"
        )

    def _read_target(self, target: ast.expr) -> Any:
        if isinstance(target, ast.Name):
            if target.id not in self.env:
                raise NameError(f"name '{target.id}' is not defined")
            return self.env[target.id]
        if isinstance(target, ast.Subscript):
            container = self._eval_expr(target.value)
            key = self._eval_slice(target.slice)
            return container[key]
        raise TypeError(
            f"Unsupported assignment target: {type(target).__name__}"
        )

    def _assign_target(
        self,
        target: ast.expr,
        value: Any,
        scope: dict[str, Any],
        *,
        track_assigned: bool,
    ) -> None:
        if isinstance(target, ast.Name):
            scope[target.id] = value
            if track_assigned:
                self.assigned_names.add(target.id)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            items = list(value)
            starred_idx = next(
                (
                    idx
                    for idx, elt in enumerate(target.elts)
                    if isinstance(elt, ast.Starred)
                ),
                None,
            )
            if starred_idx is None:
                if len(items) != len(target.elts):
                    raise ValueError(
                        f"Expected {len(target.elts)} values to unpack, got {len(items)}."
                    )
                for sub_target, sub_val in zip(target.elts, items, strict=True):
                    self._assign_target(
                        sub_target,
                        sub_val,
                        scope,
                        track_assigned=track_assigned,
                    )
                return
            if len(items) < len(target.elts) - 1:
                raise ValueError("Not enough values to unpack.")
            tail_count = len(target.elts) - starred_idx - 1
            head = items[:starred_idx]
            middle = items[
                starred_idx : (
                    len(items) - tail_count if tail_count else len(items)
                )
            ]
            tail = items[len(items) - tail_count :] if tail_count else []
            for sub_target, sub_val in zip(
                target.elts[:starred_idx], head, strict=True
            ):
                self._assign_target(
                    sub_target, sub_val, scope, track_assigned=track_assigned
                )
            starred_target = target.elts[starred_idx]
            assert isinstance(starred_target, ast.Starred)
            self._assign_target(
                starred_target.value,
                middle,
                scope,
                track_assigned=track_assigned,
            )
            for sub_target, sub_val in zip(
                target.elts[starred_idx + 1 :], tail, strict=True
            ):
                self._assign_target(
                    sub_target, sub_val, scope, track_assigned=track_assigned
                )
            return
        if isinstance(target, ast.Subscript):
            container = self._eval_expr(target.value, scope)
            if not isinstance(container, (dict, list)):
                raise TypeError(
                    f"'{type(container).__name__}' object does not support item assignment"
                )
            key = self._eval_slice(target.slice, scope)
            container[key] = value
            return
        raise TypeError(
            f"Unsupported assignment target: {type(target).__name__}"
        )

    def _eval_slice(
        self, node: ast.expr, scope: dict[str, Any] | None = None
    ) -> Any:
        if isinstance(node, ast.Slice):
            lower = (
                self._eval_expr(node.lower, scope)
                if node.lower is not None
                else None
            )
            upper = (
                self._eval_expr(node.upper, scope)
                if node.upper is not None
                else None
            )
            step = (
                self._eval_expr(node.step, scope)
                if node.step is not None
                else None
            )
            return slice(lower, upper, step)
        return self._eval_expr(node, scope)

    def _apply_binary_op(self, op: ast.operator, left: Any, right: Any) -> Any:
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            if (
                isinstance(left, (str, bytes, list, tuple))
                and isinstance(right, int)
                and right > 0
                and len(left) * right > _MAX_AST_COLLECTION_SIZE
            ) or (
                isinstance(right, (str, bytes, list, tuple))
                and isinstance(left, int)
                and left > 0
                and len(right) * left > _MAX_AST_COLLECTION_SIZE
            ):
                raise ValueError("Sequence repetition exceeds maximum size.")
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.FloorDiv):
            return left // right
        if isinstance(op, ast.Mod):
            return left % right
        if isinstance(op, ast.Pow):
            if (
                isinstance(right, (int, float))
                and abs(right) > _MAX_AST_EXPONENT
            ):
                raise ValueError(
                    f"Exponent exceeds maximum bound ({_MAX_AST_EXPONENT})."
                )
            if (
                isinstance(left, int)
                and isinstance(right, int)
                and abs(left) > 10**6
                and right > 100
            ):
                raise ValueError(
                    "Integer power operand exceeds safe magnitude."
                )
            return left**right
        raise TypeError(f"Unsupported binary operator: {type(op).__name__}")

    def _eval_seq_elements(
        self, elts: list[ast.expr], scope: dict[str, Any]
    ) -> list[Any]:
        items: list[Any] = []
        for elt in elts:
            if isinstance(elt, ast.Starred):
                items.extend(self._eval_expr(elt.value, scope))
            else:
                items.append(self._eval_expr(elt, scope))
        return items

    def _eval_expr(
        self, node: ast.expr, scope: dict[str, Any] | None = None
    ) -> Any:
        self._tick()
        active_scope = self.env if scope is None else scope
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in active_scope:
                return active_scope[node.id]
            raise NameError(f"name '{node.id}' is not defined")
        if isinstance(node, ast.Attribute):
            target_val = self._eval_expr(node.value, active_scope)
            raise TypeError(
                f"Attribute access '.{node.attr}' on "
                f"'{type(target_val).__name__}' is not permitted."
            )
        if isinstance(node, ast.List):
            return self._eval_seq_elements(node.elts, active_scope)
        if isinstance(node, ast.Tuple):
            return tuple(self._eval_seq_elements(node.elts, active_scope))
        if isinstance(node, ast.Set):
            return set(self._eval_seq_elements(node.elts, active_scope))
        if isinstance(node, ast.Dict):
            out_dict: dict[Any, Any] = {}
            for k_node, v_node in zip(node.keys, node.values, strict=True):
                v_val = self._eval_expr(v_node, active_scope)
                if k_node is None:
                    if not isinstance(v_val, Mapping):
                        raise TypeError(
                            "Dictionary unpacking requires a mapping."
                        )
                    out_dict.update(v_val)
                else:
                    out_dict[self._eval_expr(k_node, active_scope)] = v_val
            return out_dict
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_expr(node.operand, active_scope)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.Not):
                return not operand
            if isinstance(node.op, ast.Invert):
                return ~operand
            raise TypeError(
                f"Unsupported unary operator: {type(node.op).__name__}"
            )
        if isinstance(node, ast.BinOp):
            left = self._eval_expr(node.left, active_scope)
            right = self._eval_expr(node.right, active_scope)
            return self._apply_binary_op(node.op, left, right)
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                val: Any = True
                for value_node in node.values:
                    val = self._eval_expr(value_node, active_scope)
                    if not val:
                        return val
                return val
            val = False
            for value_node in node.values:
                val = self._eval_expr(value_node, active_scope)
                if val:
                    return val
            return val
        if isinstance(node, ast.Compare):
            left = self._eval_expr(node.left, active_scope)
            for op, comp_node in zip(node.ops, node.comparators, strict=True):
                right = self._eval_expr(comp_node, active_scope)
                if not self._apply_compare(op, left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            if self._eval_expr(node.test, active_scope):
                return self._eval_expr(node.body, active_scope)
            return self._eval_expr(node.orelse, active_scope)
        if isinstance(node, ast.Subscript):
            container = self._eval_expr(node.value, active_scope)
            key = self._eval_slice(node.slice, active_scope)
            return container[key]
        if isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            for part in node.values:
                if isinstance(part, ast.Constant):
                    parts.append(str(part.value))
                elif isinstance(part, ast.FormattedValue):
                    val = self._eval_expr(part.value, active_scope)
                    if part.conversion == 114:
                        val = repr(val)
                    elif part.conversion == 115:
                        val = str(val)
                    elif part.conversion == 97:
                        val = ascii(val)
                    if part.format_spec is not None:
                        spec = str(
                            self._eval_expr(part.format_spec, active_scope)
                        )
                        if len(spec) > 32:
                            raise ValueError("Format specification too long.")
                        parts.append(format(val, spec))
                    else:
                        parts.append(str(val))
                else:
                    parts.append(str(self._eval_expr(part, active_scope)))
            return "".join(parts)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            collected = self._eval_comprehension(
                node.generators, node.elt, active_scope
            )
            if isinstance(node, ast.SetComp):
                return set(collected)
            return collected
        if isinstance(node, ast.DictComp):
            return self._eval_dict_comprehension(
                node.generators, node.key, node.value, active_scope
            )
        if isinstance(node, ast.Call):
            assert isinstance(node.func, ast.Name)
            fn = self._builtins.get(node.func.id)
            if fn is None:
                raise NameError(f"name '{node.func.id}' is not defined")
            pos_args: list[Any] = []
            for arg in node.args:
                if isinstance(arg, ast.Starred):
                    pos_args.extend(self._eval_expr(arg.value, active_scope))
                else:
                    pos_args.append(self._eval_expr(arg, active_scope))
            kw_args: dict[str, Any] = {}
            for kw in node.keywords:
                val = self._eval_expr(kw.value, active_scope)
                if kw.arg is None:
                    if not isinstance(val, Mapping):
                        raise TypeError(
                            "Argument unpacking requires a mapping."
                        )
                    for k, v in val.items():
                        kw_args[str(k)] = v
                else:
                    kw_args[kw.arg] = val
            return fn(*pos_args, **kw_args)
        raise TypeError(
            f"Unsupported Python expression in diagnostic AST: {type(node).__name__}"
        )

    def _apply_compare(self, op: ast.cmpop, left: Any, right: Any) -> bool:
        if isinstance(op, ast.Eq):
            return bool(left == right)
        if isinstance(op, ast.NotEq):
            return bool(left != right)
        if isinstance(op, ast.Lt):
            return bool(left < right)
        if isinstance(op, ast.LtE):
            return bool(left <= right)
        if isinstance(op, ast.Gt):
            return bool(left > right)
        if isinstance(op, ast.GtE):
            return bool(left >= right)
        if isinstance(op, ast.Is):
            return left is right
        if isinstance(op, ast.IsNot):
            return left is not right
        if isinstance(op, ast.In):
            return bool(left in right)
        if isinstance(op, getattr(ast, "Not" + "In")):
            return bool(left not in right)
        raise TypeError(f"Unsupported comparison operator: {type(op).__name__}")

    def _iter_comprehension_scopes(
        self,
        generators: list[ast.comprehension],
        idx: int,
        child_scope: dict[str, Any],
        counter: list[int],
    ) -> Any:
        if idx == len(generators):
            yield child_scope
            return
        gen = generators[idx]
        iterable = self._eval_expr(gen.iter, child_scope)
        for item in iterable:
            counter[0] += 1
            self._tick()
            if counter[0] > _MAX_AST_COLLECTION_SIZE:
                raise RuntimeError(
                    f"Comprehension limit exceeded (max {_MAX_AST_COLLECTION_SIZE} items)."
                )
            self._assign_target(
                gen.target, item, child_scope, track_assigned=False
            )
            if all(self._eval_expr(cond, child_scope) for cond in gen.ifs):
                yield from self._iter_comprehension_scopes(
                    generators, idx + 1, child_scope, counter
                )

    def _eval_comprehension(
        self,
        generators: list[ast.comprehension],
        elt: ast.expr,
        parent_scope: dict[str, Any],
    ) -> list[Any]:
        child_scope = dict(parent_scope)
        counter = [0]
        return [
            self._eval_expr(elt, frame)
            for frame in self._iter_comprehension_scopes(
                generators, 0, child_scope, counter
            )
        ]

    def _eval_dict_comprehension(
        self,
        generators: list[ast.comprehension],
        key_expr: ast.expr,
        val_expr: ast.expr,
        parent_scope: dict[str, Any],
    ) -> dict[Any, Any]:
        child_scope = dict(parent_scope)
        counter = [0]
        out: dict[Any, Any] = {}
        for frame in self._iter_comprehension_scopes(
            generators, 0, child_scope, counter
        ):
            k = self._eval_expr(key_expr, frame)
            v = self._eval_expr(val_expr, frame)
            out[k] = v
        return out


def _evaluate_restricted_diagnostic_ast(
    code: str, input_payload: Mapping[str, object]
) -> SandboxBackendExecutionResult:
    """Evaluates a safe, bounded diagnostic snippet over `input_payload` without `exec`/`eval`.

    Supports assignments, arithmetic, comparisons, boolean ops, subscripts/slices, literals,
    comprehensions, bounded `for` loops and `if/else`, and safe builtins over a copy of
    `input_payload` (`input_data`, `readonly_input`, `incidents`, `runbooks`) without ever
    invoking Python's `eval()`, `exec()`, or OS subprocesses.

    Args:
        code: Restricted Python diagnostic snippet or expression.
        input_payload: Sanitized read-only dictionary derived from MCP tool output.

    Returns:
        `SandboxBackendExecutionResult` with JSON stdout on success or `exit_code=1` and error
        detail in `stderr` when a bounded runtime error occurs.

    Raises:
        PermissionError: If the AST contains imports, dunder attribute access, or arbitrary calls.
        ValueError: If `code` has invalid Python syntax (`E_SANDBOX_SYNTAX_ERROR`).
    """
    try:
        parsed_tree = ast.parse(code, mode="exec")
    except SyntaxError as syntax_exc:
        raise ValueError(
            f"E_SANDBOX_SYNTAX_ERROR: Invalid Python diagnostic syntax ({syntax_exc.msg})."
        ) from syntax_exc

    allowed_call_names = frozenset(
        {
            "len",
            "min",
            "max",
            "sum",
            "sorted",
            "print",
            "str",
            "int",
            "float",
            "bool",
            "dict",
            "list",
            "range",
        }
    )
    disallowed_stmt_types = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.While,
        ast.Lambda,
        ast.Try,
        ast.Raise,
        ast.Delete,
        ast.Yield,
        ast.YieldFrom,
        ast.Await,
        ast.AsyncFor,
    )
    for node in ast.walk(parsed_tree):
        if isinstance(
            node,
            (
                ast.Import,
                ast.ImportFrom,
                ast.Global,
                ast.Nonlocal,
                ast.With,
                ast.AsyncWith,
            ),
        ):
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_AST_IMPORT_DENIED: "
                "Hermetic diagnostic parser forbids module imports and context managers."
            )
        if isinstance(node, disallowed_stmt_types):
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_AST_CALL_DENIED: "
                f"Disallowed Python construct '{type(node).__name__}' in restricted diagnostic AST."
            )
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_AST_DUNDER_DENIED: "
                "Dunder attribute access is forbidden inside diagnostic expressions."
            )
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_AST_DUNDER_DENIED: "
                "Dunder identifier access is forbidden inside diagnostic expressions."
            )
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name)
            or node.func.id not in allowed_call_names
        ):
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_AST_CALL_DENIED: "
                "Only pure diagnostic builtins (len, min, max, sum, sorted, print, str, int, "
                "float, bool, dict, list, range) are permitted."
            )

    interpreter = _RestrictedAstInterpreter(input_payload)
    try:
        interpreter.run(parsed_tree.body)
    except PermissionError:
        raise
    except (
        ZeroDivisionError,
        NameError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        AttributeError,
        AssertionError,
        ArithmeticError,
        LookupError,
        RuntimeError,
    ) as runtime_exc:
        partial_stdout = "\n".join(
            "".join(interpreter.print_chunks).splitlines()
        )
        return SandboxBackendExecutionResult(
            stdout=partial_stdout,
            stderr=f"{type(runtime_exc).__name__}: {runtime_exc}",
            exit_code=1,
            backend_mode="HERMETIC_AGENT_SANDBOX_SANDBOX_SIMULATION",
        )

    stdout_lines = "".join(interpreter.print_chunks).splitlines()
    variables = {
        name: _json_safe_value(interpreter.env[name])
        for name in sorted(interpreter.assigned_names)
        if name in interpreter.env
    }
    incidents_obj = input_payload.get("incidents")
    incident_count = (
        len(incidents_obj) if isinstance(incidents_obj, list) else 0
    )
    runbooks_obj = input_payload.get("runbooks")
    runbook_count = len(runbooks_obj) if isinstance(runbooks_obj, list) else 0
    stdout_payload = json.dumps(
        {
            "workspace": "/workspace",
            "user": "appuser",
            "ast_verified_statements": len(parsed_tree.body),
            "input_incident_count": incident_count,
            "input_runbook_count": runbook_count,
            "input_keys": sorted(str(key) for key in input_payload),
            "stdout_lines": stdout_lines,
            "variables": variables,
        },
        sort_keys=True,
        default=str,
    )
    return SandboxBackendExecutionResult(
        stdout=stdout_payload,
        stderr="",
        exit_code=0,
        backend_mode="HERMETIC_AGENT_SANDBOX_SANDBOX_SIMULATION",
    )
