const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

class BaiduImageGenerator {
  constructor() {
    this.browser = null;
    this.page = null;
  }

  async init() {
    const launchOpts = {
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu'
      ]
    };

    // Detect installed Playwright browsers; fall back to full Chromium
    // if headless shell is not available (common in China where downloads may
    // be blocked).
    const userDir = process.env.USERPROFILE;
    const playwrightDir = path.join(userDir, 'AppData', 'Local', 'ms-playwright');
    const headlessShellPath = path.join(
      playwrightDir,
      `chromium_headless_shell-${chromium._revision}`,
      'chrome-headless-shell-win64',
      'chrome-headless-shell.exe'
    );
    const fullChromiumPath = path.join(
      playwrightDir,
      `chromium-${chromium._revision}`,
      'chrome-win64',
      'chrome.exe'
    );

    if (!fs.existsSync(headlessShellPath)) {
      // Try older installed full Chromium as fallback
      const dirs = fs.readdirSync(playwrightDir, { withFileTypes: true });
      for (const dirent of dirs) {
        if (dirent.isDirectory() && /^chromium-\d+$/.test(dirent.name)) {
          const exePath = path.join(
            playwrightDir, dirent.name, 'chrome-win64', 'chrome.exe'
          );
          if (fs.existsSync(exePath)) {
            launchOpts.executablePath = exePath;
            break;
          }
        }
      }
    }

    this.browser = await chromium.launch(launchOpts);

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
      const selectedUrl = imageUrls[Math.floor(Math.random() * imageUrls.length)];

      return {
        success: true,
        prompt: prompt,
        all_urls: imageUrls,
        selected_url: selectedUrl,
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

    throw new Error('Image generation timed out (over 5 minutes)');
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
      throw new Error('Failed to retrieve generated image URLs');
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

module.exports = BaiduImageGenerator;
