import os
import asyncio
import json
import subprocess
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger

PLUGIN_NAME = "astrbot_plugin_BaiduAi_Imaging"


class BaiduImageGenerator:
    """百度AI图片生成器 - 调用 Node.js 版本"""

    def __init__(self):
        self.js_path = os.path.join(os.path.dirname(__file__), "Baiduai.js")

    async def generate_image(self, prompt: str):
        """调用 Node.js 生成图片"""
        # 创建临时 JS 脚本来执行生成
        temp_js = f"""
const BaiduImageGenerator = require('{self.js_path.replace('\\', '\\\\')}');

async function main() {{
    const generator = new BaiduImageGenerator();
    try {{
        const result = await generator.generateImage('{prompt.replace("'", "\\'")}');
        console.log(JSON.stringify(result));
        await generator.close();
    }} catch (error) {{
        console.error(JSON.stringify({{ error: error.message }}));
        process.exit(1);
    }}
}}

main();
"""
        # 写入临时文件
        temp_path = os.path.join(os.path.dirname(__file__), "_temp_generate.js")
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(temp_js)

        try:
            # 执行 Node.js 脚本
            process = await asyncio.create_subprocess_exec(
                'node', temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(__file__)
            )

            stdout, stderr = await process.communicate()

            # 清理临时文件
            try:
                os.remove(temp_path)
            except:
                pass

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace') if stderr else "未知错误"
                raise Exception(f"Node.js 执行失败: {error_msg}")

            # 解析结果
            output = stdout.decode('utf-8', errors='replace').strip()
            # 找到 JSON 输出（可能有其他日志）
            lines = output.split('\n')
            result_line = None
            for line in reversed(lines):
                line = line.strip()
                if line.startswith('{'):
                    result_line = line
                    break

            if not result_line:
                raise Exception("无法解析生成结果")

            result = json.loads(result_line)

            if 'error' in result:
                raise Exception(result['error'])

            return result

        except asyncio.TimeoutError:
            raise Exception("图片生成超时")
        except Exception as e:
            raise e


class BaiduAiImagingPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 创建生成器实例池
        self.generator_pool = []
        self.max_pool_size = 3

    async def _get_generator(self):
        """从池中获取一个可用的生成器"""
        # 查找空闲的生成器
        for item in self.generator_pool:
            if not item['in_use']:
                item['in_use'] = True
                return item['generator']

        # 如果池未满，创建新实例
        if len(self.generator_pool) < self.max_pool_size:
            generator = BaiduImageGenerator()
            self.generator_pool.append({'generator': generator, 'in_use': True})
            return generator

        # 等待可用实例
        while True:
            for item in self.generator_pool:
                if not item['in_use']:
                    item['in_use'] = True
                    return item['generator']
            await asyncio.sleep(0.5)

    def _release_generator(self, generator):
        """释放生成器回池中"""
        for item in self.generator_pool:
            if item['generator'] == generator:
                item['in_use'] = False
                break

    @filter.llm_tool(name="generate_image")
    async def generate_image(self, event: AstrMessageEvent, prompt: str, send_to_user: bool = False, n: int = 1) -> str:
        """使用百度AI生成图片。When send_to_user is true, send images to user first, then return success message to agent. When false, return URLs to agent directly. All errors should be returned to agent instead of raising.

        Args:
            prompt(string): 图片描述，支持中文
            send_to_user(boolean): 是否发送给用户，true表示发送给用户，false表示仅返回URL给Agent
            n(number): 生成图片数量(1-4)，默认为1
        """
        n = min(max(n, 1), 4)

        try:
            generator = await self._get_generator()

            try:
                result = await generator.generate_image(prompt)
                image_urls = result['all_urls'][:n]

                if not image_urls:
                    return "Error: Failed to get image URLs"

                if send_to_user:
                    # 发送图片给用户（主动消息）
                    from astrbot.api.event import MessageChain
                    message_chain = MessageChain()
                    for url in image_urls:
                        message_chain = message_chain.image(url)
                    await self.context.send_message(event.unified_msg_origin, message_chain)
                    # 返回给 Agent，告知已发送
                    return f"Images have been successfully sent to the user. Generated {len(image_urls)} image(s) for prompt: '{prompt}'"
                else:
                    # 返回 URL 给 Agent
                    urls_text = "\n".join(image_urls)
                    return f"Image generation successful. Here are the URLs:\n{urls_text}\n\nPrompt: '{prompt}'"

            finally:
                self._release_generator(generator)

        except asyncio.TimeoutError:
            error_msg = "Error: Image generation timeout"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error: Image generation failed - {str(e)}"
            logger.error(error_msg)
            return error_msg

    async def terminate(self):
        """插件终止时清理"""
        self.generator_pool.clear()


def create_plugin(context: Context):
    return BaiduAiImagingPlugin(context)
