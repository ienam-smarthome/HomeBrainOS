"""One-shot validation bootstrap; removed by the live-power release patch."""
from __future__ import annotations
import runpy
import sysconfig
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name("sitecustomize.py")), run_name="__release_patch__")
stdlib_ast = Path(sysconfig.get_path("stdlib")) / "ast.py"
exec(compile(stdlib_ast.read_text(encoding="utf-8"), str(stdlib_ast), "exec"), globals(), globals())
