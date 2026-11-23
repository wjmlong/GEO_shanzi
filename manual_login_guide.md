# 手动导出东方财富 Cookie（替代 login.py）

Playwright 在你的环境里会卡死，改用手动导出 cookie。

## 步骤

### 1. 在 Windows 浏览器里登录东方财富

1. 打开 Chrome/Edge（Windows 本地浏览器，不是 WSL 里的）
2. 访问：https://guba.eastmoney.com/list,000981.html
3. 登录你的东方财富账号，过验证码
4. 随便点开一个帖子，确认能看到评论

### 2. 导出 Cookie

#### 方案 A：用浏览器扩展（推荐，最简单）

1. 安装扩展：
   - Chrome: [EditThisCookie](https://chromewebstore.google.com/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)
   - 或者: [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)

2. 在东方财富股吧页面，点击扩展图标
3. 点"导出" (Export) → 复制 JSON
4. 保存为 `E:\DISK_D\Project\GEO\eastmoney_cookies.json`

格式应该像这样（数组，每个 cookie 一个对象）：
```json
[
  {
    "domain": ".eastmoney.com",
    "name": "em_hq_fls",
    "value": "...",
    "path": "/",
    ...
  },
  ...
]
```

#### 方案 B：手动从开发者工具复制

1. 按 F12 打开开发者工具
2. 切到 Application (应用) 或 Storage (存储) 标签页
3. 左侧点 Cookies → https://guba.eastmoney.com
4. 右键第一条 cookie → "Copy all as JSON" 或逐条复制
5. 手动拼成上面的 JSON 格式，保存到 `E:\DISK_D\Project\GEO\eastmoney_cookies.json`

### 3. 测试

导出完成后，在 WSL 里运行：

```bash
cd /mnt/e/DISK_D/Project/GEO
python3 check_cookies.py
```

如果看到"Cookie 有效，拿到了评论数据"，就成功了。

## 注意事项

- `eastmoney_cookies.json` 相当于账号密码，权限设为只有你自己能读
- Cookie 会过期（一般几周到几个月），过期后重新导出一次
- 别把这个文件提交到 git 或上传到公开的地方
