# 豆包（头条搜索）与百度/必应站长平台 Sitemap 提交操作指南

豆包联网检索的核心底层网页索引是字节跳动的**头条搜索（Bytespider）**，DeepSeek 联网检索则重度依赖**必应（IndexNow）、百度与头条/搜狗**网页索引。把官网 `Sitemap` 提交一次后，搜索引擎爬虫会**每天自动定时拉取新文章**，无需每次发文重复手工提交。

---

## 一、头条搜索站长平台提交（打通「豆包」最快通道）

> 官网根目录已存在历史字节验证文件 `https://www.sensteed.com/ByteDanceVerify.html`（创建时间 2023-11-21）。

### 情况 A：能找到公司之前注册头条站长平台的账号
1. 浏览器打开 **头条搜索站长平台**：https://zhanzhang.toutiao.com/ 并登录。
2. 进入 **「站点管理」**，点击已验证的 `https://www.sensteed.com`。
3. 左侧菜单点击 **「数据提交」 → 「Sitemap 提交」**。
4. 依次填入以下两条地址并点击提交（提交一次即可永久自动抓取）：
   - `https://www.sensteed.com/insights/sitemap.xml`
   - `https://www.sensteed.com/sitemap.xml`

### 情况 B：找不到之前的旧账号（直接绑到你自己手机号下，1 分钟搞定）
因为我们拥有官网虚拟主机根目录权限，**不需要找旧账号**，可以直接用你自己的账号新增绑定：
1. 打开 https://zhanzhang.toutiao.com/ ，用你的手机号或今日头条账号注册登录。
2. 点击 **「站点管理」 → 「添加网站」**，协议选 `https://`，填入 `www.sensteed.com`。
3. 验证方式建议选 **「HTML 标签验证」** 或 **「文件验证」**：
   - 若选**文件验证**：注意如果平台生成的文件名仍叫 `ByteDanceVerify.html`，直接覆盖会导致旧账号掉线；优先选 **「HTML 标签验证」**（在首页 `<head>` 加一行 `<meta name="bytedance-verification-code" content="..." />`，可多账号并存！）。
4. 把平台给你的那行 `<meta ...>` 验证代码发给 AI 助手（或放入官网 `gb_header.html.php`），上传后回网页点 **「完成验证」** 即可立即生效，随后按「情况 A」第 3–4 步提交两条 Sitemap 即可。

---

## 二、百度搜索资源平台提交（补充国内通用与大模型索引）

> 官网根目录同样已存在百度验证文件 `https://www.sensteed.com/baidu_verify_codeva-S03vsLYuKY.html`。

1. 打开 **百度搜索资源平台**：https://ziyuan.baidu.com/ 登录（若找不到旧账号，同样可用 **HTML 标签验证** 新增绑定到自己账号）。
2. 进入 **「搜索服务」 → 「普通收录」 → 「资源提交」 → 「Sitemap」**。
3. 填入并提交：
   - `https://www.sensteed.com/insights/sitemap.xml`
   - `https://www.sensteed.com/sitemap.xml`

---

## 三、Bing / IndexNow 实时主动推送（打通 DeepSeek 外部网页检索，已自动配置完成）

- 官网根目录已部署 `IndexNow` 密钥验证文件，且全量文章 URL 已主动推送至 `https://api.indexnow.org/indexnow`（返回 `HTTP 202` 接收成功）。
- 如需查看抓取报表，可打开 **Bing Webmaster Tools**（https://www.bing.com/webmasters ），添加 `https://www.sensteed.com` 并提交 `https://www.sensteed.com/insights/sitemap.xml`。
