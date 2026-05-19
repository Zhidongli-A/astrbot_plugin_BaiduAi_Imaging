const { chromium } = require('playwright');

class BaiduImageGenerator {
  constructor() {
    this.browser = null;
    this.page = null;
  }

  async init() {
    this.browser = await chromium.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu'
      ]
    });

    this.page = await this.browser.newPage({
      viewport: { width: 1920, height: 1080 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    });

    this.page.setDefaultTimeout(60000);
    this.page.setDefaultNavigationTimeout(120000);
  }

  async generateImage(prompt) {
    if (!this.page) {
      await this.init();
    }

    try {
      await this.page.goto('https://chat.baidu.com/?enter_type=chat_url', {
        waitUntil: 'domcontentloaded',
        timeout: 120000
      });
      await this.page.waitForTimeout(5000);

      const aiImageButton = await this.page.locator('div').filter({ hasText: /^AI生图$/ }).first();
      await aiImageButton.waitFor({ state: 'visible', timeout: 15000 });
      await aiImageButton.click();
      await this.page.waitForTimeout(3000);

      const inputBox = await this.page.locator('div[contenteditable="true"]').first();
      await inputBox.waitFor({ state: 'visible', timeout: 20000 });
      await inputBox.click();
      await this.page.waitForTimeout(500);
      await this.page.keyboard.press('Control+a');
      await this.page.waitForTimeout(200);
      await this.page.keyboard.press('Delete');
      await this.page.waitForTimeout(200);
      await inputBox.fill(prompt);
      await this.page.waitForTimeout(1000);

      const sendButton = await this.page.locator('#ci-submit-button-ai');
      await sendButton.waitFor({ state: 'visible', timeout: 15000 });
      await sendButton.click();
      await this.page.waitForTimeout(5000);

      await this.waitForGenerationComplete();
      const imageUrls = await this.getImageUrls();

      return {
        success: true,
        prompt: prompt,
        all_urls: imageUrls,
        created_at: new Date().toISOString()
      };

    } catch (error) {
      throw error;
    }
  }

  async waitForGenerationComplete() {
    const maxWaitTime = 300000;
    const checkInterval = 3000;
    const startTime = Date.now();
    let lastPercentage = '';
    let imagesDetected = false;

    while (Date.now() - startTime < maxWaitTime) {
      try {
        const loadingElements = await this.page.locator('text=/收集中|生成中|[0-9]+%/').all();
        let isLoading = false;

        for (const el of loadingElements) {
          if (await el.isVisible().catch(() => false)) {
            const text = await el.textContent();
            if (text && text !== lastPercentage) {
              lastPercentage = text;
            }
            isLoading = true;
          }
        }

        const images = await this.page.locator('._image-visible_c32gq_184').all();

        if (images.length >= 4 && !imagesDetected) {
          imagesDetected = true;
        }

        if (imagesDetected && !isLoading) {
          await this.page.waitForTimeout(5000);
          return;
        }

      } catch (e) {}

      await this.page.waitForTimeout(checkInterval);
    }

    throw new Error('等待图片生成超时（超过5分钟）');
  }

  async getImageUrls() {
    const images = await this.page.locator('._image-visible_c32gq_184').all();

    let urls = [];
    for (const img of images) {
      const src = await img.getAttribute('src');
      if (src && !urls.includes(src)) {
        urls.push(src);
      }
    }

    if (urls.length === 0) {
      throw new Error('未能获取到生成的图片URL');
    }

    return urls.slice(0, 4);
  }

  async close() {
    if (this.browser) {
      await this.browser.close();
      this.browser = null;
      this.page = null;
    }
  }
}

// 直接运行入口
async function main() {
  const prompt = process.argv[2];
  if (!prompt) {
    console.error(JSON.stringify({ error: '请提供提示词' }));
    process.exit(1);
  }

  const generator = new BaiduImageGenerator();
  try {
    const result = await generator.generateImage(prompt);
    console.log(JSON.stringify(result));
    await generator.close();
  } catch (error) {
    console.error(JSON.stringify({ error: error.message }));
    await generator.close();
    process.exit(1);
  }
}

main();
