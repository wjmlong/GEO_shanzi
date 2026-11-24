# 豆包（头条搜索）与百度/必应站长平台 Sitemap 提交操作指南

豆包联网检索的核心底层网页索引是字节跳动的**头条搜索（Bytespider）**，DeepSeek 联网检索则重度依赖**必应（IndexNow）、百度与头条/搜狗**网页索引。把官网 `Sitemap` 提交一次后，搜索引擎爬虫会**每天自动定时拉取新文章**，无需每次发文重复手工提交。

---

## 一、头条搜索站长平台提交（打通「豆包」最快通道）

> **状态：HTML 标签验证已部署上线**
> - 首页 `<head>` 已写入 `<meta name="bytedance-verification-code" content="pYOH6kJPhe2BRxJr+Oi9" />`（同步覆盖源码模板 `gb_header.html.php`、`en_header.html.php` 与编译缓存 `tpl_default_gb_header.php`、`tpl_default_en_header.php`，并保留根目录历史 `ByteDanceVerify.html`）。
> - 为保持站点验证状态，后续更新头部模板时**请勿删除该 `<meta>` 标签**。

### 实测排障：提示「验证失败，该站点已经被注册」怎么办？
官网根目录在 **2023-11-21** 已由历史经办人/建站服务商上传过 `ByteDanceVerify.html`，说明 `www.sensteed.com` **早已在头条站长平台完成过认证入库**（头条实行单域名唯一账号绑定机制，旧账号未解绑前新账号无法重复绑定）：
1. **不影响当前抓取闭环**：由于我们已将 `/insights/` 全部文章自动实时合并进主站原有的 `https://www.sensteed.com/sitemap.xml`，并在首页放置了真实 HTML 链接 `<a href="/insights/">关键信息</a>` 及 `robots.txt` 双声明，头条蜘蛛（`Bytespider`）沿原有主站 Sitemap 与首页巡检即可自动抓取全部新文章。
2. **10 秒快速排查协议差异**：点击「上一步」，确认第一步协议下拉框选的是 `http://` 还是 `https://`；若此前旧账号绑的是 `http://www.sensteed.com`，切换为 `https://www.sensteed.com` 可尝试独立验证。
3. **取回站点管理权的两种方式**：
   - **内部交接（最快）**：联系 2023 年 11 月负责官网建站/运维的同事或服务商（浙江星动），登录原头条号在「站点管理」中删除解绑后，当前账号点「验证」即可秒过。
   - **官方申诉强制解绑**：点击头条站长平台顶部「联系我们」（或发邮件至 `zhanzhang@bytedance.com`），附上**山子高科技股份有限公司营业执照扫描件 + ICP 备案截图（`陇ICP备17001116号-5`）+ 阿里云万网主机控制台截图**，申请强制解除 `www.sensteed.com` 的历史账号绑定。

---

## 二、百度搜索资源平台提交（站点已验证成功！）

> **状态：站点所有权验证已通过（`https://www.sensteed.com`）**
> - 首页 `<head>` 已写入 `<meta name="baidu-site-verification" content="codeva-BYRCEuMkkZ" />`（与根目录历史 `baidu_verify_codeva-S03vsLYuKY.html` 并存，请勿删除）。

### 为什么 `sitemap` 标签页显示「今日提交上限：0条」？如何立刻提交？
百度近年对新绑定账号默认关闭 `sitemap` 文件提交配额（显示 0 条），但**不影响立即推送收录**，请直接用以下 3 个现成通道：

1. **通道 A：`普通收录` → `手动提交`（立即可用，每次最多 20 条）**
   切到蓝色的 **「手动提交」** 标签页，直接把当前 `/insights/` 全部 10 条链接一次性粘贴进去点击 **「提交」**：
   ```text
   https://www.sensteed.com/insights/
   https://www.sensteed.com/insights/article/y2mdwbg5.html
   https://www.sensteed.com/insights/article/bzpigrtn.html
   https://www.sensteed.com/insights/article/7ttgnthv.html
   https://www.sensteed.com/insights/article/keyinfo-304.html
   https://www.sensteed.com/insights/article/keyinfo-303.html
   https://www.sensteed.com/insights/article/keyinfo-302.html
   https://www.sensteed.com/insights/article/keyinfo-301.html
   https://www.sensteed.com/insights/article/keyinfo-300.html
   https://www.sensteed.com/insights/article/keyinfo-299.html
   ```
2. **通道 B：`普通收录` → `API提交`（已全自动接入官网接收端！）**
   - 官网 `/htdocs/insights/index.php` 已内置百度实时主动推送（密钥存于受 `.htaccess` `403` 保护的 `config.php` 中）：以后在 GEOFlow 点击「分发」，官网生成静态页的同时会**自动向 `data.zz.baidu.com/urls` 秒推新文章链接**。
   - 本地仓库同时提供一键批量补推脚本：`python scripts/push_urls_to_engines.py`（从 `.gitignore` 忽略的 `.env.local` 读取 `BAIDU_PUSH_TOKEN`，一键向 **IndexNow + 百度 API** 同步推送，并在批量超额时自动切换逐条降级推送）。
   - **关于新站首日 `over quota` 提示**：刚完成验证的新站点首日主动推送配额通常为 `0`，请在百度后台左侧 **「站点信息」** 中补充关联公司 ICP 备案号 `陇ICP备17001116号-5` 并勾选站点行业属性，待百度每日零点刷新配额后，官网每次发文即会自动消耗配额秒推。
3. **通道 C：左侧 `数据统计` → `Robots`（已检测生效！）**
   - `Robots` 工具已验证生效（`您的Robots文件已生效` / `robots没有错误`），两条 `Sitemap:` 声明已正式进入百度蜘蛛自然抓取队列。

---

## 三、Bing / IndexNow 实时主动推送（打通 DeepSeek 外部网页检索，已自动配置完成）

- 官网根目录已部署 `IndexNow` 密钥验证文件，且全量文章 URL 已主动推送至 `https://api.indexnow.org/indexnow`（返回 `HTTP 202` 接收成功）。
- 如需查看抓取报表，可打开 **Bing Webmaster Tools**（https://www.bing.com/webmasters ），添加 `https://www.sensteed.com` 并提交 `https://www.sensteed.com/insights/sitemap.xml`。
