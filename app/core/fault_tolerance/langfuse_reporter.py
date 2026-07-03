from dotenv import load_dotenv

load_dotenv()

import time
import uuid
from app.config.app_config import app_config
from app.core.logging import logger


_langfuse_client = None


def _get_client():
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client
    if not app_config.langfuse.enabled:
        return None
    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse()
        logger.info("[langfuse_reporter] 初始化成功")
        return _langfuse_client
    except Exception as e:
        logger.warning(f"[langfuse_reporter] 初始化失败: {e}")
        return None


def report_fault_event(
    category: str,
    level: str,
    tag: str,
    message: str,
    request_id: str = "",
    metadata: dict | None = None,
):
    client = _get_client()
    if client is None:
        return

    trace_id = f"fault_{request_id or uuid.uuid4().hex}_{int(time.time() * 1000)}"
    event_metadata = {
        "error_category": category,
        "fault_tolerance_level": level,
        "error_tag": tag,
        "message": message,
        "request_id": request_id,
    }
    if metadata:
        event_metadata.update(metadata)

    try:
        client.create_event(
            trace_context={"trace_id": trace_id},
            name=f"fault.{category}.{level}",
            input={"request_id": request_id, "message": message[:500]},
            metadata=event_metadata,
            status_message=message[:500],
            level="WARNING" if level in ("retry", "degrade") else "ERROR",
        )
        client.create_score(
            name=f"fault_tolerance_{category}",
            value=1.0,
            trace_id=trace_id,
            comment=message[:500],
            metadata={"category": category, "level": level, "tag": tag},
        )
        client.flush()
    except Exception as e:
        logger.debug(f"[langfuse_reporter] 推送失败: {e}")
