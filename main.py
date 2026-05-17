import asyncio
import time
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger

PLUGIN_NAME = "astrbot_plugin_BaiduAi_Imaging"


class BaiduImageGenerator:
    """百度AI图片生成器 - 使用 Playwright 模拟浏览器操作"""

    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None

    async def init(self):
        """初始化浏览器"""
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )

        self.page = await self.browser.new_page(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        self.page.set_default_timeout(60000)
        self.page.set_default_navigation_timeout(120000)

    async def generate_image(self, prompt: str):
        """生成图片"""
        if not self.page:
            await self.init()

        try:
            # 访问百度AI页面
            await self.page.goto(
                'https://chat.baidu.com/?enter_type=chat_url',
                wait_until='domcontentloaded',
                timeout=120000
            )
            await asyncio.sleep(5)

            # 点击AI生图按钮 - 使用 text 定位器
            ai_image_button = self.page.locator('div').filter(has_text='AI生图').first
            await ai_image_button.wait_for(state='visible', timeout=15000)
            await ai_image_button.click()
            await asyncio.sleep(3)

            # 输入提示词
            input_box = self.page.locator('div[contenteditable="true"]').first
            await input_box.wait_for(state='visible', timeout=20000)
            await input_box.click()
            await asyncio.sleep(0.5)
            await self.page.keyboard.press('Control+a')
            await asyncio.sleep(0.2)
            await self.page.keyboard.press('Delete')
            await asyncio.sleep(0.2)
            await input_box.fill(prompt)
            await asyncio.sleep(1)

            # 点击发送按钮
            send_button = self.page.locator('#ci-submit-button-ai')
            await send_button.wait_for(state='visible', timeout=15000)
            await send_button.click()
            await asyncio.sleep(5)

            # 等待生成完成
            await self._wait_for_generation_complete()
            image_urls = await self._get_image_urls()

            return {
                'success': True,
                'prompt': prompt,
                'all_urls': image_urls,
                'selected_url': image_urls[0] if image_urls else None,
                'created_at': time.time()
            }

        except Exception as e:
            raise e

    async def _wait_for_generation_complete(self):
        """等待图片生成完成"""
        max_wait_time = 300000  # 5分钟
        check_interval = 3      # 3秒检查一次
        start_time = time.time()
        images_detected = False

        while (time.time() - start_time) * 1000 < max_wait_time:
            try:
                # 检查是否还在加载中
                loading_elements = await self.page.locator('text=/收集中|生成中|[0-9]+%/').all()
                is_loading = False

                for el in loading_elements:
                    try:
                        if await el.is_visible():
                            is_loading = True
                            break
                    except:
                        pass

                # 检查图片是否已经生成
                images = await self.page.locator('._image-visible_c32gq_184').all()

                if len(images) >= 4 and not images_detected:
                    images_detected = True

                if images_detected and not is_loading:
                    await asyncio.sleep(5)
                    return

            except Exception:
                pass

            await asyncio.sleep(check_interval)

        raise Exception('等待图片生成超时（超过5分钟）')

    async def _get_image_urls(self):
        """获取生成的图片URL"""
        images = await self.page.locator('._image-visible_c32gq_184').all()

        urls = []
        for img in images:
            src = await img.get_attribute('src')
            if src and src not in urls:
                urls.append(src)

        if not urls:
            raise Exception('未能获取到生成的图片URL')

        return urls[:4]

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None


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
            await generator.init()
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
        """插件终止时关闭所有浏览器实例"""
        for item in self.generator_pool:
            try:
                await item['generator'].close()
            except:
                pass
        self.generator_pool.clear()


def create_plugin(context: Context):
    return BaiduAiImagingPlugin(context)
