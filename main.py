import os
import asyncio
import aiohttp
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star
from astrbot.api import logger


class BaiduAiImagingPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.server_process = None
        self.server_port = 3000
        self.server_host = "localhost"
        self.server_url = f"http://{self.server_host}:{self.server_port}"
        self.is_server_running = False

        asyncio.create_task(self.start_server())

    async def start_server(self):
        if self.is_server_running:
            return

        project_path = os.path.join(os.path.dirname(__file__), "Free_BaiduAi_Imaging")

        env = os.environ.copy()
        env["PORT"] = str(self.server_port)

        if os.name == 'nt':
            self.server_process = await asyncio.create_subprocess_shell(
                "npm start",
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
        else:
            self.server_process = await asyncio.create_subprocess_shell(
                "npm start",
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

        await asyncio.sleep(5)
        self.is_server_running = True
        logger.info(f"百度AI生图服务已启动: {self.server_url}")

    async def check_server(self):
        if not self.is_server_running:
            await self.start_server()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/health") as resp:
                    if resp.status == 200:
                        return True
        except Exception as e:
            logger.warning(f"服务检查失败，尝试重新启动: {str(e)}")
            self.is_server_running = False
            await self.start_server()
            return True
        return False

    @filter.llm_tool(name="generate_image")
    async def generate_image(self, event: AstrMessageEvent, prompt: str, send_to_user: bool = False, n: int = 1) -> MessageEventResult:
        """使用百度AI生成图片。

        Args:
            prompt(string): 图片描述，支持中文
            send_to_user(boolean): 是否发送给用户，true表示发送，false表示仅返回URL
            n(number): 生成图片数量(1-4)，默认为1
        """
        await self.check_server()

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "prompt": prompt,
                    "n": min(max(n, 1), 4),
                    "size": "1024x1024",
                    "response_format": "url"
                }

                async with session.post(
                    f"{self.server_url}/v1/images/generations",
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        error_data = await resp.json()
                        error_msg = error_data.get("error", {}).get("message", "生成图片失败")
                        yield event.plain_result(f"图片生成失败: {error_msg}")
                        return

                    data = await resp.json()
                    image_urls = [item["url"] for item in data.get("data", [])]

                    if not image_urls:
                        yield event.plain_result("未能获取到图片URL")
                        return

                    if send_to_user:
                        for url in image_urls:
                            yield event.image_result(url)
                        yield event.plain_result("图片已发送给用户")
                    else:
                        result = "图片生成成功！\n\n图片URL:\n" + "\n".join(image_urls)
                        yield event.plain_result(result)

        except Exception as e:
            logger.error(f"图片生成错误: {str(e)}")
            yield event.plain_result(f"图片生成过程中发生错误: {str(e)}")

    async def terminate(self):
        if self.server_process:
            self.server_process.terminate()
            await self.server_process.wait()
            self.is_server_running = False
            logger.info("百度AI生图服务已停止")

    @filter.command("baidu-image-start")
    async def start_server_cmd(self, event: AstrMessageEvent) -> MessageEventResult:
        """启动百度AI生图服务"""
        await self.start_server()
        yield event.plain_result(f"百度AI生图服务已启动: {self.server_url}")

    @filter.command("baidu-image-status")
    async def status(self, event: AstrMessageEvent) -> MessageEventResult:
        """检查百度AI生图服务状态"""
        is_running = await self.check_server()
        if is_running:
            yield event.plain_result(f"百度AI生图服务运行正常: {self.server_url}")
        else:
            yield event.plain_result("百度AI生图服务未运行")

    @filter.command("baidu-image-restart")
    async def restart_server(self, event: AstrMessageEvent) -> MessageEventResult:
        """重启百度AI生图服务"""
        if self.server_process:
            self.server_process.terminate()
            await self.server_process.wait()
            self.is_server_running = False

        await self.start_server()
        yield event.plain_result(f"百度AI生图服务已重启: {self.server_url}")


def create_plugin(context: Context):
    return BaiduAiImagingPlugin(context)