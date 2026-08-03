---
name: baiduai-image-generator
description: 当用户想要生成图片、画一张图、做一张图、给我画个 xxx 等场景时使用此 Skill。通过 Node.js 调用本地 Playwright 脚本，驱动浏览器在百度 AI 页面生成图片，并将生成的图片 URL 返回给用户。
---

# BaiduAI 生图 Skill

当用户希望生成一张图片（任何"画图/生图/给我来一张"类请求）时，按下面的流程调用本地 `Baiduai.js` 脚本来完成。

## 工作原理

`Baiduai.js` 通过 Node.js 启动 Playwright 控制 Chromium，访问百度 AI 页面，模拟用户操作输入提示词并触发生图，从页面抓取生成的图片 URL 后**随机选取其中一张**输出为 JSON。每次只返回一张图片。

## 调用方式

在 AstrBot 运行环境中执行 Node 脚本，命令格式：

```bash
cd <插件所在目录>
node Baiduai.js "<用户的图片描述>"
```

或者在 AstrBot 中通过 shell 工具调用：

```bash
cd <插件绝对路径> && node Baiduai.js "<prompt>"
```

`<prompt>` 为用户希望生成的图片描述，建议直接使用用户的原始描述（中文即可）。

脚本会输出 JSON 到 stdout：

- 成功：`{"success": true, "prompt": "...", "all_urls": ["..."], "selected_url": "...", "created_at": "..."}`
- 失败：stderr 输出 `{"error": "..."}`，退出码非 0

## 拿到结果后

1. 从 JSON 中取出 `all_urls` 字段（一个 URL 数组，**只包含一张随机选中的图片**）。
2. **调用 `send_image` 工具**，把 `all_urls` 整个传进去，工具内部会直接把图片发给用户：

   ```
   send_image(image_urls=[<url1>])
   ```

   不要自己把链接拼成 Markdown 或 base64 输出给用户——必须通过这个工具发送，否则用户看不到图。

3. 如果 `all_urls` 为空，直接告诉用户"未收到图片 URL，请稍后重试"，不要调用工具。

## 依赖与常见问题（必须先检查）

调用前请先判断运行环境是否就绪。**如果下面的环境检查不通过，不要盲目重试**，先告诉用户具体缺什么并给出修复建议。

### 1. Node.js 是否安装

```bash
node -v
```

如果提示 `command not found` 或 `node 不是内部或外部命令`，说明用户机器上没装 Node.js。请告诉用户去 https://nodejs.org/ 下载安装 LTS 版本，安装后重新启动 AstrBot。

### 2. npm 依赖是否安装

检查插件目录下是否有 `node_modules`：

```bash
ls <插件目录>/node_modules | head
```

如果不存在或没有 `playwright` 子目录，说明 npm 依赖未安装。请告诉用户在插件目录下执行：

```bash
cd <插件目录>
npm install
```

### 3. Chromium 浏览器是否已下载

Playwright 需要单独下载 Chromium 浏览器内核。如果脚本报类似以下错误，说明 Chromium 没装：

- `Executable doesn't exist at ...chromium...`
- `playwright install`
- `browserType.launch: Executable doesn't exist`
- 首次启动超时 / 找不到 chromium

请告诉用户在插件目录下执行：

```bash
cd <插件目录>
npx playwright install chromium
```

> 注意：在 AstrBot 部署在容器/服务器/Windows 服务的环境中，Chromium 经常因为重启或环境重置而丢失，需要重新执行上面的命令。如果用户报"前几天还能用，现在不行了"，**第一件事就检查 Chromium 是否还在**。

### 4. 其它常见运行时报错

- **首次启动慢**：Playwright 首次启动 Chromium 需要几秒到十几秒，超过 1 分钟没返回再考虑超时。
- **百度风控/未登录**：如果脚本报 `检测到百度安全验证` 或 `未找到发送按钮`，说明百度页面触发了风控或要求登录。这种情况无法通过代码解决，请直接告诉用户需要在能登录百度账号的浏览器环境中运行，或稍后再试。
- **超时（超过 5 分钟）**：生图本身可能较慢，但如果持续超时，结合上面的情况检查依赖和 Chromium。

## 行为准则

- 用户没有要求生图时，不要主动调用此 Skill。
- 始终把脚本输出原样转给用户看（含错误信息），方便排错。
- 如果依赖缺失，告诉用户**具体缺什么 + 怎么装**，不要笼统说"环境有问题"。
- 不要替用户执行 `npm install` 或 `npx playwright install chromium`（涉及文件系统修改和长时间下载），把命令交给用户自己跑。
- **拿到 URL 后必须调用 `send_image` 工具发送**，这是本插件对外暴露的唯一发图工具；不要在文本里直接贴链接。
