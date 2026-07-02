import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.logging import logger
from app.prompt.prompt_loader import load_prompt

_GREETING_PATTERNS = re.compile(
    r'^(你好|您好|hi|hello|嗨|早上好|下午好|晚上好|晚安|'
    r'谢谢|感谢|多谢|再见|拜拜|拜|88|'
    r'在吗|还在吗|hello|hey|hi\b)',
    re.IGNORECASE
)

_ADMIN_PATTERNS = re.compile(
    r'^(帮助|help|功能|你能做什么|你是谁|'
    r'你可以干什么|你有什么功能|怎么用|使用方法)',
    re.IGNORECASE
)

_DDL_DML_PATTERNS = re.compile(
    r'(删除|插入|更新|创建|修改|清空|'
    r'drop|truncate|insert|update|delete|alter|create|'
    r'删掉|移除|新增|新建)',
    re.IGNORECASE
)


def _rule_classify(query: str) -> str | None:
    if _GREETING_PATTERNS.match(query.strip()):
        return "greeting"
    if _ADMIN_PATTERNS.match(query.strip()):
        return "admin"
    if _DDL_DML_PATTERNS.search(query):
        return "ddl_dml"
    return None


_DIRECT_RESPONSES = {
    "greeting": "你好！我是一个数据查询助手，可以帮你查询数据库中的数据并进行数据分析。请问有什么数据问题需要解答吗？",
    "admin": "我是一个数据查询助手，支持通过自然语言查询数据库中的数据。你可以问我例如「上个月的销售额是多少」「各品类销量排名」之类的问题。",
    "ddl_dml": "抱歉，我只能执行数据查询操作（SELECT），不支持数据修改、删除或结构变更操作。",
    "out_of_domain": "抱歉，我只能处理数据查询相关问题。请提供具体的数据库查询需求，例如「查询上个月的销售数据」或「各品类销售额排名」。",
}


async def classify_intent(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "意图分类"})

    query = state["query"]

    rule_result = _rule_classify(query)
    if rule_result is not None:
        logger.info(f"规则分类结果: {rule_result}, query: {query}")
        return {
            "intent": rule_result,
            "direct_response": _DIRECT_RESPONSES[rule_result],
        }

    try:
        prompt = PromptTemplate(
            template=load_prompt("classify_intent"),
            input_variables=["query"],
        )
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        result = (await chain.ainvoke({"query": query})).strip().lower()
        logger.info(f"LLM分类结果: {result}, query: {query}")

        if result == "data_query":
            return {"intent": "data_query"}
        else:
            return {
                "intent": "out_of_domain",
                "direct_response": _DIRECT_RESPONSES["out_of_domain"],
            }
    except Exception as e:
        logger.error(f"LLM分类失败，默认视为data_query: {e}")
        return {"intent": "data_query"}
