"""Real, read-only public browser smoke check. No model or search fixtures."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from app.schemas import Browse
from app.tools import browse


async def main():
    report = {"date": datetime.now(timezone.utc).isoformat(), "mode": "live-public-browser", "url": "https://example.com", "uses_model": False}
    try:
        result = await browse(Browse(url=report["url"]), "live")
        assert "Example Domain" in result["sources"][0]["excerpt"]
        assert result["sources"][0]["fixture"] is False
        report.update(status="passed", result=result)
    except Exception as exc:
        report.update(status="blocked", reason=type(exc).__name__ + ": " + str(exc)[:600])
    output = Path(__file__).resolve().parents[2] / "evaluation" / "public-browser-result.json"
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


asyncio.run(main())
