from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger


class BaiduAiImagingPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.llm_tool(name="send_image")
    async def send_image(self, event: AstrMessageEvent, image_urls: list[str]):
        '''把 AI 生成的图片发送给当前用户。

        当 Skill 触发后从 Baiduai.js 拿到图片 URL 数组时，调用本工具把图片直接发给用户，避免再让模型输出 Markdown 链接或 base64。

        Args:
            image_urls(array[string]): 图片 URL 列表，通常来自 Baiduai.js 输出的 all_urls 字段，每次只会发送列表中的第一张有效图片
        '''
        if not image_urls:
            yield event.plain_result("未收到图片 URL，请稍后重试。")
            return

        target_url = None
        for url in image_urls:
            if url and isinstance(url, str):
                target_url = url
                break

        if not target_url:
            yield event.plain_result("图片发送失败，请稍后重试。")
            return

        try:
            yield event.image_result(target_url)
            yield event.plain_result("图片已发送")
        except Exception as e:
            logger.error(f"send_image failed for {target_url}: {e}")
            yield event.plain_result("图片发送失败，请稍后重试。")


def create_plugin(context: Context):
    return BaiduAiImagingPlugin(context)
