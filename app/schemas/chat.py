from pydantic import BaseModel


class QuerySchema(BaseModel):
    query: str


class ExportSchema(BaseModel):
    data: list[dict]
    filename: str = "export"
