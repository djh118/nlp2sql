import asyncio
import json
import threading
from typing import Optional

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.agent.context import DataAgentContext
from app.agent.callbacks import langfuse_handler
from app.clients.embedding_client import embedding_client_manager
from app.clients.es_client import es_client_manager
from app.clients.mysql_client import dw_client_manager, meta_client_manager
from app.clients.qdrant_client import qdrant_client_manager
from app.config.app_config import app_config
from app.core.logging import logger
from app.feishu.card_builder import build_result_card
from app.feishu.client import feishu_client
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_repository_qdrant import ColumnQdrantRepository
from app.repositories.qdrant.metric_repository_qdrant import MetricQdrantRepository


class FeishuWSBot:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._ws_client = None
        self._stop_event = threading.Event()

    def _build_ws_client(self):
        from lark_oapi.ws import Client as WSClient

        def _noop(*args, **kwargs):
            pass

        handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(
            self._on_message
        ).register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
            _noop
        ).build()
        return WSClient(
            app_id=app_config.feishu.app_id,
            app_secret=app_config.feishu.app_secret,
            event_handler=handler,
            auto_reconnect=True,
        )

    def _on_message(self, data: P2ImMessageReceiveV1) -> None:
        event = data.event
        if event is None or event.message is None:
            return
        message = event.message
        if message.message_type != "text":
            return

        try:
            content = json.loads(message.content)
            query_text = content.get("text", "").strip()
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"飞书消息解析失败: {message.content}")
            return

        if not query_text:
            return

        message_id = message.message_id
        logger.info(f"飞书收到消息: {query_text[:50]}")

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.error("飞书 WS Bot 没有运行中的事件循环")
            return
        asyncio.run_coroutine_threadsafe(self._handle_query(query_text, message_id), loop)

    async def _handle_query(self, text: str, message_id: str):
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

    def start(self):
        if self._thread and self._thread.is_alive():
            logger.warning("飞书 WS Bot 已在运行")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        import lark_oapi.ws.client as _ws_client_mod

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _ws_client_mod.loop = loop

        self._ws_client = self._build_ws_client()

        logger.info("飞书 WS Bot 已启动（长连接模式）")
        try:
            self._ws_client.start()
        except Exception as e:
            logger.error(f"飞书 WS Bot 异常退出: {e}")

    def stop(self):
        self._stop_event.set()
        if self._ws_client is not None:
            try:
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(loop.stop)
            except Exception as e:
                logger.warning(f"飞书 WS Bot 断开时异常: {e}")
        logger.info("飞书 WS Bot 已停止")


feishu_ws_bot = FeishuWSBot()
