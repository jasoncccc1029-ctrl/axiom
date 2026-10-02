"""Restricted SymPy MathTool and verifier tests."""

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.schemas import VerificationStatus  # noqa: E402
from app.agent.verifier import Verifier  # noqa: E402
from app.tools.math import CalculatorTool, MathTool, SafeSympyParser  # noqa: E402


@pytest.mark.asyncio
async def test_math_solve_equation():
    result = await MathTool().execute(
        {"operation": "solve", "expression": "2*x + 4 = 10", "variable": "x"}
    )
    assert result.ok is True
    assert result.output["result"] == ["3"]
    assert result.output["engine"] == "sympy"
    assert Verifier().verify({"math": result}) == VerificationStatus.VERIFIED


@pytest.mark.asyncio
async def test_math_factor_expand_derivative_integral():
    tool = MathTool()
    factor = await tool.execute({"operation": "factor", "expression": "x^2 - 1"})
    expand = await tool.execute({"operation": "expand", "expression": "(x+1)^2"})
    derivative = await tool.execute({"operation": "derivative", "expression": "x^3"})
    integral = await tool.execute({"operation": "integral", "expression": "2*x"})
    assert factor.output["result"] == "(x - 1)*(x + 1)"
    assert expand.output["result"] == "x**2 + 2*x + 1"
    assert derivative.output["result"] == "3*x**2"
    assert integral.output["result"] == "x**2"


@pytest.mark.asyncio
async def test_math_matrix_and_statistics():
    determinant = await MathTool().execute(
        {"operation": "matrix_det", "matrix": [[1, 2], [3, 4]]}
    )
    stats = await MathTool().execute(
        {"operation": "statistics", "values": [1, 2, 3, 4]}
    )
    assert determinant.ok is True
    assert determinant.output["result"] == "-2"
    assert stats.output["result"]["mean"] == "2.5"


@pytest.mark.asyncio
async def test_calculator_rejects_symbols():
    result = await CalculatorTool().execute({"expression": "x + 1"})
    assert result.ok is False


def test_safe_parser_rejects_attribute_and_import_calls():
    parser = SafeSympyParser()
    with pytest.raises(ValueError):
        parser.parse("x.__class__")
    with pytest.raises(ValueError):
        parser.parse("__import__('os')")
