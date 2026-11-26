# 集团官网（sensteed.com）GEO 静态接收端与 SEO 合规改造说明

本目录保存山子高科官网二级专栏 `https://www.sensteed.com/insights/`（**山子高科·关键信息**）的接收端源码（兼容官网 Apache + PHP 5.2+ 环境）及主站模板 SEO/GEO 改造说明。

## 一、`/insights/` 自动静态接收端特性

1. **协议兼容与安全签名**：完整实现 `GEOFlow Agent v1` 签名协议（`HMAC-SHA256` + 时间戳防重放 + `config.php`/`storage/` `403` 访问拦截）。
2. **零数据库纯静态生成**：每次在 GEOFlow 后台点击发布/更新/撤回，毫秒级在 `/htdocs/insights/article/<slug>.html` 生成独立静态 HTML 页面（同时已合并导入原 `cat_id=68` 历史关键信息文章 `keyinfo-299..304`）：
   - 独立 `<title>文章真标题 - 山子高科(000981)</title>`
   - 独立 `<meta name="description">` 与 `<meta name="keywords">`
   - 唯一文章真标题 `<h1>` + 规范化 `<h2>`/`<h3>`/`<table>` 语义层级
   - 自动注入 `@graph` 结构化数据（`Corporation` 上市公司实体 `#corporation` + `NewsArticle` + `BreadcrumbList` 面包屑 + 自动识别 `Q1/问：` 与标题问答生成的 `FAQPage` JSON-LD），对人类访客视觉零改动
3. **四重索引自动联动刷新 + 百度实时主动推送**：
   - `/insights/index.html`（关键信息专栏总览页，内置 `Corporation` + `CollectionPage` + `BreadcrumbList` JSON-LD）
   - `/insights/sitemap.xml`（专栏独立 Sitemap）
   - `/insights/llms.txt` 与主站根目录 `/llms.txt`（面向生成式 AI 引擎的标准索引）
   - 主站 `/sitemap.xml`（毫秒级本地合并 `/insights/` 最新文章 URL，杜绝静态 Sitemap 漏更）
   - **百度 API 实时主动推送**：每次从 GEOFlow 分发或更新文章时，`/insights/index.php` 自动通过 `data.zz.baidu.com/urls` 实时主动推送新文章 URL（密钥保存在 `403` 受保护的 `config.php` 中，配额不足时非阻塞降级记录日志，绝不影响正常发文）；同时本地提供一键补推脚本 `python scripts/push_urls_to_engines.py`（双推 `IndexNow` + `Baidu API`）。

## 二、主站同步完成的合规与结构修复

1. **清除 `opacity: 0` 作弊属性并实现环境融合入口**：移除原页脚数据库字段与样式中的 `opacity: 0` 透明链接，改为在页脚「技术支持：浙江星动」右侧放置与 `#252525` 深色底栏融为一体的 `#272727` `12px` 文字入口 `关键信息`（指向 `/insights/`，平时肉眼无感、悬停柔和浮现，不使用 `opacity:0` 或 `display:none`）。
2. **历史文章页唯一 `<h1>` 修复**：在 `gb_banner.html.php`、`gb_new_view.html.php` 与 `view.php` 中，将详情页顶部栏目名由 `<h1>` 改为等视觉样式 `<div>`，将文章真标题提升为页面唯一 `<h1>`，并将富文本正文内嵌 `<h1>` 自动降级为 `<h2>`。
3. **清除历史曾用名链接遗留**：将页脚站点地图中深交所信息披露外链的旧参数 `ST银亿` 更新为 `山子高科`（HTTPS）。
4. **`robots.txt` 双 Sitemap 声明与 `IndexNow` 主动推送**：同时声明 `https://www.sensteed.com/sitemap.xml` 与 `https://www.sensteed.com/insights/sitemap.xml`，并在根目录配置 `IndexNow` 验证文件主动推送新 URL。
5. **头条搜索与百度搜索资源平台 HTML 所有权验证标签**：在主站中英文头部源码模板（`gb_header.html.php`、`en_header.html.php`）及 XYCMS 编译缓存（`tpl_default_gb_header.php`、`tpl_default_en_header.php`）的 `<head>` 内同步写入 `bytedance-verification-code` 与 `baidu-site-verification` 两条 `<meta>` 标签，与根目录历史验证文件并存，请勿删除。
6. **主站全站隐形 `Corporation` JSON-LD 实体锚点**：在主站中英文头部源码模板（`gb_header.html.php`、`en_header.html.php`）及编译缓存（`tpl_default_gb_header.php`、`tpl_default_en_header.php`）的 `<head>` 内注入标准 `https://schema.org/Corporation` JSON-LD（`@id: https://www.sensteed.com/#corporation`），明确声明证券代码 `SZSE:000981`、法定名称 `山子高科技股份有限公司`（`ShanZi High-Tech Co., Ltd.`）、核心下属企业 `邦奇动力 (Punch Powertrain)` 与 `艾尔希 (ARC Automotive)` 及核心技术领域，并与 `/insights/` 专栏及单篇静态页的 `@graph`（`Corporation + CollectionPage / NewsArticle + BreadcrumbList + FAQPage`）实现统一 `@id` 实体关联，对人类访客页面外观零影响。
