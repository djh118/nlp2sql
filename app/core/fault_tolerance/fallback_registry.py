from app.core.logging import logger
from app.core.context import request_id_ctx_var
from app.core.fault_tolerance.langfuse_reporter import report_fault_event
from app.repositories.mysql.meta_mysql_repository import MetaMySQLRepository


class FallbackRegistry:

    @staticmethod
    async def vector_retrieval_fallback(query: str, meta_mysql: MetaMySQLRepository) -> list:
        logger.info("[fallback] 向量检索降级: 使用 MySQL 关键词匹配")
        report_fault_event(
            category="vector_retrieval",
            level="degrade",
            tag="vector_retrieval/degrade/mysql_fallback",
            message="向量检索降级: 使用 MySQL 关键词匹配",
            request_id=request_id_ctx_var.get(""),
            metadata={"fallback_type": "mysql_keyword"},
        )
        try:
            from sqlalchemy import select
            from app.models.mysql.table_info_mysql import TableInfoMySQL
            from app.models.mysql.column_info_mysql import ColumnInfoMySQL
            tables_result = await meta_mysql.session.execute(
                select(TableInfoMySQL)
            )
            tables = tables_result.scalars().all()
            result = []
            for table in tables:
                columns_result = await meta_mysql.session.execute(
                    select(ColumnInfoMySQL).where(ColumnInfoMySQL.table_id == table.id)
                )
                columns = columns_result.scalars().all()
                result.append({
                    "name": table.name,
                    "role": table.role,
                    "description": table.description,
                    "columns": [
                        {
                            "id": c.id,
                            "name": c.name,
                            "type": c.type,
                            "role": c.role,
                            "description": c.description,
                            "alias": c.alias,
                            "examples": c.examples,
                            "table_id": c.table_id,
                        }
                        for c in columns
                    ],
                })
            return result
        except Exception as e:
            logger.error(f"[fallback] MySQL 关键词降级也失败: {e}")
            return []

    @staticmethod
    def empty_recall_message() -> str:
        return "暂未找到与您查询匹配的业务数据表，请尝试更精确的关键词"

    @staticmethod
    def llm_fallback_message() -> str:
        return "SQL 生成服务暂时不可用，请稍后重试"

    @staticmethod
    def db_unavailable_message() -> str:
        return "数据仓库暂时不可用，请稍后重试"
