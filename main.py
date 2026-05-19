import os
import asyncio
import json
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger

PLUGIN_NAME = "astrbot_plugin_BaiduAi_Imaging"


class BaiduAiImagingPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.js_path = os.path.join(os.path.dirname(__file__), "Baiduai.js")

    async def _generate_image(self, prompt: str):
        """调用 Node.js 执行 Baiduai.js"""
        process = await asyncio.create_subprocess_exec(
            'node', self.js_path, prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.path.dirname(__file__)
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error = stderr.decode('utf-8', errors='replace').strip()
            raise Exception(f"生成失败: {error}")

        result = json.loads(stdout.decode('utf-8'))

        if 'error' in result:
            raise Exception(result['error'])

        return result

    @filter.llm_tool(name="generate_image")
    async def generate_image(self, event: AstrMessageEvent, prompt: str, send_to_user: bool = False, n: int = 1) -> str:
        """使用百度AI生成图片。

        Args:
            prompt(string): 图片描述，支持中文
            send_to_user(boolean): 是否发送给用户，true表示发送给用户，false表示仅返回URL给Agent
            n(number): 生成图片数量(1-4)，默认为1
        """
        n = min(max(n, 1), 4)

        try:
            result = await self._generate_image(prompt)
            image_urls = result['all_urls'][:n]

            if not image_urls:
                return "Error: Failed to get image URLs"

            if send_to_user:
                from astrbot.api.event import MessageChain
                message_chain = MessageChain()
                for url in image_urls:
                    message_chain = message_chain.image(url)
                await self.context.send_message(event.unified_msg_origin, message_chain)
                return f"Images have been successfully sent to the user. Generated {len(image_urls)} image(s) for prompt: '{prompt}'"
            else:
                urls_text = "\n".join(image_urls)
                return f"Image generation successful. Here are the URLs:\n{urls_text}\n\nPrompt: '{prompt}'"

        except Exception as e:
            error_msg = f"Error: Image generation failed - {str(e)}"
            logger.error(error_msg)
            return error_msg


def create_plugin(context: Context):
    return BaiduAiImagingPlugin(context)
