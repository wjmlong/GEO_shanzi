# 国内 AI 引擎 GEO 采样

个人、非商业使用，目标为山子高科（000981）。仅使用 requests、既有 PyYAML 和标准库；Python 3.10，SQLite WAL。未核实在线接口，开发和测试不联网。

## 使用

所需环境变量：`DEEPSEEK_API_KEY`、`ARK_API_KEY`、`DOUBAO_ENDPOINT_ID`。
请在本机 shell 中设置并导出环境变量，或自行将其保存在已被 .gitignore 忽略的 `.env` 后由你自己的环境管理工具导入 shell。程序不自动读取 `.env`，不要把密钥填入 YAML、命令行参数或提交到仓库。缺少 key 或豆包接入点的引擎会明确提示并跳过。

```bash
python3 monitor.py geo run --engines deepseek,doubao --groups brand,category,holdout --repeat 3 --dry-run
python3 monitor.py geo run --engines deepseek,doubao --groups brand,category,holdout --repeat 3
python3 monitor.py geo report
python3 monitor.py geo report --run 1
# 等价入口
python3 -m geo.cli run --dry-run
```

实际 run 会调用收费 API；dry-run 只输出缺失配置提示、计划调用数和粗估 token，不请求接口、不打开数据库。估算输入为题目字符数 × 1.5 加消息开销，输出默认每调用 600 token；它不是计费预测或输出长度限制，不含重试。未读取退避状态，因此实际调用数可能更少。默认 30 题 × 2 引擎 × 3 次 = 180 个样本，全部发生三次重试时最多 720 次 HTTP 请求。

run 和 report 均支持 `--db`（默认项目的 guba.db）；run 支持 `--config`、`--questions`、`--brand` 指定 YAML 文件。run 结束直接输出 Markdown；可用 shell 重定向保存 report。定时使用系统 cron，例如（完成本地环境配置后自行启用）：

```cron
0 9 * * * cd /mnt/e/DISK_D/Project/GEO && /usr/bin/python3 -m geo.cli run >> /tmp/geo-sampling.log 2>&1
```

cron 环境独立，需要自行注入上述变量；不要让两个采样任务重叠运行。

## 配置与题库

`config.yaml` 的 `repeat` 默认 3，可由 CLI 覆盖；`interval` 默认 1 秒，控制样本之间的间隔；`temperature` 默认 0.7；`timeout` 默认 60 秒；`estimated_output_tokens` 仅供 dry-run 估算。引擎配置可覆盖 temperature、interval（重试最小间隔）、timeout。

DeepSeek 默认地址 https://api.deepseek.com，`engines.deepseek.model` 默认 deepseek-chat。豆包默认地址 https://ark.cn-beijing.volces.com/api/v3，模型从 `DOUBAO_ENDPOINT_ID` 读取（ep-xxxx 接入点），不使用 YAML 中的 model。

每引擎配置 `web_search: "off"` 或 `"on"`，默认 off。**必须加引号**，避免 YAML 1.1 自动转成布尔值。联网参数待按官方文档核实；on 模式要求填写 `extra_body`，该对象的字段原样合入请求体，不硬编码任何联网字段。off 模式忽略 extra_body。禁止覆盖 model/messages/temperature/stream，避免存储元数据与真实请求不符。on 只代表请求意图，不证明服务端进行了搜索。

questions.yaml 有版本号与 30 条占位题，每组 10 条；每题包含 id、group、intent、text。brand 为品牌直问，category 为品类/场景问，holdout 为独立留出题，**不得参与任何内容优化**。品类（尤其化工新材料）与当前业务是否适配，需要用户确认；题目不是对主营业务的事实断言。修改题库请递增 version，并保持留出题独立维护。

brand.yaml 的银亿股份标记为历史名称，ST银亿等历史简称也需要用户确认。competitors 暂空，请填名称字符串，或 `{name: 公司名, aliases: [别名]}`。

## 存储、错误与报告

独立迁移创建 geo_runs、geo_samples，不改变现有表含义；analysis_json 补充保存 URL、公司列表名次等规则结果。geo_attempts 保存每次 HTTP 尝试的请求时间、延迟、原始 JSON、状态及错误，通过 sample_id 关联引擎、模型、联网模式和温度；每次响应里的 usage 保留在原始 JSON 中。geo_samples 的原始响应和 token 是最后一次尝试，延迟为含重试等待的总耗时，asked_at 是首次请求时间。非 JSON 响应以 response_text 保存。运行 note 保存题库、分析配置和采样配置快照，不保存环境变量。

429/5xx 最多重试三次，等待 1、2、4 秒（或配置的更大最小间隔）；其他 4xx、传输异常和解析失败不重试，记录错误后继续下一题。样本逐条提交；中断时保留已写入的数据。空回答视为错误。

使用 store.py 的 `geo:deepseek`、`geo:doubao` 平台状态；每个失败样本调用现有 record_failure，30 分钟起指数退避至最大 12 小时。本轮继续采样，下轮检查退避；整轮全部成功才清零。此策略是为了兼容现有平台规则，发生限流后当前轮仍可能产生更多失败。已有退避跳过时不制造 error 样本，原因写入 run note。

报告分别统计 brand/category/holdout，且按引擎、模型、联网模式和温度分别列出。error 样本不进入提及率、位置、情感和域名分母；全部失败时比率为 N/A。位置从 0 开始，只对品牌命中样本求平均。域名 Top10 按出现次数计数，将 www. 前缀合并，其余子域名独立。差值比较上一 run 的相同配置与题库版本；配置或版本缺失匹配时 N/A。情感和域名差值为计数差，采样数量变化时需要谨慎解读。

兼容说明：保留已有 `analyze_answer` 和 `build_geo_report` 核心入口及其原统计口径；新命令行使用 `analyze` 和 `build_report`，后者按配置隔离并按域名出现次数统计。不要混用两套报告的域名计数或版本差值。

## 已知局限与待核实事项

**API 回答 ≠ 用户在豆包/DeepSeek App 里看到的联网搜索结果；两者要分别统计，不能混用。**

- 未进行任何真实接口验收；豆包接入点可用性、模型支持的 temperature 范围、账户权限、额度与响应 usage 字段需要用户核实。
- 豆包方舟是否支持本接入点联网、额外请求体字段名及结构、引用信息返回位置，均需按官方文档核实。DeepSeek API 是否支持联网也未核实，不能以配置 on 推断其支持。
- 规则仅匹配答案正文，不验证引用是否真实，也不读取结构化搜索引用；裸域名匹配可能误把形似域名的文本算作来源。
- 重叠别名按最长优先、不重复计数；数字代码有数字边界。历史别名可能扩大命中。没有完整公司实体识别；公司名次仅在首次品牌命中前有显式列表编号时给出，该编号不保证等于真实公司排序，否则为空。
- 情感复用股吧词典，是整条回答的粗判，不能视为针对品牌的态度，反讽、否定、引用和多公司回答可能误判。analyze 的 hook 默认关闭，CLI 不启用模型复判。
- 采样有随机性；题库、别名、竞品、extra_body、重复次数或题目子集变化均影响可比性。即使模型名称不变，服务端模型版本也可能变化。
- 没有任务调度服务、并发运行锁、自动 App 采集或 token 成本核算；定时由外部调度器负责。报告包含原始运行配置和题目，请按个人数据管理要求保存。

离线测试：`python3 -m unittest discover -s tests -v`。新测试使用 requests mock 与内存数据库，不读取任何已有数据库或敏感文件。
