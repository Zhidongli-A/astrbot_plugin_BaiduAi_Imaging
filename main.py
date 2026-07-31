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
            image_urls(array[string]): 图片 URL 列表，通常来自 Baiduai.js 输出的 all_urls 字段，可传 1~4 个
        '''
        if not image_urls:
            yield event.plain_result("未收到图片 URL，请稍后重试。")
            return

        sent = 0
        for url in image_urls:
            if not url or not isinstance(url, str):
                continue
            try:
                yield event.image_result(url)
                sent += 1
            except Exception as e:
                logger.error(f"send_image failed for {url}: {e}")

        if sent == 0:
            yield event.plain_result("图片发送失败，请稍后重试。")


def create_plugin(context: Context):
    return BaiduAiImagingPlugin(context)
