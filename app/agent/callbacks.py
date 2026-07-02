from dotenv import load_dotenv

load_dotenv()

from app.config.app_config import app_config
from app.core.logging import logger

langfuse_handler = None

if app_config.langfuse.enabled:
    try:
        from langfuse.langchain import CallbackHandler

        langfuse_handler = CallbackHandler()
        logger.info("LangFuse callback handler 初始化成功")
    except Exception as e:
        logger.error(f"LangFuse callback handler 初始化失败: {e}")
