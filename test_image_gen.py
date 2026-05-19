"""
独立测试脚本 - 不依赖任何框架
直接运行: python test_image_gen.py
"""
import asyncio
import time
import re
from playwright.async_api import async_playwright


class BaiduImageGenerator:
    """百度AI图片生成器 - 完全独立版本（与原版 JS 完全一致）"""

    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None

    async def init(self):
        """初始化浏览器"""
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
        print("[INFO] 浏览器初始化完成")

    async def generate_image(self, prompt: str):
        """生成图片 - 与原版 JS 完全一致"""
        if not self.page:
            await self.init()

        print(f"[INFO] 开始生成图片: {prompt}")

        try:
            # 访问百度AI页面 - 与原版一致
            print("[INFO] 访问百度AI页面...")
            await self.page.goto(
                'https://chat.baidu.com/?enter_type=chat_url',
                wait_until='domcontentloaded',
                timeout=120000
            )
            await self.page.wait_for_timeout(5000)  # 原版 5 秒

            # 点击AI生图按钮 - 与原版一致
            print("[INFO] 查找AI生图按钮...")
            ai_image_button = self.page.locator('div').filter(has_text=re.compile(r'^AI生图$')).first
            await ai_image_button.wait_for(state='visible', timeout=15000)
            print("[INFO] 点击AI生图按钮...")
            await ai_image_button.click()
            await self.page.wait_for_timeout(3000)  # 原版 3 秒

            # 输入提示词 - 与原版完全一致（使用 Control+a + Delete 清空）
            print(f"[INFO] 输入提示词: {prompt}")
            input_box = self.page.locator('div[contenteditable="true"]').first
            await input_box.wait_for(state='visible', timeout=20000)
            await input_box.click()
            await self.page.wait_for_timeout(500)   # 原版 500ms
            await self.page.keyboard.press('Control+a')
            await self.page.wait_for_timeout(200)   # 原版 200ms
            await self.page.keyboard.press('Delete')
            await self.page.wait_for_timeout(200)   # 原版 200ms
            await input_box.fill(prompt)
            await self.page.wait_for_timeout(1000)  # 原版 1 秒

            # 点击发送按钮 - 与原版一致
            print("[INFO] 点击发送按钮...")
            send_button = self.page.locator('#ci-submit-button-ai')
            await send_button.wait_for(state='visible', timeout=15000)
            await send_button.click()
            await self.page.wait_for_timeout(5000)  # 原版 5 秒

            # 点击发送后截图
            screenshot_path = "after_send.png"
            await self.page.screenshot(path=screenshot_path, full_page=True)
            print(f"[INFO] 已截图保存到: {screenshot_path}")

            # 等待生成完成
            print("[INFO] 等待图片生成...")
            await self._wait_for_generation_complete()
            image_urls = await self._get_image_urls()

            print(f"[SUCCESS] 图片生成成功！获取到 {len(image_urls)} 张图片")

            return {
                'success': True,
                'prompt': prompt,
                'all_urls': image_urls,
                'selected_url': image_urls[0] if image_urls else None,
                'created_at': time.time() * 1000
            }

        except Exception as e:
            print(f"[ERROR] 图片生成失败: {str(e)}")
            raise e

    async def _wait_for_generation_complete(self):
        """等待图片生成完成 - 与原版 JS 完全一致"""
        max_wait_time = 300000  # 5分钟
        check_interval = 3000   # 3秒（原版）
        start_time = time.time() * 1000
        last_percentage = ''
        last_log_time = 0
        images_detected = False

        while (time.time() * 1000 - start_time) < max_wait_time:
            try:
                # 检查是否还在加载中 - 与原版一致
                loading_elements = await self.page.locator('text=/收集中|生成中|[0-9]+%/').all()
                is_loading = False

                for el in loading_elements:
                    try:
                        if await el.is_visible():
                            text = await el.text_content()
                            if text and text != last_percentage:
                                last_percentage = text
                                print(f"[PROGRESS] {text}")
                            is_loading = True
                            break
                    except:
                        pass

                # 检查图片是否已经生成
                images = await self.page.locator('._image-visible_c32gq_184').all()

                if len(images) >= 4 and not images_detected:
                    images_detected = True
                    print(f"[INFO] 检测到 {len(images)} 张图片已生成")

                if images_detected and not is_loading:
                    print("[INFO] 图片生成完成！")
                    await self.page.wait_for_timeout(5000)  # 原版 5 秒
                    return

                if (time.time() * 1000 - last_log_time) > 30000:
                    last_log_time = time.time() * 1000

            except Exception:
                pass

            await self.page.wait_for_timeout(check_interval)

        raise Exception('等待图片生成超时（超过5分钟）')

    async def _get_image_urls(self):
        """获取生成的图片URL - 与原版一致"""
        images = await self.page.locator('._image-visible_c32gq_184').all()

        urls = []
        for img in images:
            src = await img.get_attribute('src')
            if src and src not in urls:
                urls.append(src)

        if len(urls) == 0:
            raise Exception('未能获取到生成的图片URL')

        return urls[:4]

    async def close(self):
        """关闭浏览器 - 与原版一致"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None
            print("[INFO] 浏览器已关闭")


async def main():
    """测试主函数"""
    generator = BaiduImageGenerator()

    try:
        prompt = "一只可爱的橘猫在草地上玩耍"
        result = await generator.generate_image(prompt)

        print("\n" + "="*50)
        print("生成结果:")
        print(f"提示词: {result['prompt']}")
        print(f"图片数量: {len(result['all_urls'])}")
        print("\n图片 URLs:")
        for i, url in enumerate(result['all_urls'], 1):
            print(f"  {i}. {url}")
        print("="*50)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        await generator.close()


if __name__ == "__main__":
    print("="*50)
    print("百度AI图片生成器 - 独立测试")
    print("="*50 + "\n")
    asyncio.run(main())
