import asyncio

from langchain.chat_models import init_chat_model

from app.config.app_config import app_config
from app.agent.callbacks import langfuse_handler
from app.core.fault_tolerance.retry import async_retry, RetryConfig
from app.core.logging import logger

model_name = app_config.llm.model_name
api_key = app_config.llm.api_key

llm = init_chat_model(model=model_name, api_key=api_key, temperature=0)
backup_llm = init_chat_model(
    model=app_config.fault_tolerance.llm_fallback.backup_model_name,
    api_key=api_key,
    temperature=0,
)

if langfuse_handler is not None:
    llm.callbacks = [langfuse_handler]


async def invoke_llm_with_fallback(prompt, input_vars, timeout=30):
    main_config = RetryConfig(max_retries=1, base_delay=2.0, is_read_only=True)
    last_error = None
    for attempt in range(main_config.max_retries + 1):
        try:
            result = await asyncio.wait_for(
                llm.ainvoke(prompt.format(**input_vars)),
                timeout=timeout,
            )
            return result.content if hasattr(result, "content") else str(result)
        except Exception as e:
            last_error = e
            logger.warning(f"[llm] 主模型调用失败 (attempt {attempt + 1}): {e}")
            if attempt < main_config.max_retries:
                await asyncio.sleep(main_config.base_delay * (main_config.backoff_factor ** attempt))
    logger.warning(f"[llm] 主模型失败，切换备用模型: {last_error}")
    try:
        backup_result = await asyncio.wait_for(
            backup_llm.ainvoke(prompt.format(**input_vars)),
            timeout=timeout,
        )
        return backup_result.content if hasattr(backup_result, "content") else str(backup_result)
    except Exception as e:
        logger.error(f"[llm] 备用模型也失败: {e}")
        raise


if __name__ == "__main__":
    async def test():
        print(await llm.ainvoke("中国的首都是哪里？"))

    print(asyncio.run(test()))
