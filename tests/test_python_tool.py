"""Python restricted AST sandbox tests."""

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.tools.python import PythonTool  # noqa: E402


@pytest.mark.asyncio
async def test_python_tool_executes_safe_arithmetic_and_loop():
    result = await PythonTool().execute(
        {"code": "total = 0\nfor i in range(5):\n    total += i\nprint(total)"}
    )
    assert result.ok is True
    assert result.output["stdout"] == "10\n"
    assert result.output["stderr"] == ""
    assert result.output["exit_code"] == 0
    assert result.output["verified"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code",
    [
        "import os\nprint(os.getcwd())",
        "open('secret.txt').read()",
        "__import__('subprocess')",
        "x = (1).__class__",
        "while True:\n    pass",
        "import socket",
    ],
)
async def test_python_tool_blocks_dangerous_capabilities(code):
    result = await PythonTool().execute({"code": code})
    assert result.ok is False
    assert result.output["exit_code"] == 1
    assert result.output["verified"] is False


@pytest.mark.asyncio
async def test_python_tool_enforces_loop_and_output_limits():
    loop = await PythonTool().execute({"code": "for i in range(100000):\n    print(i)"})
    assert loop.ok is False
    assert "limit" in loop.error.lower()


@pytest.mark.asyncio
async def test_python_tool_extracts_markdown_fence():
    result = await PythonTool().execute({"code": "```python\nprint(sum([1,2,3]))\n```"})
    assert result.ok is True
    assert result.output["stdout"] == "6\n"
