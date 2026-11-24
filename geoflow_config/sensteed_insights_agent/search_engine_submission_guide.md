# 豆包（头条搜索）与百度/必应站长平台 Sitemap 提交操作指南

豆包联网检索的核心底层网页索引是字节跳动的**头条搜索（Bytespider）**，DeepSeek 联网检索则重度依赖**必应（IndexNow）、百度与头条/搜狗**网页索引。把官网 `Sitemap` 提交一次后，搜索引擎爬虫会**每天自动定时拉取新文章**，无需每次发文重复手工提交。

---

## 一、头条搜索站长平台提交（打通「豆包」最快通道）

> **状态：HTML 标签验证已部署上线**
> - 首页 `<head>` 已写入 `<meta name="bytedance-verification-code" content="pYOH6kJPhe2BRxJr+Oi9" />`（同步覆盖源码模板 `gb_header.html.php`、`en_header.html.php` 与编译缓存 `tpl_default_gb_header.php`、`tpl_default_en_header.php`，并保留根目录历史 `ByteDanceVerify.html`）。
> - 为保持站点验证状态，后续更新头部模板时**请勿删除该 `<meta>` 标签**。

### 操作步骤
1. 在 **头条搜索站长平台**（https://zhanzhang.toutiao.com/ ）验证页面直接点击蓝色 **「验证」** 按钮完成所有权绑定。
2. 验证通过后，左侧菜单点击 **「数据提交」 → 「自动收录」 / 「Sitemap」**（或 **「链接提交」**）。
3. 依次填入以下两条 Sitemap 地址并提交（提交一次即可每日自动巡检抓取）：
   - `https://www.sensteed.com/insights/sitemap.xml`
   - `https://www.sensteed.com/sitemap.xml`
4. 如需让单篇新稿件最快进入索引，也可在 **「链接提交」** 中一次性粘贴当前 `/insights/article/*.html` 文章链接主动推送。

---

## 二、百度搜索资源平台提交（补充国内通用与大模型索引）

> **状态：HTML 标签验证已部署上线**
> - 首页 `<head>` 已写入 `<meta name="baidu-site-verification" content="codeva-BYRCEuMkkZ" />`（与根目录历史 `baidu_verify_codeva-S03vsLYuKY.html` 并存，互不影响）。
> - 为保持站点验证状态，后续更新头部模板时**请勿删除该 `<meta>` 标签**。

### 操作步骤
1. 在 **百度搜索资源平台**（https://ziyuan.baidu.com/ ）第三步验证页面直接点击蓝色 **「完成验证」** 按钮。
2. 进入 **「搜索服务」 → 「普通收录」 → 「资源提交」 → 「Sitemap」**。
3. 依次填入并提交：
   - `https://www.sensteed.com/insights/sitemap.xml`
   - `https://www.sensteed.com/sitemap.xml`

---

## 三、Bing / IndexNow 实时主动推送（打通 DeepSeek 外部网页检索，已自动配置完成）

- 官网根目录已部署 `IndexNow` 密钥验证文件，且全量文章 URL 已主动推送至 `https://api.indexnow.org/indexnow`（返回 `HTTP 202` 接收成功）。
- 如需查看抓取报表，可打开 **Bing Webmaster Tools**（https://www.bing.com/webmasters ），添加 `https://www.sensteed.com` 并提交 `https://www.sensteed.com/insights/sitemap.xml`。
