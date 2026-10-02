# Tools

All tools implement `name`, `description`, JSON-compatible input/output
schemas, and async `execute()`.

- `CalculatorTool`: restricted numeric expressions.
- `MathTool`: safe AST parser plus SymPy for algebra, equations,
  factorization, expansion, calculus, matrices, and basic statistics.
- `PythonTool`: restricted AST interpreter; no `exec`, `eval`, imports,
  attributes, filesystem, network, subprocess, or OS access.
- `KnowledgeSearchTool`: retrieves untrusted document passages.

ToolRouter only executes explicitly registered tools. Python execution has
time, instruction, collection, memory approximation, and output limits.
