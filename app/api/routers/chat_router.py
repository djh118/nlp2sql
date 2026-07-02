import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import StreamingResponse

from app.api.deps import get_chat_service
from app.schemas.chat import ExportSchema, QuerySchema
from app.service.export_service import rows_to_excel

chat_router = APIRouter(prefix="/api")


@chat_router.post("/query")
async def date_query(query: QuerySchema, chat_service=Depends(get_chat_service)):
    async def event_stream():
        try:
            async for chunk in chat_service.stream_chat(query.query):
                yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )


@chat_router.post("/export")
async def export_data(body: ExportSchema):
    try:
        buf = rows_to_excel(body.data)
        encoded_filename = body.filename.encode("utf-8").decode("iso-8859-1")
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}.xlsx"},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"导出失败: {str(e)}"})
