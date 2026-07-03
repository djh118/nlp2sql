import json

import httpx
from datetime import datetime, timezone
from dataclasses import dataclass

from app.config.app_config import app_config
from app.core.logging import logger


@dataclass
class FeishuTokens:
    access_token: str
    expire_at: float


class FeishuClient:
    BASE = "https://open.feishu.cn/open-apis"

    def __init__(self):
        self.app_id = app_config.feishu.app_id
        self.app_secret = app_config.feishu.app_secret
        self._tokens: FeishuTokens | None = None
        self._http = httpx.AsyncClient(timeout=10)

    async def _ensure_token(self):
        if self._tokens and datetime.now(timezone.utc).timestamp() < self._tokens.expire_at - 60:
            return self._tokens.access_token
        resp = await self._http.post(
            f"{self.BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        data = resp.json()
        self._tokens = FeishuTokens(
            access_token=data["tenant_access_token"],
            expire_at=datetime.now(timezone.utc).timestamp() + data["expire"],
        )
        logger.info(f"飞书 token 刷新成功，有效期 {data['expire']}s")
        return self._tokens.access_token

    async def reply_card(self, message_id: str, card_json: str):
        token = await self._ensure_token()
        resp = await self._http.post(
            f"{self.BASE}/im/v1/messages/{message_id}/reply",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": card_json,
                "msg_type": "interactive",
            },
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.error(f"飞书卡片回复失败: {data}")
        return data

    async def reply_text(self, message_id: str, text: str):
        token = await self._ensure_token()
        resp = await self._http.post(
            f"{self.BASE}/im/v1/messages/{message_id}/reply",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": json.dumps({"text": text}),
                "msg_type": "text",
            },
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.error(f"飞书回复失败: {data}")
        return data

    async def close(self):
        await self._http.aclose()


feishu_client = FeishuClient()
