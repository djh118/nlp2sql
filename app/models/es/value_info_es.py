from typing import TypedDict


class ValueInfoES(TypedDict):
    id: str
    value: str
    type: str
    column_id: str
    column_name: str
    table_id: str
    table_name: str


