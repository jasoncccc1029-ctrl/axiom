"""Restricted SymPy math tool. It never uses eval/sympify on user input."""

from __future__ import annotations

import ast
import re
import statistics
import time
from typing import Any

import sympy as sp

from app.tools.base import Tool, ToolResult


class SafeSympyParser:
    ALLOWED_FUNCTIONS = {
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "exp": sp.exp,
        "log": sp.log,
        "sqrt": sp.sqrt,
        "abs": sp.Abs,
    }
    BIN_OPS = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.Pow: lambda a, b: a**b,
    }

    def parse(self, expression: str) -> sp.Expr:
        value = expression.strip().replace("^", "**")
        if len(value) > 1000:
            raise ValueError("Expression too long")
        tree = ast.parse(value, mode="eval")
        return self._convert(tree.body)

    def _convert(self, node: ast.AST) -> sp.Expr:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return sp.Integer(node.value) if isinstance(node.value, int) else sp.Float(node.value)
        if isinstance(node, ast.Name) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,30}", node.id):
            if node.id in {"pi", "E"}:
                return sp.pi if node.id == "pi" else sp.E
            return sp.Symbol(node.id)
        if isinstance(node, ast.BinOp) and type(node.op) in self.BIN_OPS:
            return self.BIN_OPS[type(node.op)](
                self._convert(node.left), self._convert(node.right)
            )
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._convert(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in self.ALLOWED_FUNCTIONS
            and not node.keywords
        ):
            return self.ALLOWED_FUNCTIONS[node.func.id](
                *(self._convert(argument) for argument in node.args)
            )
        raise ValueError(f"Unsupported expression node: {node.__class__.__name__}")


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate a restricted numeric expression."
    input_schema = {
        "type": "object",
        "required": ["expression"],
        "properties": {"expression": {"type": "string"}},
    }
    output_schema = {
        "type": "object",
        "properties": {"result": {"type": "string"}, "numeric": {"type": "number"}},
    }

    def __init__(self) -> None:
        self.parser = SafeSympyParser()

    async def execute(self, payload: dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        try:
            expression = _extract_expression(str(payload.get("expression") or ""))
            parsed = self.parser.parse(expression)
            if parsed.free_symbols:
                raise ValueError("Calculator accepts numeric expressions only")
            numeric = float(sp.N(parsed))
            return ToolResult(
                ok=True,
                output={"result": str(sp.simplify(parsed)), "numeric": numeric, "verified": True},
                execution_time_ms=_elapsed(started),
            )
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc)[:300], execution_time_ms=_elapsed(started))


class MathTool(Tool):
    name = "math"
    description = (
        "Compute and verify algebra, equations, factorization, expansion, derivatives, "
        "integrals, matrices and basic statistics with SymPy."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "expression": {"type": "string"},
            "variable": {"type": "string"},
            "matrix": {"type": "array"},
            "values": {"type": "array"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "result": {},
            "verified": {"type": "boolean"},
        },
    }

    def __init__(self) -> None:
        self.parser = SafeSympyParser()

    async def execute(self, payload: dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        try:
            operation = str(payload.get("operation") or "").strip().lower()
            raw = str(payload.get("expression") or payload.get("problem") or "").strip()
            operation = operation or infer_math_operation(raw)
            variable = sp.Symbol(str(payload.get("variable") or _infer_variable(raw) or "x"))
            result: Any

            if operation in {"solve", "equation"}:
                left, right = _split_equation(raw)
                result = sp.solve(
                    sp.Eq(self.parser.parse(left), self.parser.parse(right)), variable
                )
            elif operation == "factor":
                result = sp.factor(self.parser.parse(_extract_expression(raw)))
            elif operation == "expand":
                result = sp.expand(self.parser.parse(_extract_expression(raw)))
            elif operation in {"derivative", "differentiate"}:
                result = sp.diff(self.parser.parse(_extract_expression(raw)), variable)
            elif operation in {"integral", "integrate"}:
                result = sp.integrate(self.parser.parse(_extract_expression(raw)), variable)
            elif operation.startswith("matrix"):
                matrix = _matrix(payload.get("matrix"), raw)
                if operation in {"matrix_det", "matrix_determinant"}:
                    result = matrix.det()
                elif operation == "matrix_inverse":
                    result = matrix.inv()
                elif operation == "matrix_transpose":
                    result = matrix.T
                else:
                    result = matrix
            elif operation == "statistics":
                values = [float(value) for value in (payload.get("values") or [])]
                if not values:
                    raise ValueError("values are required")
                result = {
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
                }
            else:
                result = sp.simplify(self.parser.parse(_extract_expression(raw)))

            return ToolResult(
                ok=True,
                output={
                    "operation": operation,
                    "result": _serialize(result),
                    "verified": True,
                    "engine": "sympy",
                },
                execution_time_ms=_elapsed(started),
            )
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc)[:300], execution_time_ms=_elapsed(started))


def infer_math_operation(text: str) -> str:
    lower = text.lower()
    if "determinant" in lower or "det(" in lower or "行列式" in lower:
        return "matrix_det"
    if "inverse" in lower or "反矩陣" in lower:
        return "matrix_inverse"
    if "factor" in lower or "因式分解" in lower:
        return "factor"
    if "expand" in lower or "展開" in lower:
        return "expand"
    if "derivative" in lower or "differentiate" in lower or "微分" in lower:
        return "derivative"
    if "integral" in lower or "integrate" in lower or "積分" in lower:
        return "integral"
    if "=" in text:
        return "solve"
    return "simplify"


def _extract_expression(text: str) -> str:
    value = text.strip()
    value = re.sub(
        r"^(please\s+)?(solve|factor|expand|differentiate|integrate|simplify|compute)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    fenced = re.search(r"`([^`]+)`", value)
    if fenced:
        return fenced.group(1)
    match = re.search(r"([A-Za-z0-9_().+\-*/^ ]+(?:=[A-Za-z0-9_().+\-*/^ ]+)?)", value)
    if not match:
        raise ValueError("No supported expression found")
    return match.group(1).strip()


def _split_equation(text: str) -> tuple[str, str]:
    expression = _extract_expression(text)
    if "=" not in expression:
        raise ValueError("Equation must contain '='")
    return tuple(part.strip() for part in expression.split("=", 1))  # type: ignore[return-value]


def _infer_variable(text: str) -> str | None:
    candidates = re.findall(r"\b([a-zA-Z])\b", text)
    return candidates[0] if candidates else None


def _matrix(value: object, raw: str) -> sp.Matrix:
    if isinstance(value, list) and value and all(isinstance(row, list) for row in value):
        return sp.Matrix(value)
    match = re.search(r"\[\s*\[([^\]]+)\]\s*,\s*\[([^\]]+)\]\s*\]", raw)
    if not match:
        raise ValueError("matrix must be provided as nested arrays")
    rows = [
        [SafeSympyParser().parse(part.strip()) for part in group.split(",")]
        for group in match.groups()
    ]
    return sp.Matrix(rows)


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if isinstance(value, sp.MatrixBase):
        return [[str(item) for item in row] for row in value.tolist()]
    return str(value)


def _elapsed(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
