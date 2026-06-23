import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config.app_config import DBConfig, app_config


class MySQLClientManager:
    def __init__(self, db_config: DBConfig):
        self.engine = None
        self.session_factory = None
        self.db_config = db_config

    def _get_url(self):
        return f"mysql+asyncmy://{self.db_config.user}:{self.db_config.password}@{self.db_config.host}:{self.db_config.port}/{self.db_config.database}?charset=utf8mb4"

    def init(self):
        self.engine = create_async_engine(
            self._get_url(),
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False
        )

    async def close(self):
        await self.engine.dispose()


# 实例化全局对象
dw_client_manager = MySQLClientManager(app_config.db_dw)
meta_client_manager = MySQLClientManager(app_config.db_meta)

if __name__ == '__main__':
    async def test():
        dw_client_manager.init()
        async with AsyncSession(dw_client_manager.engine) as session:
            result = await session.execute(text("show tables"))
            print(result.mappings().fetchall())


    asyncio.run(test())
