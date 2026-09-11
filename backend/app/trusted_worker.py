"""Cancellable subprocess for FIXED application tools, never model-generated code."""

import json
import sys
from .schemas import TOOLS
from .tools import ingest, analyze, report

if sys.platform != "win32":
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))

request = json.loads(sys.stdin.read())
try:
    args = TOOLS[request["tool"]].model_validate(request["arguments"])
    if request["tool"] == "ingest":
        result = ingest(request["task_id"], args)
    elif request["tool"] == "analyze_csv":
        result = analyze(request["task_id"], args)
    elif request["tool"] == "report":
        result = report(args, request["checkpoint"], request["mode"])
    else:
        raise ValueError("Not a fixed application tool")
    print(json.dumps({"result": result}))
except Exception as exc:
    print(json.dumps({"error": str(exc)[:400] if isinstance(exc, ValueError) else type(exc).__name__ + ": invalid input or tool failure"}))
