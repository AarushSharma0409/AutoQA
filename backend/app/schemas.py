from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateTask(StrictModel):
    goal: str = Field(min_length=3, max_length=8000)
    file_ids: list[str] = Field(default_factory=list, max_length=10)


class Ingest(StrictModel):
    file_id: str


class Analyze(StrictModel):
    file_id: str
    category_column: str = "category"
    value_column: str = "revenue"


class Search(StrictModel):
    query: str = Field(min_length=3, max_length=400)


class Browse(StrictModel):
    url: str = Field(max_length=2000)


class Python(StrictModel):
    code: str = Field(min_length=1, max_length=16000)
    file_ids: list[str] = Field(default_factory=list, max_length=5)


class Report(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    findings: str = Field(max_length=12000)
    hypotheses: str = Field(max_length=6000)
    source_ids: list[str] = Field(default_factory=list, max_length=20)


class Finish(StrictModel):
    summary: str = Field(min_length=1, max_length=3000)


TOOLS = {"ingest": Ingest, "analyze_csv": Analyze, "search": Search, "browse": Browse, "python": Python, "report": Report, "finish": Finish}


class Decision(StrictModel):
    tool: Literal["ingest", "analyze_csv", "search", "browse", "python", "report", "finish"]
    arguments: dict
    summary: str = Field(max_length=500)


class Approval(StrictModel):
    digest: str
    approved: bool
