const { chromium } = require('playwright');

class BaiduImageGenerator {
  constructor() {
    this.browser = null;
    this.page = null;
  }

  log(step, message) {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [${step}] ${message}`);
  }

  async init() {
    this.log('初始化', '正在启动浏览器...');
    this.browser = await chromium.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu'
      ]
    });
    this.log('初始化', '浏览器启动完成');

    this.log('初始化', '正在创建新页面...');
    this.page = await this.browser.newPage({
      viewport: { width: 1920, height: 1080 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    });
    this.log('初始化', '页面创建完成');

    this.page.setDefaultTimeout(60000);
    this.page.setDefaultNavigationTimeout(120000);
  }

  async generateImage(prompt) {
    if (!this.page) {
      await this.init();
    }

    this.log('请求', `开始生成图片: "${prompt}"`);

    try {
      // 步骤1: 访问页面
      this.log('步骤1', '正在访问百度AI页面...');
      await this.page.goto('https://chat.baidu.com/?enter_type=chat_url', {
        waitUntil: 'networkidle',
        timeout: 120000
      });
      await this.page.waitForTimeout(3000);
      this.log('步骤1', '页面加载完成');

      // 步骤2: 点击AI生图按钮
      this.log('步骤2', '正在查找并点击"AI生图"按钮...');
      const aiImageButton = await this.page.locator('div').filter({ hasText: /^AI生图$/ }).first();
      await aiImageButton.waitFor({ state: 'visible', timeout: 15000 });
      await aiImageButton.click();
      this.log('步骤2', '已点击AI生图按钮');
      
      // 等待页面切换
      await this.page.waitForTimeout(5000);

      // 步骤3: 查找输入框并输入提示词
      this.log('步骤3', '正在查找输入框...');
      const inputBox = await this.page.locator('div[contenteditable="true"]').first();
      await inputBox.waitFor({ state: 'visible', timeout: 20000 });
      
      this.log('步骤3', '找到输入框，正在输入提示词...');
      await inputBox.click();
      await this.page.waitForTimeout(500);
      await this.page.keyboard.press('Control+a');
      await this.page.waitForTimeout(200);
      await this.page.keyboard.press('Delete');
      await this.page.waitForTimeout(200);
      await inputBox.fill(prompt);
      await this.page.waitForTimeout(1000);
      this.log('步骤3', `提示词输入完成: "${prompt}"`);

      // 步骤4: 点击发送按钮
      this.log('步骤4', '正在查找发送按钮...');
      const sendButton = await this.page.locator('#ci-submit-button-ai');
      await sendButton.waitFor({ state: 'visible', timeout: 15000 });
      await sendButton.click();
      this.log('步骤4', '已点击发送按钮');
      
      await this.page.waitForTimeout(3000);

      // 步骤5: 等待图片生成
      this.log('步骤5', '等待图片生成完成...');
      await this.waitForGenerationComplete();
      this.log('步骤5', '图片生成完成');

      // 步骤6: 获取图片URL
      this.log('步骤6', '正在获取图片URL...');
      const imageUrls = await this.getImageUrls();
      this.log('步骤6', `成功获取 ${imageUrls.length} 张图片URL`);

      const selectedUrl = imageUrls[Math.floor(Math.random() * imageUrls.length)];

      this.log('完成', `图片生成成功: "${prompt}"`);
      this.log('完成', `选中图片URL: ${selectedUrl}`);

      return {
        success: true,
        prompt: prompt,
        all_urls: imageUrls,
        selected_url: selectedUrl,
        created_at: new Date().toISOString()
      };

    } catch (error) {
      this.log('失败', `生成失败: ${error.message}`);
      throw error;
    }
  }

  async waitForGenerationComplete() {
    const maxWaitTime = 300000;
    const checkInterval = 3000;
    const startTime = Date.now();
    let lastPercentage = '';
    let lastLogTime = 0;
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
              this.log('生成中', `当前进度: ${text}`);
            }
            isLoading = true;
          }
        }

        const images = await this.page.locator('._image-visible_c32gq_184').all();

        if (images.length >= 4 && !imagesDetected) {
          imagesDetected = true;
          this.log('生成中', `检测到 ${images.length} 张图片已生成`);
        }

        if (imagesDetected && !isLoading) {
          await this.page.waitForTimeout(5000);
          return;
        }

        // 每10秒输出一次状态
        if (Date.now() - lastLogTime > 10000) {
          lastLogTime = Date.now();
          const elapsed = Math.floor((Date.now() - startTime) / 1000);
          this.log('生成中', `已等待 ${elapsed} 秒...`);
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
      if (src && !urls.includes(src) && src.startsWith('http')) {
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
      this.log('关闭', '正在关闭浏览器...');
      await this.browser.close();
      this.browser = null;
      this.page = null;
      this.log('关闭', '浏览器已关闭');
    }
  }
}

module.exports = BaiduImageGenerator;
