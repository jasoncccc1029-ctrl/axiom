"""Restricted Python AST interpreter.

No exec/eval, imports, attributes, filesystem, network, subprocess or OS calls.
This intentionally supports a small educational subset of Python.
"""

from __future__ import annotations

import ast
import operator
import re
import time
from typing import Any

from app.config import settings
from app.tools.base import Tool, ToolResult


class SandboxViolation(ValueError):
    pass


class SafePythonInterpreter:
    BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    COMPARE_OPS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }
    SAFE_CALLS = {
        "len": len,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sorted": sorted,
    }

    def __init__(
        self,
        *,
        timeout_seconds: float = 3.0,
        output_limit: int = 20_000,
        max_steps: int = 20_000,
        memory_limit_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.output_limit = output_limit
        self.max_steps = max_steps
        self.memory_limit_bytes = memory_limit_bytes
        self.started = 0.0
        self.steps = 0
        self.env: dict[str, Any] = {}
        self.stdout: list[str] = []

    def run(self, code: str) -> str:
        if len(code) > 20_000:
            raise SandboxViolation("Code is too long")
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise SandboxViolation(f"SyntaxError: {exc.msg}") from exc
        if sum(1 for _ in ast.walk(tree)) > 2_000:
            raise SandboxViolation("Program is too complex")
        self.started = time.perf_counter()
        for statement in tree.body:
            self._statement(statement)
        return "".join(self.stdout)

    def _tick(self) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise SandboxViolation("Instruction limit exceeded")
        if time.perf_counter() - self.started > self.timeout_seconds:
            raise SandboxViolation("Execution timed out")
        if len(repr(self.env)) + sum(len(item) for item in self.stdout) > self.memory_limit_bytes:
            raise SandboxViolation("Memory limit exceeded")

    def _statement(self, node: ast.stmt) -> None:
        self._tick()
        if isinstance(node, ast.Expr):
            self._expr(node.value)
            return
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            value = self._expr(node.value)
            self._assign(node.targets[0], value)
            return
        if isinstance(node, ast.AugAssign):
            current = self._expr(node.target)
            operation = self.BIN_OPS.get(type(node.op))
            if not operation:
                raise SandboxViolation("Unsupported augmented operation")
            self._assign(node.target, operation(current, self._expr(node.value)))
            return
        if isinstance(node, ast.If):
            branch = node.body if self._expr(node.test) else node.orelse
            for statement in branch:
                self._statement(statement)
            return
        if isinstance(node, ast.For):
            values = self._expr(node.iter)
            if not isinstance(values, (range, list, tuple)):
                raise SandboxViolation("For loop requires range/list/tuple")
            if len(values) > 5_000:
                raise SandboxViolation("Loop limit exceeded")
            for value in values:
                self._assign(node.target, value)
                for statement in node.body:
                    self._statement(statement)
            return
        if isinstance(node, ast.Pass):
            return
        raise SandboxViolation(f"Statement not allowed: {node.__class__.__name__}")

    def _expr(self, node: ast.AST) -> Any:
        self._tick()
        if isinstance(node, ast.Constant) and isinstance(
            node.value, (str, int, float, bool, type(None))
        ):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in self.env:
                raise SandboxViolation(f"Unknown name: {node.id}")
            return self.env[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in self.BIN_OPS:
            left, right = self._expr(node.left), self._expr(node.right)
            if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and abs(right) > 1000:
                raise SandboxViolation("Exponent too large")
            return self.BIN_OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
            value = self._expr(node.operand)
            if isinstance(node.op, ast.Not):
                return not value
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BoolOp):
            values = [self._expr(value) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare):
            left = self._expr(node.left)
            for operation, comparator in zip(node.ops, node.comparators):
                right = self._expr(comparator)
                fn = self.COMPARE_OPS.get(type(operation))
                if not fn or not fn(left, right):
                    return False
                left = right
            return True
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = [self._expr(item) for item in node.elts]
            if len(values) > 10_000:
                raise SandboxViolation("Collection too large")
            if isinstance(node, ast.Tuple):
                return tuple(values)
            if isinstance(node, ast.Set):
                return set(values)
            return values
        if isinstance(node, ast.Dict):
            return {
                self._expr(key): self._expr(value)
                for key, value in zip(node.keys, node.values)
            }
        if isinstance(node, ast.Subscript):
            return self._expr(node.value)[self._expr(node.slice)]
        if isinstance(node, ast.Slice):
            return slice(
                self._expr(node.lower) if node.lower else None,
                self._expr(node.upper) if node.upper else None,
                self._expr(node.step) if node.step else None,
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = [self._expr(argument) for argument in node.args]
            if node.keywords:
                raise SandboxViolation("Keyword arguments are not allowed")
            if node.func.id == "print":
                output = " ".join(str(value) for value in args) + "\n"
                if sum(len(item) for item in self.stdout) + len(output) > self.output_limit:
                    raise SandboxViolation("Output limit exceeded")
                self.stdout.append(output)
                return None
            if node.func.id == "range":
                if len(args) not in {1, 2, 3}:
                    raise SandboxViolation("range expects 1-3 arguments")
                value = range(*(int(argument) for argument in args))
                if len(value) > 5_000:
                    raise SandboxViolation("range limit exceeded")
                return value
            function = self.SAFE_CALLS.get(node.func.id)
            if function:
                return function(*args)
            raise SandboxViolation(f"Call not allowed: {node.func.id}")
        # Attribute access blocks os.system, pathlib, network clients, dunder escapes, etc.
        if isinstance(node, (ast.Attribute, ast.Lambda, ast.ListComp, ast.DictComp, ast.GeneratorExp)):
            raise SandboxViolation(f"Expression not allowed: {node.__class__.__name__}")
        raise SandboxViolation(f"Expression not allowed: {node.__class__.__name__}")

    def _assign(self, target: ast.AST, value: Any) -> None:
        if isinstance(target, ast.Name) and not target.id.startswith("_"):
            self.env[target.id] = value
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            if not isinstance(value, (tuple, list)) or len(value) != len(target.elts):
                raise SandboxViolation("Invalid unpacking")
            for child, item in zip(target.elts, value):
                self._assign(child, item)
            return
        if isinstance(target, ast.Subscript):
            container = self._expr(target.value)
            container[self._expr(target.slice)] = value
            return
        raise SandboxViolation("Assignment target not allowed")


class PythonTool(Tool):
    name = "python"
    description = "Run a restricted educational Python subset without OS/network/filesystem access."
    input_schema = {
        "type": "object",
        "required": ["code"],
        "properties": {"code": {"type": "string"}},
    }
    output_schema = {
        "type": "object",
        "properties": {
            "stdout": {"type": "string"},
            "stderr": {"type": "string"},
            "exit_code": {"type": "integer"},
            "execution_time": {"type": "number"},
        },
    }

    async def execute(self, payload: dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        code = _extract_code(str(payload.get("code") or ""))
        interpreter = SafePythonInterpreter(
            timeout_seconds=settings.python_timeout_seconds,
            output_limit=settings.python_output_limit,
        )
        try:
            stdout = interpreter.run(code)
            elapsed = (time.perf_counter() - started) * 1000
            return ToolResult(
                ok=True,
                output={
                    "stdout": stdout,
                    "stderr": "",
                    "exit_code": 0,
                    "execution_time": round(elapsed, 3),
                    "verified": True,
                    "sandbox": "restricted_ast",
                },
                execution_time_ms=round(elapsed, 3),
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return ToolResult(
                ok=False,
                output={
                    "stdout": "".join(interpreter.stdout)[: settings.python_output_limit],
                    "stderr": str(exc)[:2000],
                    "exit_code": 1,
                    "execution_time": round(elapsed, 3),
                    "verified": False,
                    "sandbox": "restricted_ast",
                },
                error=str(exc)[:300],
                execution_time_ms=round(elapsed, 3),
            )


def _extract_code(value: str) -> str:
    match = re.search(r"```(?:python|py)?\s*([\s\S]*?)```", value, flags=re.IGNORECASE)
    return match.group(1).strip() if match else value.strip()
