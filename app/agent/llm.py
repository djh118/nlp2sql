import asyncio

from langchain.chat_models import init_chat_model

from app.config.app_config import app_config
from app.agent.callbacks import langfuse_handler
from app.core.fault_tolerance.retry import async_retry, RetryConfig
from app.core.logging import logger

model_name = app_config.llm.model_name
sql_model_name = app_config.llm.sql_model_name
api_key = app_config.llm.api_key

llm = init_chat_model(
    model=model_name, model_provider="deepseek", api_key=api_key, temperature=0,
)
sql_llm = init_chat_model(
    model=sql_model_name, model_provider="deepseek", api_key=api_key, temperature=0,
    extra_body={"thinking": {"type": "enabled"}},
)
backup_llm = init_chat_model(
    model=app_config.fault_tolerance.llm_fallback.backup_model_name,
    model_provider="deepseek",
    api_key=api_key,
    temperature=0,
)

if langfuse_handler is not None:
    llm.callbacks = [langfuse_handler]


async def _invoke_with_retry(target_llm, prompt, input_vars, timeout, log_prefix=""):
    config = RetryConfig(max_retries=1, base_delay=2.0, is_read_only=True)
    last_error = None
    for attempt in range(config.max_retries + 1):
        try:
            result = await asyncio.wait_for(
                target_llm.ainvoke(prompt.format(**input_vars)),
                timeout=timeout,
            )
            return result.content if hasattr(result, "content") else str(result)
        except Exception as e:
            last_error = e
            logger.warning(f"[llm{log_prefix}] 调用失败 (attempt {attempt + 1}): {e}")
            if attempt < config.max_retries:
                await asyncio.sleep(config.base_delay * (config.backoff_factor ** attempt))
    raise last_error


async def invoke_llm_with_fallback(prompt, input_vars, timeout=30):
    try:
        return await _invoke_with_retry(llm, prompt, input_vars, timeout)
    except Exception as e:
        logger.warning(f"[llm] 主模型失败，切换备用模型: {e}")
        try:
            return await _invoke_with_retry(backup_llm, prompt, input_vars, timeout, log_prefix="/backup")
        except Exception as e2:
            logger.error(f"[llm] 备用模型也失败: {e2}")
            raise


async def invoke_sql_llm_with_fallback(prompt, input_vars, timeout=30):
    try:
        return await _invoke_with_retry(sql_llm, prompt, input_vars, timeout, log_prefix="/sql")
    except Exception as e:
        logger.warning(f"[llm/sql] reasoner失败，切换备用模型: {e}")
        try:
            return await _invoke_with_retry(backup_llm, prompt, input_vars, timeout, log_prefix="/backup")
        except Exception as e2:
            logger.error(f"[llm/sql] 备用模型也失败: {e2}")
            raise


if __name__ == "__main__":
    async def test():
        print(await llm.ainvoke("中国的首都是哪里？"))

    print(asyncio.run(test()))
