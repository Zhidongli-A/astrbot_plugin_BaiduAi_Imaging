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

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=370
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise Exception('Node.js subprocess timed out (over 370 seconds)')

        stdout_str = stdout.decode('utf-8', errors='replace').strip()
        stderr_str = stderr.decode('utf-8', errors='replace').strip()

        # 优先解析 stdout ── 成功时此处为纯净 JSON
        if stdout_str:
            try:
                result = json.loads(stdout_str)
                if 'error' in result:
                    raise Exception(result['error'])
                return result
            except json.JSONDecodeError:
                pass

        # 进程退出码非 0 时，从 stderr 提取错误
        if process.returncode != 0 and stderr_str:
            for line in reversed(stderr_str.split('\n')):
                line = line.strip()
                if line.startswith('{'):
                    try:
                        err_result = json.loads(line)
                        if 'error' in err_result:
                            raise Exception(err_result['error'])
                    except json.JSONDecodeError:
                        pass

        # 最终错误报告
        error_detail = stderr_str or stdout_str or 'unknown error'
        raise Exception(f"Image generation failed: {error_detail}")

    @filter.command("generate_image")
    async def generate_image(self, event: AstrMessageEvent):
        """使用百度AI生成图片。用法: generate_image <描述>"""
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法: generate_image <图片描述>")
            return
        prompt = args[1]

        yield event.plain_result(f"正在生成: {prompt}")

        try:
            result = await self._generate_image(prompt)
            image_urls = result['all_urls']

            if not image_urls:
                yield event.plain_result("生成失败: 未收到图片 URL")
                return

            for url in image_urls:
                yield event.image_result(url)

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            yield event.plain_result(f"生成失败: {str(e)}")


def create_plugin(context: Context):
    return BaiduAiImagingPlugin(context)
