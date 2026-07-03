import hashlib
import json
import asyncio

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.agent.context import DataAgentContext
from app.agent.callbacks import langfuse_handler
from app.clients.embedding_client import embedding_client_manager
from app.clients.es_client import es_client_manager
from app.clients.mysql_client import dw_client_manager, meta_client_manager
from app.clients.qdrant_client import qdrant_client_manager
from app.core.logging import logger
from app.feishu.card_builder import build_result_card
from app.feishu.client import feishu_client
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_repository_qdrant import ColumnQdrantRepository
from app.repositories.qdrant.metric_repository_qdrant import MetricQdrantRepository

feishu_router = APIRouter(prefix="/feishu")


def _verify_signature(body: bytes, timestamp: str, nonce: str, sign: str) -> bool:
    from app.config.app_config import app_config
    token = app_config.feishu.app_secret
    s = "".join(sorted([token, timestamp, nonce]))
    return hashlib.sha1(s.encode("utf-8")).hexdigest() == sign


async def _process_message(text: str, message_id: str):
    await feishu_client.reply_text(message_id, f"正在查询: {text[:50]}...")

    try:
        async with (
            meta_client_manager.session_factory() as meta_session,
            dw_client_manager.session_factory() as dw_session,
        ):
            context = DataAgentContext(
                metric_qdrant_repository=MetricQdrantRepository(qdrant_client_manager.client),
                value_es_repository=ValueESRepository(es_client_manager.client),
                column_qdrant_repository=ColumnQdrantRepository(qdrant_client_manager.client),
                embedding_client=embedding_client_manager.client,
                meta_mysql_repository=MetaMySQLRepository(meta_session),
                dw_mysql_repository=DWMySQLRepository(dw_session),
            )
            config = {"callbacks": [langfuse_handler]} if langfuse_handler else {}

            result_data = None
            error_msg = ""
            async for chunk in graph.astream(
                input=DataAgentState(query=text),
                context=context,
                stream_mode="custom",
                config=config,
            ):
                stage = chunk.get("stage", "")
                if "result" in chunk and chunk["result"] is not None:
                    result_data = chunk["result"]
                elif stage == "SQL安全拦截":
                    error_msg = chunk.get("error", "SQL 被安全拦截")

            if result_data is not None:
                card_json = build_result_card(result_data)
                await feishu_client.reply_card(message_id, card_json)
            elif error_msg:
                await feishu_client.reply_text(message_id, f"查询失败: {error_msg}")
            else:
                await feishu_client.reply_text(message_id, "查询完成，但未能获取到结果数据")

    except Exception as e:
        logger.error(f"飞书查询失败: {e}")
        await feishu_client.reply_text(message_id, f"查询失败: {str(e)}")


@feishu_router.post("/event")
async def feishu_event(request: Request):
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid json")

    ts = payload.get("header", {}).get("timestamp") or request.headers.get("X-Timestamp")
    nonce = payload.get("header", {}).get("nonce") or request.headers.get("X-Nonce", "0")
    sign = payload.get("header", {}).get("signature") or request.headers.get("X-Signature", "")

    if ts and sign:
        if not _verify_signature(body, str(ts), str(nonce), sign):
            logger.warning("飞书签名验证失败")
            raise HTTPException(status_code=403, detail="signature verification failed")

    event_type = payload.get("type", "")
    if event_type == "url_verification":
        return JSONResponse({"challenge": payload.get("challenge")})

    header = payload.get("header", {})
    event = header.get("event_type", "") or event_type

    if event == "im.message.receive_v1":
        event_body = payload.get("event", payload)
        message = event_body.get("message", {})
        message_id = message.get("message_id", "")
        content_str = message.get("content", "{}")
        msg_type = message.get("message_type", "")

        if msg_type == "text":
            try:
                content = json.loads(content_str)
            except json.JSONDecodeError:
                content = {"text": content_str}
            query_text = content.get("text", "").strip()
            if query_text:
                asyncio.ensure_future(_process_message(query_text, message_id))

    return JSONResponse({"code": 0, "msg": "success"})
