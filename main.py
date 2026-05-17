import os
import asyncio
import aiohttp
import json
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star
from astrbot.api import logger
from quart import jsonify, Response

PLUGIN_NAME = "astrbot_plugin_BaiduAi_Imaging"


class BaiduAiImagingPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.server_process = None
        self.server_port = 1145
        self.server_host = "localhost"
        self.server_url = f"http://{self.server_host}:{self.server_port}"
        self.is_server_running = False
        
        # 日志收集
        self.log_buffer = []
        self.max_log_buffer = 500
        self.log_subscribers = []
        
        # 注册 Web API
        self._register_web_apis()

        asyncio.create_task(self.start_server())

    def _register_web_apis(self):
        """注册插件页面所需的 Web API"""
        self.context.register_web_api(
            f"/{PLUGIN_NAME}/logs/stream",
            self.logs_stream,
            ["GET"],
            "日志实时流 (SSE)",
        )

    async def logs_stream(self):
        """SSE 日志流接口"""
        async def event_stream():
            queue = asyncio.Queue()
            self.log_subscribers.append(queue)
            
            try:
                # 发送历史日志
                for log in self.log_buffer:
                    yield f"data: {json.dumps(log, ensure_ascii=False)}\n\n"
                
                # 实时推送新日志
                while True:
                    try:
                        log = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f"data: {json.dumps(log, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        # 发送心跳保持连接
                        yield ":heartbeat\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                if queue in self.log_subscribers:
                    self.log_subscribers.remove(queue)
        
        return Response(
            event_stream(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            }
        )

    def _add_log(self, message: str, level: str = "INFO"):
        """添加日志到缓冲区并推送给订阅者"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }
        
        self.log_buffer.append(log_entry)
        if len(self.log_buffer) > self.max_log_buffer:
            self.log_buffer.pop(0)
        
        # 推送给所有订阅者
        for queue in self.log_subscribers:
            try:
                queue.put_nowait(log_entry)
            except asyncio.QueueFull:
                pass

    async def start_server(self):
        if self.is_server_running:
            return

        project_path = os.path.join(os.path.dirname(__file__), "Free_BaiduAi_Imaging")

        env = os.environ.copy()
        env["PORT"] = str(self.server_port)

        self._add_log("正在启动 Node.js 服务...", "INFO")

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

        # 启动日志读取任务
        asyncio.create_task(self._read_stdout())
        asyncio.create_task(self._read_stderr())

        await asyncio.sleep(10)
        self.is_server_running = True
        self._add_log(f"百度AI生图服务已启动: {self.server_url}", "INFO")
        logger.info(f"百度AI生图服务已启动: {self.server_url}")

    async def _read_stdout(self):
        """读取 Node.js 标准输出"""
        if not self.server_process:
            return
        while True:
            try:
                line = await self.server_process.stdout.readline()
                if not line:
                    break
                message = line.decode('utf-8', errors='replace').strip()
                if message:
                    self._add_log(message, "INFO")
            except Exception as e:
                self._add_log(f"读取 stdout 错误: {e}", "ERROR")
                break

    async def _read_stderr(self):
        """读取 Node.js 标准错误"""
        if not self.server_process:
            return
        while True:
            try:
                line = await self.server_process.stderr.readline()
                if not line:
                    break
                message = line.decode('utf-8', errors='replace').strip()
                if message:
                    self._add_log(message, "ERROR")
            except Exception as e:
                self._add_log(f"读取 stderr 错误: {e}", "ERROR")
                break

    async def check_server(self):
        if not self.is_server_running:
            self._add_log("服务未运行，正在启动...", "WARN")
            await self.start_server()

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(f"{self.server_url}/health") as resp:
                    if resp.status == 200:
                        return True
        except Exception as e:
            self._add_log(f"服务检查失败: {str(e)}", "WARN")
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
        
        self._add_log(f"收到图片生成请求: {prompt[:50]}...", "INFO")

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
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
                        try:
                            error_data = await resp.json()
                            error_msg = error_data.get("error", {}).get("message", "生成图片失败")
                        except Exception:
                            text_content = await resp.text()
                            error_msg = f"HTTP {resp.status}: {text_content[:100]}"
                        self._add_log(f"图片生成失败: {error_msg}", "ERROR")
                        yield event.plain_result(f"图片生成失败: {error_msg}")
                        return

                    try:
                        data = await resp.json()
                    except Exception as json_error:
                        text_content = await resp.text()
                        logger.error(f"JSON解析失败: {text_content}")
                        self._add_log(f"JSON解析失败", "ERROR")
                        yield event.plain_result(f"图片生成失败: 服务器返回格式错误")
                        return

                    image_urls = [item["url"] for item in data.get("data", [])]

                    if not image_urls:
                        self._add_log("未能获取到图片URL", "WARN")
                        yield event.plain_result("未能获取到图片URL")
                        return

                    self._add_log(f"图片生成成功，返回 {len(image_urls)} 张图片", "INFO")
                    if send_to_user:
                        for url in image_urls:
                            yield event.image_result(url)
                        yield event.plain_result("图片已发送给用户")
                    else:
                        result = "图片生成成功！\n\n图片URL:\n" + "\n".join(image_urls)
                        yield event.plain_result(result)

        except aiohttp.ClientError as e:
            logger.error(f"网络请求错误: {str(e)}")
            self._add_log(f"网络请求错误: {str(e)}", "ERROR")
            yield event.plain_result(f"图片生成失败: 网络连接错误，请检查服务是否正常启动")
        except asyncio.TimeoutError:
            logger.error("请求超时")
            self._add_log("请求超时", "ERROR")
            yield event.plain_result("图片生成失败: 请求超时")
        except Exception as e:
            logger.error(f"图片生成错误: {str(e)}")
            self._add_log(f"图片生成错误: {str(e)}", "ERROR")
            yield event.plain_result(f"图片生成过程中发生错误: {str(e)}")

    async def terminate(self):
        self._add_log("正在停止服务...", "INFO")
        if self.server_process:
            self.server_process.terminate()
            await self.server_process.wait()
            self.is_server_running = False
            self._add_log("百度AI生图服务已停止", "INFO")
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
        self._add_log("正在重启服务...", "INFO")
        if self.server_process:
            self.server_process.terminate()
            await self.server_process.wait()
            self.is_server_running = False

        await self.start_server()
        yield event.plain_result(f"百度AI生图服务已重启: {self.server_url}")


def create_plugin(context: Context):
    return BaiduAiImagingPlugin(context)