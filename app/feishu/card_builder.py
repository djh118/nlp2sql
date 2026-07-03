import json
from decimal import Decimal
from datetime import date, datetime
from typing import Any


MAX_ROWS = 10
MAX_CELL_LEN = 50


def _fmt(val: Any) -> str:
    if isinstance(val, Decimal):
        return f"{float(val):.2f}"
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if val is None:
        return "NULL"
    s = str(val)
    if len(s) > MAX_CELL_LEN:
        s = s[: MAX_CELL_LEN - 3] + "..."
    return s


def _cell(text: str, bold: bool = False) -> dict:
    content = f"**{text}**" if bold else text
    return {
        "tag": "column",
        "width": "weighted",
        "weight": 1,
        "vertical_align": "top",
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": content}}
        ],
    }


def build_result_card(data: list[dict], title: str = "📊 查询结果") -> str:
    if not data:
        raise ValueError("data is empty")

    columns = list(data[0].keys())

    header_cols = [_cell(c, bold=True) for c in columns]
    elements: list[dict] = [
        {
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "grey",
            "columns": header_cols,
        }
    ]

    for i, row in enumerate(data[:MAX_ROWS]):
        row_cols = [_cell(_fmt(row.get(c, ""))) for c in columns]
        el: dict = {
            "tag": "column_set",
            "flex_mode": "none",
            "columns": row_cols,
        }
        if i % 2 == 0:
            el["background_style"] = "default"
        elements.append(el)

    if len(data) > MAX_ROWS:
        elements.append(
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"... 仅显示前 {MAX_ROWS} 行，共 {len(data)} 行",
                    }
                ],
            }
        )

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "blue",
        },
        "elements": elements,
    }

    return json.dumps(card, ensure_ascii=False)
