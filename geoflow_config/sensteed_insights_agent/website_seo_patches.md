# 集团官网（sensteed.com）GEO 静态接收端与 SEO 合规改造说明

本目录保存山子高科官网二级专栏 `https://www.sensteed.com/insights/` 的接收端源码（兼容官网 Apache + PHP 5.2+ 环境）及主站模板 SEO/GEO 改造说明。

## 一、`/insights/` 自动静态接收端特性

1. **协议兼容与安全签名**：完整实现 `GEOFlow Agent v1` 签名协议（`HMAC-SHA256` + 时间戳防重放 + `config.php`/`storage/` `403` 访问拦截）。
2. **零数据库纯静态生成**：每次在 GEOFlow 后台点击发布/更新/撤回，毫秒级在 `/htdocs/insights/article/<slug>.html` 生成独立静态 HTML 页面：
   - 独立 `<title>文章真标题 - 山子高科(000981)</title>`
   - 独立 `<meta name="description">` 与 `<meta name="keywords">`
   - 唯一文章真标题 `<h1>` + 规范化 `<h2>`/`<h3>`/`<table>` 语义层级
   - 自动注入 `NewsArticle` JSON-LD，并在检测到问答结构时自动提取生成 `FAQPage` JSON-LD
3. **四重索引自动联动刷新**：
   - `/insights/index.html`（专栏索引页）
   - `/insights/sitemap.xml`（专栏独立 Sitemap）
   - `/insights/llms.txt` 与主站根目录 `/llms.txt`（面向生成式 AI 引擎的标准索引）
   - 主站 `/sitemap.xml`（毫秒级本地合并 `/insights/` 最新文章 URL，杜绝静态 Sitemap 漏更）

## 二、主站同步完成的合规与结构修复

1. **清除 `opacity: 0` 隐藏链接作弊风险**：移除原页脚数据库字段与样式中的 `opacity: 0` 透明链接，改为在页脚「技术支持：浙江星动」右侧放置正常可见、低对比度 `12px` 浅灰文字入口 `资料索引`（指向 `/insights/`），符合字节/头条搜索与百度反作弊规范。
2. **历史文章页唯一 `<h1>` 修复**：在 `gb_banner.html.php`、`gb_new_view.html.php` 与 `view.php` 中，将详情页顶部栏目名由 `<h1>` 改为等视觉样式 `<div>`，将文章真标题提升为页面唯一 `<h1>`，并将富文本正文内嵌 `<h1>` 自动降级为 `<h2>`。
3. **清除历史曾用名链接遗留**：将顶部导航栏深交所信息披露外链中的旧参数 `ST银亿` 更新为 `山子高科`（HTTPS）。
4. **`robots.txt` 双 Sitemap 声明**：同时声明 `https://www.sensteed.com/sitemap.xml` 与 `https://www.sensteed.com/insights/sitemap.xml`。
