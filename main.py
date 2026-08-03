from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext


@dataclass
class SendImageTool(FunctionTool[AstrAgentContext]):
    '''把 AI 生成的图片发送给当前用户。

    当 Skill 触发后从 Baiduai.js 拿到图片 URL 数组时，调用本工具把图片直接发给用户，避免再让模型输出 Markdown 链接或 base64。

    Args:
        image_urls(array[string]): 图片 URL 列表，通常来自 Baiduai.js 输出的 all_urls 字段，每次只会发送列表中的第一张有效图片
    '''
    name: str = "send_image"
    description: str = "把 AI 生成的图片发送给当前用户。每次只发送列表中的第一张有效图片。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "image_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "图片 URL 列表，来自 Baiduai.js 输出的 all_urls 字段，每次只会发送列表中的第一张有效图片",
                },
            },
            "required": ["image_urls"],
        },
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        image_urls = kwargs.get("image_urls") or []
        event = context.context.event

        if not image_urls:
            await event.send(event.plain_result("未收到图片 URL，请稍后重试。"))
            return "图片发送失败：未收到 URL"

        target_url = None
        for url in image_urls:
            if url and isinstance(url, str):
                target_url = url
                break

        if not target_url:
            await event.send(event.plain_result("图片发送失败，请稍后重试。"))
            return "图片发送失败：URL 无效"

        try:
            await event.send(event.image_result(target_url))
            return "图片已发送"
        except Exception as e:
            logger.error(f"send_image failed for {target_url}: {e}")
            await event.send(event.plain_result("图片发送失败，请稍后重试。"))
            return "图片发送失败：发生异常"


class BaiduAiImagingPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(SendImageTool())


def create_plugin(context: Context):
    return BaiduAiImagingPlugin(context)
