import sys
from pathlib import Path
from genvm_linter import GenVMLinter

contract_path = Path("contracts/build/Solvent.bundled.py")
code = contract_path.read_text(encoding="utf-8")

linter = GenVMLinter()
issues = linter.lint_source(code)

print(f"Total issues found: {len(issues)}")
for issue in issues:
    print(f" - {issue}")

if len(issues) == 0:
    print("SUCCESS: GenLayer bundle passed AST linting with 0 issues!")
    sys.exit(0)
else:
    sys.exit(1)
