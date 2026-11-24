@php
    $mx = \App\Http\Controllers\Admin\GeoMatrixController::matrixData();
    $mxSummary = $mx['summary'];
    $mxPlatforms = $mx['platforms'];
    $mxLedger = $mx['ledger'];
    $totalTitles = $mx['titles_by_lib']->flatten()->count();
    $totalKeywords = $mx['keywords_by_lib']->flatten()->count();
    $hubOnline = (bool) ($mx['browser_hub_online'] ?? false);
    $browserGuiUrl = request()->getScheme() . '://' . request()->getHost() . ':18082/vnc.html?autoconnect=true&resize=scale';
@endphp

<style>
    /* Minimalist Cool-Slate + GEOFlow Brand-Blue Design System (2 close color families only) */
    #sz-geo-console {
        --sz-surface: #FFFFFF;
        --sz-subtle: #F8FAFC;
        --sz-track: #F1F5F9;
        --sz-border: #E2E8F0;
        --sz-border-strong: #CBD5E1;
        --sz-ink: #0F172A;
        --sz-ink-2: #475569;
        --sz-ink-3: #64748B;
        --sz-blue: #2563EB;
        --sz-blue-hover: #1D4ED8;
        --sz-blue-ink: #1D4ED8;
        --sz-blue-soft: #EFF6FF;
        --sz-blue-border: #BFDBFE;
        color: var(--sz-ink);
        font-feature-settings: "tnum" 1;
    }
    #sz-geo-console .sz-card {
        background: var(--sz-surface);
        border: 1px solid var(--sz-border);
        border-radius: 12px;
        padding: 20px 24px;
    }
    #sz-geo-console .sz-inset {
        background: var(--sz-subtle);
        border: 1px solid var(--sz-border);
        border-radius: 10px;
    }
    #sz-geo-console .sz-kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-top: 18px;
    }
    @media (max-width: 768px) {
        #sz-geo-console .sz-kpi-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }
    #sz-geo-console .sz-kpi-box {
        background: var(--sz-subtle);
        border: 1px solid var(--sz-border);
        border-radius: 10px;
        padding: 14px 18px;
    }
    #sz-geo-console .sz-kpi-label {
        font-size: 12px;
        color: var(--sz-ink-3);
        line-height: 1.4;
    }
    #sz-geo-console .sz-kpi-val {
        margin-top: 6px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 24px;
        font-weight: 600;
        line-height: 1.2;
        color: var(--sz-ink);
    }
    #sz-geo-console .sz-kpi-val.is-accent {
        color: var(--sz-blue-ink);
    }
    #sz-geo-console .sz-title {
        font-size: 17px;
        font-weight: 600;
        color: var(--sz-ink);
        letter-spacing: -0.01em;
        line-height: 1.35;
    }
    #sz-geo-console .sz-section-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--sz-ink);
        line-height: 1.4;
    }
    #sz-geo-console .sz-subtitle {
        margin-top: 3px;
        font-size: 12px;
        color: var(--sz-ink-3);
        line-height: 1.5;
    }
    #sz-geo-console .sz-btn-primary {
        background: var(--sz-blue);
        color: #FFFFFF;
        border: 1px solid var(--sz-blue);
        border-radius: 8px;
        font-weight: 500;
        transition: background-color 140ms ease, border-color 140ms ease;
    }
    #sz-geo-console .sz-btn-primary:hover {
        background: var(--sz-blue-hover);
        border-color: var(--sz-blue-hover);
    }
    #sz-geo-console .sz-btn-primary:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
    #sz-geo-console .sz-btn-ghost {
        background: var(--sz-surface);
        color: var(--sz-ink);
        border: 1px solid var(--sz-border);
        border-radius: 8px;
        font-weight: 500;
        transition: background-color 140ms ease, border-color 140ms ease;
    }
    #sz-geo-console .sz-btn-ghost:hover {
        background: var(--sz-subtle);
        border-color: var(--sz-border-strong);
    }
    #sz-geo-console .sz-btn-blue-outline {
        background: var(--sz-surface);
        color: var(--sz-blue-ink);
        border: 1px solid var(--sz-blue-border);
        border-radius: 8px;
        font-weight: 500;
        transition: background-color 140ms ease, border-color 140ms ease;
    }
    #sz-geo-console .sz-btn-blue-outline:hover {
        background: var(--sz-blue-soft);
        border-color: var(--sz-blue);
    }
    #sz-geo-console .sz-seg {
        display: inline-flex;
        align-items: center;
        background: var(--sz-track);
        border: 1px solid var(--sz-border);
        border-radius: 8px;
        padding: 3px;
        gap: 2px;
    }
    #sz-geo-console .sz-seg-btn {
        white-space: nowrap;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 500;
        color: var(--sz-ink-2);
        transition: background-color 140ms ease, color 140ms ease;
    }
    #sz-geo-console .sz-seg-btn.is-active {
        background: var(--sz-surface);
        color: var(--sz-blue-ink);
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
    }
    #sz-geo-console .sz-tag-slate {
        display: inline-flex;
        align-items: center;
        background: var(--sz-track);
        color: var(--sz-ink-2);
        border: 1px solid var(--sz-border);
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 500;
        white-space: nowrap;
    }
    #sz-geo-console .sz-tag-blue {
        display: inline-flex;
        align-items: center;
        background: var(--sz-blue-soft);
        color: var(--sz-blue-ink);
        border: 1px solid var(--sz-blue-border);
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 500;
        white-space: nowrap;
    }
    #sz-geo-console .sz-input {
        background: var(--sz-surface);
        border: 1px solid var(--sz-border);
        border-radius: 8px;
        color: var(--sz-ink);
        transition: border-color 140ms ease;
    }
    #sz-geo-console .sz-input:focus {
        outline: none;
        border-color: var(--sz-blue);
    }
    #sz-geo-console .sz-dropzone {
        background: var(--sz-subtle);
        border: 1px solid var(--sz-border);
        border-radius: 10px;
        padding: 20px 16px;
        text-align: center;
        cursor: pointer;
        transition: border-color 150ms ease, background-color 150ms ease;
    }
    #sz-geo-console .sz-dropzone:hover,
    #sz-geo-console .sz-dropzone.is-dragover {
        background: var(--sz-blue-soft);
        border-color: var(--sz-blue);
    }
    #sz-geo-console .sz-plat-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin-top: 16px;
    }
    @media (max-width: 1024px) {
        #sz-geo-console .sz-plat-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }
    @media (max-width: 640px) {
        #sz-geo-console .sz-plat-grid {
            grid-template-columns: minmax(0, 1fr);
        }
    }
    #sz-geo-console .sz-plat-card {
        background: var(--sz-surface);
        border: 1px solid var(--sz-border);
        border-radius: 10px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: border-color 150ms ease, box-shadow 150ms ease;
    }
    #sz-geo-console .sz-plat-card:hover {
        border-color: var(--sz-blue-border);
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.05);
    }
    #sz-geo-console .sz-dot {
        display: inline-block;
        width: 6px;
        height: 6px;
        border-radius: 9999px;
    }
    #sz-geo-console .sz-dot-done { background: var(--sz-blue); }
    #sz-geo-console .sz-dot-wait { background: #CBD5E1; }
    #sz-geo-console .sz-checkbox {
        accent-color: var(--sz-blue);
    }
    #sz-geo-console .sz-table th,
    #sz-geo-console .sz-table td {
        padding: 12px 14px;
        vertical-align: middle;
    }
    #sz-geo-console .sz-table tbody tr {
        border-bottom: 1px solid var(--sz-border);
        transition: background-color 120ms ease;
    }
    #sz-geo-console .sz-table tbody tr:hover {
        background: var(--sz-subtle);
    }
    #sz-geo-console .sz-flash {
        background: var(--sz-blue-soft);
        border: 1px solid var(--sz-blue-border);
        color: var(--sz-blue-ink);
        border-radius: 10px;
        padding: 12px 16px;
        font-size: 13px;
        line-height: 1.5;
    }
</style>

<div class="space-y-5" id="sz-geo-console">
    {{-- 操作回执提示条 --}}
    @if(session('message'))
        <div class="sz-flash" role="status">{{ session('message') }}</div>
    @endif
    @if($errors->any())
        <div class="sz-flash" style="background: var(--sz-subtle); border-color: var(--sz-border-strong); color: var(--sz-ink);" role="alert">
            {{ $errors->first() }}
        </div>
    @endif

    {{-- 顶部标题与核心汇总 --}}
    <section class="sz-card">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <div class="flex items-center gap-2 text-xs" style="color: var(--sz-ink-3);">
                    <span class="font-mono">000981.SZ</span>
                    <span>·</span>
                    <span>山子高科 GEO 工作台</span>
                </div>
                <div class="sz-title mt-1">合规质检、分发矩阵与被翻牌台账</div>
            </div>
            <div class="flex flex-wrap items-center gap-2">
                <a href="{{ $browserGuiUrl }}" target="_blank" rel="noopener noreferrer" class="sz-btn-blue-outline inline-flex h-9 items-center gap-2 px-3.5 text-xs">
                    <span class="sz-dot {{ $hubOnline ? 'sz-dot-done' : 'sz-dot-wait' }}"></span>
                    <span>云端登录浏览器 ↗</span>
                </a>
                <a href="{{ route('admin.analytics.ai-visibility') }}" class="sz-btn-ghost inline-flex h-9 items-center px-3.5 text-xs">
                    AI 可见性成绩单
                </a>
                <a href="{{ route('admin.distribution.export-ledger') }}" class="sz-btn-primary inline-flex h-9 items-center px-3.5 text-xs">
                    导出 Excel (.csv)
                </a>
            </div>
        </div>

        <div class="sz-kpi-grid">
            <div class="sz-kpi-box">
                <div class="sz-kpi-label">已上线链接</div>
                <div class="sz-kpi-val">{{ $mxSummary['published_count'] }}</div>
            </div>
            <div class="sz-kpi-box">
                <div class="sz-kpi-label">待发外网工单</div>
                <div class="sz-kpi-val">{{ $mxSummary['pending_count'] }}</div>
            </div>
            <div class="sz-kpi-box">
                <div class="sz-kpi-label">AI 翻牌链接 / 引用次数</div>
                <div class="sz-kpi-val is-accent">
                    {{ $mxSummary['cited_urls'] }} <span class="text-xs font-normal" style="color: var(--sz-ink-3);">/ {{ $mxSummary['citation_hits'] }} 次</span>
                </div>
            </div>
            <div class="sz-kpi-box">
                <div class="sz-kpi-label">链接被翻牌率</div>
                <div class="sz-kpi-val is-accent">{{ number_format($mxSummary['citation_rate'], 1) }}%</div>
            </div>
        </div>
    </section>

    {{-- 区块 1：独立拖拽合规质检打分台 + 一键派发 --}}
    <section class="sz-card">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <div class="sz-section-title">文章合规质检与一键派发</div>
                <div class="sz-subtitle">拖入自写稿对照官方知识库（KB#2 + KB#3）评分并查看扣分理由与改写建议，确认后勾选渠道派发。</div>
            </div>
            <div class="sz-seg shrink-0 self-start sm:self-auto">
                <button type="button" id="sz-tab-upload" class="sz-seg-btn is-active">自写稿拖入</button>
                <button type="button" id="sz-tab-existing" class="sz-seg-btn">系统已生成稿</button>
            </div>
        </div>

        <form method="POST" action="{{ route('admin.distribution.quick-dispatch') }}" id="sz-dispatch-form" class="mt-4 space-y-4">
            @csrf
            <input type="hidden" name="mode" id="sz-mode-input" value="upload">

            {{-- 模式 A：拖拽上传 / 粘贴自写文章 --}}
            <div id="sz-panel-upload" class="space-y-3">
                <div id="sz-dropzone" class="sz-dropzone">
                    <input type="file" id="sz-file-input" accept=".md,.txt,.markdown" class="hidden">
                    <div class="text-sm font-medium" style="color: var(--sz-ink);">将 .md 或 .txt 稿件拖入此处，或点击选择本地文件</div>
                    <div class="mt-1 text-xs" style="color: var(--sz-ink-3);">自动读取标题与正文，随时点击下方按钮执行上市公司信披合规质检</div>
                    <div id="sz-file-status" class="mt-2 hidden text-xs font-medium" style="color: var(--sz-blue-ink);"></div>
                </div>

                <div>
                    <input type="text" name="title" id="sz-title-input" placeholder="文章标题（拖入文件自动提取，或直接输入）" class="sz-input w-full px-3.5 py-2 text-sm">
                </div>
                <div>
                    <textarea name="content" id="sz-content-input" rows="6" placeholder="在此粘贴或拖入文章正文（支持 Markdown 或纯文本）" class="sz-input w-full px-3.5 py-2.5 font-mono text-xs leading-relaxed"></textarea>
                </div>

                <div class="flex flex-wrap items-center gap-3">
                    <button type="button" id="sz-inspect-btn" class="sz-btn-primary inline-flex h-9 items-center px-4 text-xs">
                        开始合规质检打分
                    </button>
                    <span id="sz-inspect-hint" class="text-xs" style="color: var(--sz-ink-3);"></span>
                </div>

                {{-- 质检报告输出区 --}}
                <div id="sz-inspect-result" class="hidden sz-inset p-4 space-y-3.5">
                    <div class="flex flex-wrap items-center justify-between gap-2 pb-3" style="border-bottom: 1px solid var(--sz-border);">
                        <div class="flex items-center gap-3">
                            <span id="sz-score-badge" class="font-mono text-2xl font-semibold"></span>
                            <span id="sz-pass-badge" class="sz-tag-slate"></span>
                        </div>
                        <span class="text-xs" style="color: var(--sz-ink-3);">质检依据：Prompt#10 + KB#2 + KB#3（85 分过关）</span>
                    </div>
                    <div>
                        <div class="text-xs font-medium" style="color: var(--sz-ink-2);">综合评语与打分理由</div>
                        <p id="sz-score-summary" class="mt-1 text-sm leading-6" style="color: var(--sz-ink);"></p>
                    </div>
                    <div id="sz-score-dims" class="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4"></div>
                    <div id="sz-score-issues-wrap" class="space-y-2">
                        <div class="text-xs font-medium" style="color: var(--sz-ink-2);">逐条扣分项与修改建议</div>
                        <div id="sz-score-issues" class="space-y-2"></div>
                    </div>
                </div>
            </div>

            {{-- 模式 B：从系统已生成过检文章中选取 --}}
            <div id="sz-panel-existing" class="hidden space-y-2">
                <label class="block text-xs font-medium" style="color: var(--sz-ink-2);">选择一篇系统已生成并通过审核的稿件</label>
                <select name="article_id" id="sz-article-select" class="sz-input w-full px-3.5 py-2 text-sm">
                    <option value="">-- 请选择文章 --</option>
                    @foreach($mx['approved_articles'] as $art)
                        <option value="{{ $art->id }}">#{{ $art->id }} · {{ $art->title }}（{{ substr((string) $art->updated_at, 0, 10) }}）</option>
                    @endforeach
                </select>
            </div>

            {{-- 勾选要派发的平台 --}}
            <div class="sz-inset p-4">
                <div class="flex items-center justify-between gap-2">
                    <span class="text-xs font-medium" style="color: var(--sz-ink-2);">选择派发渠道（官网 1 秒同步上线，外部平台生成待发台账）</span>
                    <button type="button" id="sz-toggle-all-plat" class="whitespace-nowrap text-xs font-medium" style="color: var(--sz-blue-ink);">全选 / 反选</button>
                </div>
                <div class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                    @foreach($mxPlatforms as $p)
                        <label class="flex cursor-pointer items-center gap-2.5 rounded-lg bg-white px-3 py-2 text-xs transition-colors" style="border: 1px solid var(--sz-border);">
                            <input type="checkbox" name="account_ids[]" value="{{ $p['id'] }}" class="sz-plat-chk sz-checkbox h-3.5 w-3.5" @checked($p['is_official'] || in_array($p['platform'], ['toutiao', 'sohu', 'netease'], true))>
                            <span class="font-mono text-[11px]" style="color: var(--sz-ink-3);">{{ $p['code'] }}</span>
                            <span class="truncate font-medium" style="color: var(--sz-ink);">{{ $p['short_name'] }}</span>
                        </label>
                    @endforeach
                </div>
            </div>

            <div class="flex flex-wrap items-center justify-between gap-3">
                <span class="text-xs" style="color: var(--sz-ink-3);">官网 1 秒自动上线；外网渠道将直接驱动云端常驻浏览器执行自动填稿或发布。</span>
                <div class="flex flex-wrap items-center gap-2">
                    <select name="external_action" class="sz-input h-9 px-3 text-xs">
                        <option value="draft">外网模式：云端浏览器自动填入草稿（核对后发布）</option>
                        <option value="publish">外网模式：云端浏览器直接自动提交发布</option>
                        <option value="ledger_only">外网模式：仅记入下方待发台账</option>
                    </select>
                    <button type="submit" id="sz-dispatch-submit" class="sz-btn-primary inline-flex h-9 items-center px-4 text-xs">
                        确认一键派发
                    </button>
                </div>
            </div>
        </form>
    </section>

    {{-- 区块 2：九大发布阵地 --}}
    <section class="sz-card">
        <div class="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
            <div class="sz-section-title">九大发布阵地</div>
            <div class="text-xs" style="color: var(--sz-ink-3);">按豆包与 DeepSeek 抓取权重排序，点击右侧直达各平台创作后台</div>
        </div>

        <div class="sz-plat-grid">
            @foreach($mxPlatforms as $p)
                <div class="sz-plat-card">
                    <div>
                        <div class="flex items-center justify-between gap-2">
                            <span class="font-mono text-[11px]" style="color: var(--sz-ink-3);">{{ $p['code'] }}</span>
                            <span class="{{ $p['badge'] }}">{{ $p['ai_target'] }}</span>
                        </div>
                        <div class="mt-2.5 text-sm font-semibold" style="color: var(--sz-ink);">{{ $p['short_name'] }}</div>
                        <p class="mt-1 line-clamp-2 text-xs leading-5" style="color: var(--sz-ink-2);">{{ $p['summary'] }}</p>
                    </div>
                    <div class="mt-4 flex items-center justify-between pt-3 text-xs" style="border-top: 1px solid var(--sz-border);">
                        <div class="flex items-center gap-3 font-mono text-[11px]" style="color: var(--sz-ink-3);">
                            <span>已发 <strong style="color: var(--sz-ink);">{{ $p['published_count'] }}</strong></span>
                            <span>待发 <strong style="color: var(--sz-ink-2);">{{ $p['pending_count'] }}</strong></span>
                            <span>翻牌 <strong style="color: var(--sz-blue-ink);">{{ $p['citation_count'] }}</strong></span>
                        </div>
                        <a href="{{ $p['editor_url'] }}" target="_blank" rel="noopener noreferrer" class="whitespace-nowrap font-medium hover:underline" style="color: var(--sz-blue-ink);">
                            进入后台 ↗
                        </a>
                    </div>
                </div>
            @endforeach
        </div>
    </section>

    {{-- 区块 3：Excel 风格全平台发稿链接 & AI 被翻牌率总表 --}}
    <section class="sz-card">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <div class="sz-section-title">全平台发稿与被翻牌台账</div>
                <div class="sz-subtitle">待发记录可直接复制标题或正文去外网发布，发布后粘贴真实网址保存，即纳入被翻牌率统计。</div>
            </div>
            <div class="flex flex-wrap items-center gap-2">
                <select id="sz-filter-platform" class="sz-input h-8 px-2.5 text-xs">
                    <option value="">全部平台 ({{ count($mxLedger) }})</option>
                    @foreach($mxPlatforms as $p)
                        <option value="{{ $p['short_name'] }}">{{ $p['code'] }} {{ $p['short_name'] }}</option>
                    @endforeach
                </select>
                <select id="sz-filter-status" class="sz-input h-8 px-2.5 text-xs">
                    <option value="">全部状态</option>
                    <option value="completed">已上线</option>
                    <option value="pending">待发 / 处理中</option>
                </select>
            </div>
        </div>

        <div class="mt-4 overflow-x-auto rounded-lg" style="border: 1px solid var(--sz-border);">
            <table class="sz-table min-w-full text-left text-xs" id="sz-excel-table" style="border-collapse: collapse;">
                <thead style="background: var(--sz-subtle); border-bottom: 1px solid var(--sz-border); color: var(--sz-ink-3);">
                    <tr>
                        <th class="font-medium">#</th>
                        <th class="font-medium">发布平台</th>
                        <th class="font-medium">文章标题与快捷复制</th>
                        <th class="font-medium">状态</th>
                        <th class="font-medium">线上真实链接（回填追踪）</th>
                        <th class="text-center font-medium">被翻牌</th>
                        <th class="font-medium">更新日期</th>
                    </tr>
                </thead>
                <tbody style="background: var(--sz-surface);">
                    @forelse($mxLedger as $idx => $row)
                        @php($isDone = $row['status'] === 'completed')
                        <tr class="sz-ledger-row" data-platform="{{ $row['platform_label'] }}" data-status="{{ $isDone ? 'completed' : 'pending' }}">
                            <td class="font-mono" style="color: var(--sz-ink-3);">{{ $idx + 1 }}</td>
                            <td class="whitespace-nowrap">
                                <span class="{{ $row['badge'] }}">{{ $row['platform_label'] }}</span>
                            </td>
                            <td class="max-w-sm">
                                <div class="font-medium leading-5" style="color: var(--sz-ink);">{{ $row['title'] }}</div>
                                @if($row['content'] !== '')
                                    <div class="mt-1.5 flex flex-wrap items-center gap-1.5">
                                        <button type="button" class="sz-copy-btn sz-btn-ghost px-2 py-0.5 text-[11px]" data-copy="{{ $row['title'] }}">复制标题</button>
                                        <button type="button" class="sz-copy-btn sz-btn-ghost px-2 py-0.5 text-[11px]" data-copy="{{ $row['content'] }}">复制正文</button>
                                        @if(!$isDone && !empty($row['article_id']) && !empty($row['account_id']))
                                            <form method="POST" action="{{ route('admin.distribution.quick-dispatch') }}" class="inline">
                                                @csrf
                                                <input type="hidden" name="mode" value="existing">
                                                <input type="hidden" name="article_id" value="{{ $row['article_id'] }}">
                                                <input type="hidden" name="account_ids[]" value="{{ $row['account_id'] }}">
                                                <input type="hidden" name="external_action" value="draft">
                                                <button type="submit" class="sz-btn-blue-outline px-2 py-0.5 text-[11px]">云端填稿</button>
                                            </form>
                                            <form method="POST" action="{{ route('admin.distribution.quick-dispatch') }}" class="inline">
                                                @csrf
                                                <input type="hidden" name="mode" value="existing">
                                                <input type="hidden" name="article_id" value="{{ $row['article_id'] }}">
                                                <input type="hidden" name="account_ids[]" value="{{ $row['account_id'] }}">
                                                <input type="hidden" name="external_action" value="publish">
                                                <button type="submit" class="sz-btn-primary px-2 py-0.5 text-[11px]">云端直发</button>
                                            </form>
                                        @endif
                                        @if(!$isDone && $row['editor_url'] !== '#')
                                            <a href="{{ $row['editor_url'] }}" target="_blank" rel="noopener noreferrer" class="px-1.5 py-0.5 text-[11px] font-medium hover:underline" style="color: var(--sz-blue-ink);">去发文 ↗</a>
                                        @endif
                                    </div>
                                @endif
                            </td>
                            <td class="whitespace-nowrap">
                                <span class="inline-flex items-center gap-1.5 text-xs" style="color: {{ $isDone ? 'var(--sz-ink)' : 'var(--sz-ink-3)' }};">
                                    <span class="sz-dot {{ $isDone ? 'sz-dot-done' : 'sz-dot-wait' }}"></span>
                                    {{ $isDone ? '已上线' : '待发布' }}
                                </span>
                            </td>
                            <td style="min-width: 260px;">
                                @if($row['manual_publication_id'])
                                    <form method="POST" action="{{ route('admin.distribution.quick-receipt') }}" class="flex items-center gap-1.5">
                                        @csrf
                                        <input type="hidden" name="manual_publication_id" value="{{ $row['manual_publication_id'] }}">
                                        <input type="url" name="completion_url" value="{{ $row['url'] }}" placeholder="发完后粘贴真实链接 https://..." class="sz-input w-full px-2.5 py-1 text-xs">
                                        <button type="submit" class="sz-btn-ghost shrink-0 px-2.5 py-1 text-xs">保存</button>
                                    </form>
                                    @if($row['url'] !== '')
                                        <a href="{{ $row['url'] }}" target="_blank" rel="noopener noreferrer" class="mt-1 block truncate text-[11px] hover:underline" style="color: var(--sz-blue-ink);">{{ $row['url'] }}</a>
                                    @endif
                                @elseif($row['url'] !== '')
                                    <a href="{{ $row['url'] }}" target="_blank" rel="noopener noreferrer" class="block max-w-xs truncate font-mono text-[11px] hover:underline" style="color: var(--sz-blue-ink);">{{ $row['url'] }}</a>
                                @else
                                    <span style="color: var(--sz-ink-3);">—</span>
                                @endif
                            </td>
                            <td class="text-center font-mono">
                                @if($row['citations'] > 0)
                                    <span class="sz-tag-blue">{{ $row['citations'] }} 次</span>
                                @else
                                    <span style="color: var(--sz-ink-3);">0</span>
                                @endif
                            </td>
                            <td class="whitespace-nowrap font-mono text-[11px]" style="color: var(--sz-ink-3);">{{ $row['updated_at'] }}</td>
                        </tr>
                    @empty
                        <tr>
                            <td colspan="7" class="py-8 text-center text-xs" style="color: var(--sz-ink-3);">暂无记录，请在上方拖入文章一键派发。</td>
                        </tr>
                    @endforelse
                </tbody>
            </table>
        </div>
    </section>

    {{-- 区块 4：可视化资产库与产品库 --}}
    <section class="sz-card">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <div class="sz-section-title">资产库与产品库</div>
                <div class="sz-subtitle">可视化查看并手动增删标题、关键词与官方事实知识库；新增关键词将同步进入 AI 可见性监控词表。</div>
            </div>
            <div class="sz-seg shrink-0 self-start sm:self-auto">
                <button type="button" class="sz-asset-tab sz-seg-btn is-active" data-target="sz-asset-titles">标题库 ({{ $totalTitles }})</button>
                <button type="button" class="sz-asset-tab sz-seg-btn" data-target="sz-asset-keywords">关键词库 ({{ $totalKeywords }})</button>
                <button type="button" class="sz-asset-tab sz-seg-btn" data-target="sz-asset-kb">知识库 ({{ count($mx['knowledge_bases']) }})</button>
            </div>
        </div>

        {{-- 标题库视图 --}}
        <div id="sz-asset-titles" class="sz-asset-panel mt-4 space-y-4">
            <form method="POST" action="{{ route('admin.distribution.assets.title.save') }}" class="sz-inset flex flex-wrap items-center gap-2 p-3 text-xs">
                @csrf
                <select name="library_id" required class="sz-input h-8 px-2.5 text-xs">
                    @foreach($mx['title_libraries'] as $tl)
                        <option value="{{ $tl->id }}">{{ $tl->name }}</option>
                    @endforeach
                </select>
                <input type="text" name="title" required placeholder="输入新标题（例如：山子高科邦奇动力 DT2 混动变速箱量产进展）" class="sz-input h-8 flex-1 px-3 text-xs" style="min-width: 240px;">
                <button type="submit" class="sz-btn-primary h-8 px-3.5 text-xs">新增标题 +</button>
            </form>

            <div class="grid grid-cols-1 gap-3 lg:grid-cols-3">
                @foreach($mx['title_libraries'] as $tl)
                    @php($items = $mx['titles_by_lib']->get($tl->id, collect()))
                    <div class="sz-inset flex flex-col p-4">
                        <div class="flex items-center justify-between gap-2 pb-2.5" style="border-bottom: 1px solid var(--sz-border);">
                            <div class="text-xs font-semibold" style="color: var(--sz-ink);">{{ $tl->name }}</div>
                            <span class="font-mono text-[11px]" style="color: var(--sz-ink-3);">{{ $items->count() }}</span>
                        </div>
                        <ul class="mt-2.5 max-h-64 space-y-1.5 overflow-y-auto pr-1 text-xs">
                            @foreach($items as $ti)
                                <li class="flex items-start justify-between gap-2 rounded-md bg-white px-2.5 py-1.5" style="border: 1px solid var(--sz-border);">
                                    <span class="leading-5" style="color: var(--sz-ink);">{{ $ti->title }}</span>
                                    <form method="POST" action="{{ route('admin.distribution.assets.title.delete') }}" onsubmit="return confirm('确定删除该标题？')">
                                        @csrf
                                        <input type="hidden" name="id" value="{{ $ti->id }}">
                                        <button type="submit" class="shrink-0 px-1 text-sm leading-none hover:opacity-70" style="color: var(--sz-ink-3);" title="删除">×</button>
                                    </form>
                                </li>
                            @endforeach
                        </ul>
                    </div>
                @endforeach
            </div>
        </div>

        {{-- 关键词库视图 --}}
        <div id="sz-asset-keywords" class="sz-asset-panel mt-4 hidden space-y-4">
            <form method="POST" action="{{ route('admin.distribution.assets.keyword.save') }}" class="sz-inset flex flex-wrap items-center gap-2 p-3 text-xs">
                @csrf
                <select name="library_id" required class="sz-input h-8 px-2.5 text-xs">
                    @foreach($mx['keyword_libraries'] as $kl)
                        <option value="{{ $kl->id }}">{{ $kl->name }}</option>
                    @endforeach
                </select>
                <input type="text" name="keyword" required placeholder="输入新关键词（支持中文逗号或换行一次批量添加多个）" class="sz-input h-8 flex-1 px-3 text-xs" style="min-width: 240px;">
                <button type="submit" class="sz-btn-primary h-8 px-3.5 text-xs">新增并同步监控 +</button>
            </form>

            <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                @foreach($mx['keyword_libraries'] as $kl)
                    @php($items = $mx['keywords_by_lib']->get($kl->id, collect()))
                    <div class="sz-inset p-4">
                        <div class="flex items-center justify-between gap-2 pb-2.5" style="border-bottom: 1px solid var(--sz-border);">
                            <div class="text-xs font-semibold" style="color: var(--sz-ink);">{{ $kl->name }}</div>
                            <span class="font-mono text-[11px]" style="color: var(--sz-ink-3);">{{ $items->count() }} 词</span>
                        </div>
                        <div class="mt-3 flex flex-wrap gap-1.5">
                            @foreach($items as $ki)
                                <span class="inline-flex items-center gap-1 rounded-md bg-white px-2.5 py-1 text-xs" style="border: 1px solid var(--sz-border); color: var(--sz-ink);">
                                    <span>{{ $ki->keyword }}</span>
                                    <form method="POST" action="{{ route('admin.distribution.assets.keyword.delete') }}" class="inline" onsubmit="return confirm('确定删除关键词「{{ $ki->keyword }}」？')">
                                        @csrf
                                        <input type="hidden" name="id" value="{{ $ki->id }}">
                                        <button type="submit" class="ml-0.5 leading-none hover:opacity-70" style="color: var(--sz-ink-3);" title="删除">×</button>
                                    </form>
                                </span>
                            @endforeach
                        </div>
                    </div>
                @endforeach
            </div>
        </div>

        {{-- 知识库视图 --}}
        <div id="sz-asset-kb" class="sz-asset-panel mt-4 hidden space-y-3">
            @foreach($mx['knowledge_bases'] as $kb)
                <details class="sz-inset p-4">
                    <summary class="flex cursor-pointer items-center justify-between text-xs font-semibold" style="color: var(--sz-ink);">
                        <span>KB#{{ $kb->id }} · {{ $kb->name }}</span>
                        <span class="font-mono font-normal" style="color: var(--sz-ink-3);">{{ mb_strlen((string) $kb->content) }} 字 · 更新于 {{ substr((string) $kb->updated_at, 0, 10) }}</span>
                    </summary>
                    <pre class="mt-3 max-h-72 overflow-y-auto whitespace-pre-wrap rounded-md bg-white p-3.5 text-xs leading-6" style="border: 1px solid var(--sz-border); color: var(--sz-ink-2);">{{ $kb->content }}</pre>
                </details>
            @endforeach
        </div>
    </section>
</div>

<script>
(() => {
    // 1. Copy helper with HTTP fallback (works on non-HTTPS internal hosts)
    function copyText(text, btn) {
        const done = () => {
            const orig = btn.textContent;
            btn.textContent = '已复制';
            setTimeout(() => { btn.textContent = orig; }, 1400);
        };
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
        } else {
            fallbackCopy(text, done);
        }
    }
    function fallbackCopy(text, cb) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        try { document.execCommand('copy'); } catch (e) {}
        document.body.removeChild(ta);
        cb();
    }
    document.querySelectorAll('.sz-copy-btn').forEach(btn => {
        btn.addEventListener('click', () => copyText(btn.dataset.copy || '', btn));
    });

    // 2. Upload vs Existing tabs
    const tabUpload = document.getElementById('sz-tab-upload');
    const tabExisting = document.getElementById('sz-tab-existing');
    const panelUpload = document.getElementById('sz-panel-upload');
    const panelExisting = document.getElementById('sz-panel-existing');
    const modeInput = document.getElementById('sz-mode-input');

    function setMode(m) {
        modeInput.value = m;
        if (m === 'upload') {
            panelUpload.classList.remove('hidden');
            panelExisting.classList.add('hidden');
            tabUpload.classList.add('is-active');
            tabExisting.classList.remove('is-active');
        } else {
            panelUpload.classList.add('hidden');
            panelExisting.classList.remove('hidden');
            tabExisting.classList.add('is-active');
            tabUpload.classList.remove('is-active');
        }
    }
    tabUpload?.addEventListener('click', () => setMode('upload'));
    tabExisting?.addEventListener('click', () => setMode('existing'));

    // 3. Drag & Drop file reader (.md / .txt)
    const dropzone = document.getElementById('sz-dropzone');
    const fileInput = document.getElementById('sz-file-input');
    const titleInput = document.getElementById('sz-title-input');
    const contentInput = document.getElementById('sz-content-input');
    const fileStatus = document.getElementById('sz-file-status');

    function loadFile(file) {
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
            const text = String(reader.result || '');
            contentInput.value = text;
            const lines = text.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
            let title = file.name.replace(/\.(md|txt|markdown)$/i, '');
            if (lines.length && lines[0].startsWith('#')) {
                title = lines[0].replace(/^#+\s*/, '');
            } else if (lines.length && lines[0].length <= 60) {
                title = lines[0];
            }
            if (!titleInput.value.trim()) titleInput.value = title;
            fileStatus.textContent = `已加载：${file.name}（${text.length} 字）`;
            fileStatus.classList.remove('hidden');
        };
        reader.readAsText(file, 'utf-8');
    }
    dropzone?.addEventListener('click', () => fileInput?.click());
    fileInput?.addEventListener('change', e => loadFile(e.target.files?.[0]));
    dropzone?.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('is-dragover'); });
    dropzone?.addEventListener('dragleave', () => { dropzone.classList.remove('is-dragover'); });
    dropzone?.addEventListener('drop', e => {
        e.preventDefault();
        dropzone.classList.remove('is-dragover');
        loadFile(e.dataTransfer?.files?.[0]);
    });

    // 4. Synchronous AI Quality Inspection (with detailed reasons & rewrite suggestions)
    const inspectBtn = document.getElementById('sz-inspect-btn');
    const inspectHint = document.getElementById('sz-inspect-hint');
    const inspectResult = document.getElementById('sz-inspect-result');

    inspectBtn?.addEventListener('click', async () => {
        const title = (titleInput?.value || '').trim();
        const content = (contentInput?.value || '').trim();
        if (title.length < 2 || content.length < 20) {
            inspectHint.textContent = '请先拖入文件或填写标题与正文（至少 20 字）。';
            return;
        }
        inspectBtn.disabled = true;
        inspectHint.textContent = '正在对照山子高科官方知识库执行合规评审，预计需要 10–25 秒...';
        try {
            const resp = await fetch('{{ route("admin.distribution.quick-inspect") }}', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]')?.content || '{{ csrf_token() }}'
                },
                body: JSON.stringify({ title, content })
            });
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                inspectHint.textContent = data.error || '质检失败，请稍后重试。';
                return;
            }
            inspectHint.textContent = '质检完成。';
            inspectResult.classList.remove('hidden');
            const scoreBadge = document.getElementById('sz-score-badge');
            const passBadge = document.getElementById('sz-pass-badge');
            scoreBadge.textContent = `${data.score} / 100`;
            scoreBadge.style.color = data.passed ? 'var(--sz-blue-ink)' : 'var(--sz-ink)';
            passBadge.textContent = data.passed ? '通过（可直接派发）' : '未达 85 分（建议修改后发布）';
            passBadge.className = data.passed ? 'sz-tag-blue' : 'sz-tag-slate';
            document.getElementById('sz-score-summary').textContent = data.summary || '';

            const dimsEl = document.getElementById('sz-score-dims');
            dimsEl.innerHTML = '';
            (data.dimensions || []).forEach(d => {
                const div = document.createElement('div');
                div.className = 'rounded-lg bg-white p-3 text-xs';
                div.style.border = '1px solid var(--sz-border)';
                div.innerHTML = `<div class="flex items-center justify-between font-medium" style="color: var(--sz-ink);"><span>${escapeHtml(d.name || '')}</span><span class="font-mono" style="color: var(--sz-blue-ink);">${escapeHtml(String(d.score ?? ''))}</span></div><p class="mt-1.5 leading-5" style="color: var(--sz-ink-2);">${escapeHtml(d.comment || '')}</p>`;
                dimsEl.appendChild(div);
            });

            const issuesEl = document.getElementById('sz-score-issues');
            issuesEl.innerHTML = '';
            const issues = data.issues || [];
            if (!issues.length) {
                issuesEl.innerHTML = '<div class="rounded-lg bg-white p-3 text-xs" style="border: 1px solid var(--sz-border); color: var(--sz-ink-2);">未发现合规红线或事实偏差，可直接派发。</div>';
            } else {
                const sevMap = { high: '高危红线', medium: '需补充口径', low: '优化建议' };
                issues.forEach(it => {
                    const sev = String(it.severity || 'medium').toLowerCase();
                    const tagCls = sev === 'high' ? 'sz-tag-blue' : 'sz-tag-slate';
                    const card = document.createElement('div');
                    card.className = 'rounded-lg bg-white p-3 text-xs space-y-1.5';
                    card.style.border = '1px solid var(--sz-border)';
                    card.innerHTML = `
                        <div class="flex items-center justify-between gap-2">
                            <span class="font-medium" style="color: var(--sz-ink);">${escapeHtml(it.title || '扣分项')}</span>
                            <span class="${tagCls}">${sevMap[sev] || '建议'}</span>
                        </div>
                        ${it.quote ? `<div class="rounded px-2.5 py-1.5 font-mono text-[11px]" style="background: var(--sz-subtle); color: var(--sz-ink-2);">原文：${escapeHtml(it.quote)}</div>` : ''}
                        <div style="color: var(--sz-ink-2);"><span style="color: var(--sz-ink);">扣分理由：</span>${escapeHtml(it.reason || '')}</div>
                        <div style="color: var(--sz-blue-ink);"><span>修改建议：</span>${escapeHtml(it.suggestion || '')}</div>
                    `;
                    issuesEl.appendChild(card);
                });
            }
        } catch (err) {
            inspectHint.textContent = '网络或超时异常：' + (err?.message || err);
        } finally {
            inspectBtn.disabled = false;
        }
    });

    function escapeHtml(s) {
        return s.replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
    }

    // 5. Select/Deselect all platforms
    document.getElementById('sz-toggle-all-plat')?.addEventListener('click', () => {
        const chks = Array.from(document.querySelectorAll('.sz-plat-chk'));
        const allChecked = chks.every(c => c.checked);
        chks.forEach(c => { c.checked = !allChecked; });
    });

    // 6. Client-side pre-submit guard for quickDispatch
    document.getElementById('sz-dispatch-form')?.addEventListener('submit', e => {
        const checked = document.querySelectorAll('.sz-plat-chk:checked').length;
        if (!checked) {
            e.preventDefault();
            alert('请至少勾选一个派发渠道。');
            return;
        }
        if (modeInput.value === 'upload') {
            if (!(titleInput?.value || '').trim() || !(contentInput?.value || '').trim()) {
                e.preventDefault();
                alert('请先拖入文件或填写文章标题与正文。');
                return;
            }
        } else {
            const artSel = document.getElementById('sz-article-select');
            if (!(artSel?.value || '').trim()) {
                e.preventDefault();
                alert('请先选择一篇系统已生成的文章。');
                return;
            }
        }
        const btn = document.getElementById('sz-dispatch-submit');
        if (btn) {
            btn.disabled = true;
            btn.textContent = '派发中...';
        }
    });

    // 7. Ledger filters
    const filterPlat = document.getElementById('sz-filter-platform');
    const filterStatus = document.getElementById('sz-filter-status');
    function applyFilters() {
        const fp = filterPlat?.value || '';
        const fs = filterStatus?.value || '';
        document.querySelectorAll('.sz-ledger-row').forEach(tr => {
            const okP = !fp || tr.dataset.platform === fp;
            const okS = !fs || tr.dataset.status === fs;
            tr.classList.toggle('hidden', !(okP && okS));
        });
    }
    filterPlat?.addEventListener('change', applyFilters);
    filterStatus?.addEventListener('change', applyFilters);

    // 8. Asset Library tabs
    const assetTabs = document.querySelectorAll('.sz-asset-tab');
    const assetPanels = document.querySelectorAll('.sz-asset-panel');
    assetTabs.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.target;
            assetTabs.forEach(b => b.classList.remove('is-active'));
            btn.classList.add('is-active');
            assetPanels.forEach(p => p.classList.toggle('hidden', p.id !== target));
        });
    });
})();
</script>
