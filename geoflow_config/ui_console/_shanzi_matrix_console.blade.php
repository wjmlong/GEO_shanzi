@php
    $mx = \App\Http\Controllers\Admin\GeoMatrixController::matrixData();
    $mxSummary = $mx['summary'];
    $mxPlatforms = $mx['platforms'];
    $mxLedger = $mx['ledger'];
@endphp

<div class="space-y-6" id="sz-geo-console">
    {{-- 顶部标题与核心汇总 --}}
    <section class="rounded-xl border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
                <h1 class="text-xl font-bold text-gray-950">山子高科（000981.SZ）GEO 一站式质检、分发与被翻牌追踪台</h1>
                <p class="mt-1 text-sm text-gray-500">拖入自己写的稿件先做合规打分（含详细理由与改写建议）→ 勾选平台 1 秒发官网 / 生成矩阵工单 → Excel 总表追踪每条链接的 AI 被翻牌次数。</p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
                <a href="{{ route('admin.distribution.export-ledger') }}" class="inline-flex min-h-10 items-center gap-2 rounded-lg bg-emerald-600 px-4 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700">
                    <span>📥 导出 Excel 总表 (.csv)</span>
                </a>
                <a href="{{ route('admin.analytics.ai-visibility') }}" class="inline-flex min-h-10 items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-4 text-sm font-semibold text-violet-700 hover:bg-violet-100">
                    <span>📊 AI 可见性成绩单</span>
                </a>
            </div>
        </div>

        <div class="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-3.5">
                <div class="text-xs text-gray-500">全平台已上线链接</div>
                <div class="mt-1 font-mono text-2xl font-bold text-gray-950">{{ $mxSummary['published_count'] }}</div>
            </div>
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-3.5">
                <div class="text-xs text-gray-500">待发外部平台工单</div>
                <div class="mt-1 font-mono text-2xl font-bold text-amber-600">{{ $mxSummary['pending_count'] }}</div>
            </div>
            <div class="rounded-lg border border-indigo-100 bg-indigo-50/50 p-3.5">
                <div class="text-xs text-indigo-700">被 AI 翻牌链接数 / 总引用</div>
                <div class="mt-1 font-mono text-2xl font-bold text-indigo-700">{{ $mxSummary['cited_urls'] }} <span class="text-sm font-normal text-indigo-500">/ {{ $mxSummary['citation_hits'] }}次</span></div>
            </div>
            <div class="rounded-lg border border-emerald-100 bg-emerald-50/50 p-3.5">
                <div class="text-xs text-emerald-700">当前链接被翻牌率</div>
                <div class="mt-1 font-mono text-2xl font-bold text-emerald-700">{{ number_format($mxSummary['citation_rate'], 1) }}%</div>
            </div>
        </div>
    </section>

    {{-- 区块 1：独立拖拽合规质检打分台 + 一键派发 --}}
    <section class="rounded-xl border border-blue-200 bg-white p-5 shadow-sm sm:p-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <h2 class="text-lg font-bold text-gray-950">🛡️ 拖拽文章合规质检打分 & 一键派发</h2>
                <p class="mt-0.5 text-xs text-gray-500">把你自己写的 `.md` / `.txt` 稿件直接拖进来，先对照山子高科官方知识库（KB#2+KB#3）打分看扣分理由与改写建议，满意后再勾选平台一键发走。</p>
            </div>
            <div class="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1 text-xs font-semibold">
                <button type="button" id="sz-tab-upload" class="rounded-md bg-white px-3 py-1.5 text-blue-700 shadow-sm">📥 拖入/粘贴自写稿</button>
                <button type="button" id="sz-tab-existing" class="rounded-md px-3 py-1.5 text-gray-600 hover:text-gray-900">📚 选系统已写好稿</button>
            </div>
        </div>

        <form method="POST" action="{{ route('admin.distribution.quick-dispatch') }}" id="sz-dispatch-form" class="mt-4 space-y-4">
            @csrf
            <input type="hidden" name="mode" id="sz-dispatch-mode" value="upload">

            {{-- 模式 A：拖拽上传 / 粘贴自写文章 --}}
            <div id="sz-panel-upload" class="space-y-3">
                <div id="sz-dropzone" class="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-blue-300 bg-blue-50/40 px-4 py-6 text-center transition hover:border-blue-500 hover:bg-blue-50">
                    <div class="text-sm font-semibold text-blue-800">把你的 `.md` 或 `.txt` 文章拖到这里（或点击选择文件）</div>
                    <div class="mt-1 text-xs text-blue-600/80" id="sz-dropzone-hint">自动提取标题与正文，随时可以点「🛡️ 立即合规打分」看详细评分理由</div>
                    <input type="file" id="sz-file-input" accept=".md,.txt,.markdown" class="hidden">
                </div>

                <div class="grid grid-cols-1 gap-3">
                    <input type="text" name="title" id="sz-input-title" placeholder="文章标题（拖入文件会自动提取，也可直接粘贴）" class="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm font-medium focus:border-blue-500 focus:ring-2 focus:ring-blue-200">
                    <textarea name="content" id="sz-input-content" rows="6" placeholder="在这里粘贴或拖入你的文章正文（支持 Markdown 或纯文本）……" class="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm leading-6 focus:border-blue-500 focus:ring-2 focus:ring-blue-200"></textarea>
                </div>

                <div class="flex flex-wrap items-center gap-3">
                    <button type="button" id="sz-btn-inspect" class="inline-flex min-h-10 items-center gap-2 rounded-lg bg-emerald-600 px-4 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50">
                        <span>🛡️ 立即合规质检打分（看打分理由与修改建议）</span>
                    </button>
                    <span id="sz-inspect-status" class="text-xs text-gray-500"></span>
                </div>

                {{-- 实时质检打分报告展示区 --}}
                <div id="sz-inspect-result" class="hidden rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-4">
                    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 pb-3">
                        <div class="flex items-center gap-3">
                            <span id="sz-score-badge" class="inline-flex items-center rounded-full px-3.5 py-1 font-mono text-lg font-bold"></span>
                            <span id="sz-pass-label" class="text-sm font-semibold"></span>
                        </div>
                        <span class="text-xs text-gray-400">依据：山子高科 KB#2 官方披露库 + KB#3 业务品牌库 + Prompt#10 合规安检门</span>
                    </div>
                    <div>
                        <div class="text-xs font-semibold uppercase tracking-wider text-gray-500">总评与打分理由</div>
                        <p id="sz-score-summary" class="mt-1 text-sm leading-6 text-gray-800"></p>
                    </div>
                    <div id="sz-score-dims" class="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4"></div>
                    <div id="sz-score-issues-wrap" class="hidden">
                        <div class="text-xs font-semibold uppercase tracking-wider text-rose-600">逐条扣分明细与改写建议</div>
                        <div id="sz-score-issues" class="mt-2 space-y-2"></div>
                    </div>
                </div>
            </div>

            {{-- 模式 B：选择系统已有过检文章 --}}
            <div id="sz-panel-existing" class="hidden">
                <label class="block text-xs font-semibold text-gray-600 mb-1.5">选择系统已通过质检的成品稿件</label>
                <select name="article_id" id="sz-select-article" class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm">
                    @foreach ($mx['approved_articles'] as $art)
                        <option value="{{ $art->id }}">#{{ $art->id }} · {{ $art->title }}（{{ $art->status === 'published' ? '已发官网' : '待派发' }}）</option>
                    @endforeach
                </select>
            </div>

            {{-- 勾选要派发的 9 个平台 --}}
            <div class="rounded-lg border border-gray-200 bg-gray-50/70 p-4">
                <div class="mb-2.5 flex items-center justify-between">
                    <span class="text-xs font-semibold text-gray-700">勾选本次要派发的平台（① 官网 1 秒自动上线，②～⑨ 自动生成下方 Excel 待发清单）：</span>
                    <button type="button" id="sz-check-all" class="text-xs font-semibold text-blue-600 hover:underline">全选 / 反选</button>
                </div>
                <div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
                    @foreach ($mxPlatforms as $pl)
                        <label class="flex cursor-pointer items-start gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs hover:border-blue-300">
                            <input type="checkbox" name="account_ids[]" value="{{ $pl['id'] }}" @checked($pl['is_official'] || str_contains($pl['name'], '今日头条') || str_contains($pl['name'], '搜狐号')) class="sz-plat-cb mt-0.5 rounded border-gray-300 text-blue-600">
                            <span class="min-w-0">
                                <span class="block truncate font-semibold text-gray-900">{{ $pl['name'] }}</span>
                                <span class="mt-0.5 inline-block text-[11px] text-gray-500">{{ $pl['ai_target'] }}</span>
                            </span>
                        </label>
                    @endforeach
                </div>
                <div class="mt-4 flex justify-end">
                    <button type="submit" class="inline-flex min-h-10 items-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700">
                        <span>🚀 立即派发到已勾选平台</span>
                    </button>
                </div>
            </div>
        </form>
    </section>

    {{-- 区块 2：9 大发布平台矩阵卡片 --}}
    <section class="rounded-xl border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
        <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
                <h2 class="text-lg font-bold text-gray-950">🎯 山子高科 9 大发布阵地矩阵</h2>
                <p class="mt-0.5 text-xs text-gray-500">按对豆包 / DeepSeek 的真实抓权优先级 ①～⑨ 排列；点「打开创作后台」直达各平台发文编辑器（在右侧内置浏览器登一次即可持久保留 Cookie）。</p>
            </div>
        </div>
        <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
            @foreach ($mxPlatforms as $pl)
                <div class="flex flex-col justify-between rounded-xl border border-gray-200 bg-white p-4 transition hover:border-blue-300 hover:shadow-sm">
                    <div>
                        <div class="flex items-start justify-between gap-2">
                            <div class="text-sm font-bold text-gray-950">{{ $pl['name'] }}</div>
                            <span class="shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-semibold {{ $pl['badge'] }}">{{ $pl['ai_target'] }}</span>
                        </div>
                        <p class="mt-2 line-clamp-2 text-xs leading-5 text-gray-500">{{ $pl['notes'] }}</p>
                    </div>
                    <div class="mt-3 flex items-center justify-between border-t border-gray-100 pt-3 text-xs">
                        <div class="flex items-center gap-3 font-mono">
                            <span class="text-emerald-700">已发 <b>{{ $pl['published_count'] }}</b></span>
                            <span class="text-amber-600">待发 <b>{{ $pl['pending_count'] }}</b></span>
                            <span class="text-indigo-700">翻牌 <b>{{ $pl['citation_count'] }}</b></span>
                        </div>
                        <a href="{{ $pl['editor_url'] }}" target="_blank" rel="noopener" class="font-semibold text-blue-600 hover:text-blue-800">打开后台 ↗</a>
                    </div>
                </div>
            @endforeach
        </div>
    </section>

    {{-- 区块 3：Excel 风格全平台发稿与被翻牌率追踪总表 --}}
    <section class="rounded-xl border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <h2 class="text-lg font-bold text-gray-950">📊 全平台发稿链接 & AI 被翻牌率总表（Excel 视图）</h2>
                <p class="mt-0.5 text-xs text-gray-500">每条发出去的链接都在这里留底；待发布行可直接「📋复制标题 / 📄复制正文 → 打开后台发帖 → 粘贴上线网址点保存」，系统自动统计豆包/DeepSeek 翻牌次数。</p>
            </div>
            <div class="flex flex-wrap items-center gap-2 text-xs">
                <select id="sz-filter-platform" class="rounded-lg border border-gray-300 bg-white px-2.5 py-2">
                    <option value="">全部平台 ({{ count($mxLedger) }})</option>
                    @foreach ($mxPlatforms as $pl)
                        <option value="{{ $pl['name'] }}">{{ $pl['name'] }}</option>
                    @endforeach
                </select>
                <select id="sz-filter-status" class="rounded-lg border border-gray-300 bg-white px-2.5 py-2">
                    <option value="">全部状态</option>
                    <option value="completed">🟢 已上线</option>
                    <option value="ready">🟡 待发布</option>
                </select>
            </div>
        </div>

        <div class="mt-4 overflow-x-auto rounded-lg border border-gray-200">
            <table class="min-w-full divide-y divide-gray-200 text-left text-xs" id="sz-excel-table">
                <thead class="bg-gray-50 font-semibold text-gray-600">
                    <tr>
                        <th class="px-3 py-2.5">#</th>
                        <th class="px-3 py-2.5">发布平台</th>
                        <th class="px-3 py-2.5">文章标题</th>
                        <th class="px-3 py-2.5">状态</th>
                        <th class="px-3 py-2.5">线上真实链接（可粘贴登记）</th>
                        <th class="px-3 py-2.5 text-center">AI 被翻牌</th>
                        <th class="px-3 py-2.5 text-right">快捷操作</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100 bg-white">
                    @foreach ($mxLedger as $idx => $row)
                        <tr class="sz-ledger-row hover:bg-blue-50/30" data-platform="{{ $row['platform_label'] }}" data-status="{{ $row['status'] === 'completed' ? 'completed' : 'ready' }}">
                            <td class="px-3 py-2.5 font-mono text-gray-400">{{ $idx + 1 }}</td>
                            <td class="px-3 py-2.5 whitespace-nowrap">
                                <span class="inline-flex rounded-md border px-2 py-0.5 font-semibold {{ $row['badge'] }}">{{ $row['platform_label'] }}</span>
                            </td>
                            <td class="px-3 py-2.5 max-w-xs">
                                <div class="font-medium text-gray-900 line-clamp-2" title="{{ $row['title'] }}">{{ $row['title'] }}</div>
                                <div class="mt-0.5 text-[11px] text-gray-400">{{ $row['updated_at'] }}</div>
                            </td>
                            <td class="px-3 py-2.5 whitespace-nowrap">
                                @if ($row['status'] === 'completed')
                                    <span class="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-700">🟢 已上线</span>
                                @else
                                    <span class="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-700">🟡 待发布</span>
                                @endif
                            </td>
                            <td class="px-3 py-2.5 min-w-[260px]">
                                @if ($row['url'] !== '')
                                    <a href="{{ $row['url'] }}" target="_blank" rel="noopener" class="block max-w-[280px] truncate font-mono text-blue-600 underline hover:text-blue-800">{{ $row['url'] }}</a>
                                @elseif ($row['manual_publication_id'])
                                    <form method="POST" action="{{ route('admin.distribution.quick-receipt') }}" class="flex items-center gap-1.5">
                                        @csrf
                                        <input type="hidden" name="manual_publication_id" value="{{ $row['manual_publication_id'] }}">
                                        <input type="url" name="completion_url" required placeholder="发完后把帖子链接贴这里..." class="w-48 rounded border border-gray-300 px-2 py-1 text-xs focus:border-blue-500">
                                        <button type="submit" class="rounded bg-blue-600 px-2.5 py-1 font-semibold text-white hover:bg-blue-700">保存</button>
                                    </form>
                                @else
                                    <span class="text-gray-400">—</span>
                                @endif
                            </td>
                            <td class="px-3 py-2.5 text-center whitespace-nowrap font-mono">
                                @if ($row['citations'] > 0)
                                    <span class="inline-flex rounded-full bg-indigo-100 px-2.5 py-0.5 font-bold text-indigo-700">🔥 {{ $row['citations'] }} 次</span>
                                @else
                                    <span class="text-gray-400">0 次</span>
                                @endif
                            </td>
                            <td class="px-3 py-2.5 text-right whitespace-nowrap">
                                <div class="inline-flex items-center gap-1">
                                    <button type="button" class="sz-copy-btn rounded border border-gray-200 bg-white px-2 py-1 font-medium text-gray-700 hover:bg-gray-50" data-copy-text="{{ $row['title'] }}">📋 标题</button>
                                    @if ($row['content'] !== '')
                                        <button type="button" class="sz-copy-btn rounded border border-gray-200 bg-white px-2 py-1 font-medium text-gray-700 hover:bg-gray-50" data-copy-text="{{ $row['content'] }}">📄 正文</button>
                                    @endif
                                    <a href="{{ $row['editor_url'] }}" target="_blank" rel="noopener" class="rounded border border-blue-200 bg-blue-50 px-2 py-1 font-semibold text-blue-700 hover:bg-blue-100">去发 ↗</a>
                                </div>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>
    </section>

    {{-- 区块 4：可视化资产库（标题库 / 关键词库 / 知识库，支持人工手动增删） --}}
    <section class="rounded-xl border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <h2 class="text-lg font-bold text-gray-950">📚 可视化内容资产库（标题库 / 关键词库 / 知识库 · 支持手动更新）</h2>
                <p class="mt-0.5 text-xs text-gray-500">不用到处翻菜单，在这里直接查看、手动新增或删除山子高科核心母题、监测关键词与官方知识库。</p>
            </div>
            <div class="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1 text-xs font-semibold">
                <button type="button" data-asset-tab="titles" class="sz-asset-tab rounded-md bg-white px-3 py-1.5 text-blue-700 shadow-sm">标题库 (36)</button>
                <button type="button" data-asset-tab="keywords" class="sz-asset-tab rounded-md px-3 py-1.5 text-gray-600 hover:text-gray-900">关键词库 (52)</button>
                <button type="button" data-asset-tab="kbs" class="sz-asset-tab rounded-md px-3 py-1.5 text-gray-600 hover:text-gray-900">官方知识库 (3)</button>
            </div>
        </div>

        {{-- Asset Tab 1: 标题库 --}}
        <div id="sz-asset-titles" class="sz-asset-panel mt-4 space-y-4">
            <form method="POST" action="{{ route('admin.distribution.assets.title.save') }}" class="flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs">
                @csrf
                <select name="library_id" class="rounded-md border border-gray-300 bg-white px-2.5 py-2">
                    @foreach ($mx['title_libraries'] as $tl)
                        <option value="{{ $tl->id }}">{{ $tl->name }}</option>
                    @endforeach
                </select>
                <input type="text" name="title" required placeholder="输入新母题标题（如：山子高科2026年报核心亮点拆解）" class="min-w-[240px] flex-1 rounded-md border border-gray-300 bg-white px-3 py-2">
                <input type="text" name="keyword" placeholder="SEO关键词（逗号分隔，选填）" class="w-52 rounded-md border border-gray-300 bg-white px-3 py-2">
                <button type="submit" class="rounded-md bg-blue-600 px-3.5 py-2 font-semibold text-white hover:bg-blue-700">+ 手动新增标题</button>
            </form>
            <div class="grid grid-cols-1 gap-3 lg:grid-cols-3">
                @foreach ($mx['title_libraries'] as $tl)
                    @php($tItems = $mx['titles_by_lib']->get($tl->id, collect()))
                    <div class="rounded-lg border border-gray-200 p-3.5">
                        <div class="flex items-center justify-between border-b border-gray-100 pb-2">
                            <span class="text-xs font-bold text-gray-900">{{ $tl->name }}</span>
                            <span class="rounded-full bg-blue-50 px-2 py-0.5 font-mono text-[11px] font-semibold text-blue-700">{{ $tItems->count() }} 题</span>
                        </div>
                        <ul class="mt-2 max-h-64 space-y-1.5 overflow-y-auto pr-1 text-xs">
                            @foreach ($tItems as $ti)
                                <li class="flex items-start justify-between gap-2 rounded bg-gray-50 px-2.5 py-1.5 hover:bg-blue-50/40">
                                    <span class="text-gray-800 leading-5">{{ $ti->title }}</span>
                                    <form method="POST" action="{{ route('admin.distribution.assets.title.delete') }}" onsubmit="return confirm('确定删除该标题？')">
                                        @csrf
                                        <input type="hidden" name="title_id" value="{{ $ti->id }}">
                                        <button type="submit" class="shrink-0 text-gray-400 hover:text-rose-600" title="删除">✕</button>
                                    </form>
                                </li>
                            @endforeach
                        </ul>
                    </div>
                @endforeach
            </div>
        </div>

        {{-- Asset Tab 2: 关键词库 --}}
        <div id="sz-asset-keywords" class="sz-asset-panel mt-4 hidden space-y-4">
            <form method="POST" action="{{ route('admin.distribution.assets.keyword.save') }}" class="flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs">
                @csrf
                <select name="library_id" class="rounded-md border border-gray-300 bg-white px-2.5 py-2">
                    @foreach ($mx['keyword_libraries'] as $kl)
                        <option value="{{ $kl->id }}">{{ $kl->name }}</option>
                    @endforeach
                </select>
                <input type="text" name="keyword" required placeholder="输入新监测关键词（自动同步至 AI 可见性专题）" class="min-w-[240px] flex-1 rounded-md border border-gray-300 bg-white px-3 py-2">
                <button type="submit" class="rounded-md bg-blue-600 px-3.5 py-2 font-semibold text-white hover:bg-blue-700">+ 手动新增关键词</button>
            </form>
            <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                @foreach ($mx['keyword_libraries'] as $kl)
                    @php($kItems = $mx['keywords_by_lib']->get($kl->id, collect()))
                    <div class="rounded-lg border border-gray-200 p-3.5">
                        <div class="flex items-center justify-between border-b border-gray-100 pb-2">
                            <span class="text-xs font-bold text-gray-900">{{ $kl->name }}</span>
                            <span class="rounded-full bg-emerald-50 px-2 py-0.5 font-mono text-[11px] font-semibold text-emerald-700">{{ $kItems->count() }} 词</span>
                        </div>
                        <div class="mt-2.5 flex flex-wrap gap-1.5">
                            @foreach ($kItems as $ki)
                                <span class="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs text-gray-800">
                                    {{ $ki->keyword }}
                                    <form method="POST" action="{{ route('admin.distribution.assets.keyword.delete') }}" class="inline" onsubmit="return confirm('确定删除关键词「{{ $ki->keyword }}」？')">
                                        @csrf
                                        <input type="hidden" name="keyword_id" value="{{ $ki->id }}">
                                        <button type="submit" class="text-gray-400 hover:text-rose-600" title="删除">×</button>
                                    </form>
                                </span>
                            @endforeach
                        </div>
                    </div>
                @endforeach
            </div>
        </div>

        {{-- Asset Tab 3: 官方知识库 --}}
        <div id="sz-asset-kbs" class="sz-asset-panel mt-4 hidden space-y-3">
            <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
                @foreach ($mx['knowledge_bases'] as $kb)
                    <div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
                        <div>
                            <div class="text-sm font-bold text-gray-900">#{{ $kb->id }} · {{ $kb->name }}</div>
                            <p class="mt-1.5 text-xs leading-5 text-gray-500">{{ $kb->description ?: mb_substr(strip_tags((string) $kb->content), 0, 120) }}</p>
                        </div>
                        <div class="mt-3 flex items-center justify-between border-t border-gray-100 pt-2.5 text-xs">
                            <span class="text-gray-400">更新于 {{ substr((string) $kb->updated_at, 0, 10) }}</span>
                            <a href="{{ url('/geo_admin/materials/knowledge/' . $kb->id . '/edit') }}" class="font-semibold text-blue-600 hover:underline">编辑全文 ↗</a>
                        </div>
                    </div>
                @endforeach
            </div>
        </div>
    </section>
</div>

<script>
(function () {
    const csrf = document.querySelector('#sz-dispatch-form input[name="_token"]')?.value || '';

    // 1. Copy helper with HTTP fallback (works on non-HTTPS internal hosts)
    function copyText(text, btn) {
        const done = () => {
            const old = btn.textContent;
            btn.textContent = '✅ 已复制';
            setTimeout(() => { btn.textContent = old; }, 1200);
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
        ta.select();
        try { document.execCommand('copy'); } catch (e) {}
        document.body.removeChild(ta);
        cb();
    }
    document.querySelectorAll('.sz-copy-btn').forEach(btn => {
        btn.addEventListener('click', () => copyText(btn.getAttribute('data-copy-text') || '', btn));
    });

    // 2. Upload vs Existing tabs
    const tabUpload = document.getElementById('sz-tab-upload');
    const tabExisting = document.getElementById('sz-tab-existing');
    const panelUpload = document.getElementById('sz-panel-upload');
    const panelExisting = document.getElementById('sz-panel-existing');
    const modeInput = document.getElementById('sz-dispatch-mode');
    tabUpload?.addEventListener('click', () => {
        modeInput.value = 'upload';
        panelUpload.classList.remove('hidden');
        panelExisting.classList.add('hidden');
        tabUpload.classList.add('bg-white', 'text-blue-700', 'shadow-sm');
        tabExisting.classList.remove('bg-white', 'text-blue-700', 'shadow-sm');
    });
    tabExisting?.addEventListener('click', () => {
        modeInput.value = 'existing';
        panelExisting.classList.remove('hidden');
        panelUpload.classList.add('hidden');
        tabExisting.classList.add('bg-white', 'text-blue-700', 'shadow-sm');
        tabUpload.classList.remove('bg-white', 'text-blue-700', 'shadow-sm');
    });

    // 3. Drag & Drop file reader (.md / .txt)
    const dropzone = document.getElementById('sz-dropzone');
    const fileInput = document.getElementById('sz-file-input');
    const titleInput = document.getElementById('sz-input-title');
    const contentInput = document.getElementById('sz-input-content');
    const dropHint = document.getElementById('sz-dropzone-hint');

    function handleFile(file) {
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
            const raw = String(reader.result || '').trim();
            let lines = raw.split(/\r?\n/);
            let detectedTitle = file.name.replace(/\.(md|txt|markdown)$/i, '');
            if (lines.length && lines[0].trim().startsWith('#')) {
                detectedTitle = lines[0].replace(/^#+\s*/, '').trim() || detectedTitle;
                lines = lines.slice(1);
            }
            titleInput.value = detectedTitle;
            contentInput.value = lines.join('\n').trim() || raw;
            dropHint.textContent = '✅ 已载入文件：' + file.name + '（共 ' + contentInput.value.length + ' 字），可以直接点「🛡️ 立即合规质检打分」！';
        };
        reader.readAsText(file, 'utf-8');
    }
    dropzone?.addEventListener('click', () => fileInput.click());
    fileInput?.addEventListener('change', (e) => handleFile(e.target.files?.[0]));
    dropzone?.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('border-blue-600', 'bg-blue-100/60'); });
    dropzone?.addEventListener('dragleave', () => { dropzone.classList.remove('border-blue-600', 'bg-blue-100/60'); });
    dropzone?.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('border-blue-600', 'bg-blue-100/60');
        handleFile(e.dataTransfer?.files?.[0]);
    });

    // 4. Standalone AI Quality Inspection with reasons
    const btnInspect = document.getElementById('sz-btn-inspect');
    const statusEl = document.getElementById('sz-inspect-status');
    const resBox = document.getElementById('sz-inspect-result');
    btnInspect?.addEventListener('click', async () => {
        const title = (titleInput.value || '').trim();
        const content = (contentInput.value || '').trim();
        if (!title || content.length < 20) {
            statusEl.textContent = '⚠️ 请先拖入文章或填写标题与至少 20 字正文。';
            return;
        }
        btnInspect.disabled = true;
        statusEl.textContent = '⏳ 正在对照山子高科官方知识库与信披红线逐条评分（约 5～15 秒）...';
        try {
            const resp = await fetch('{{ route("admin.distribution.quick-inspect") }}', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf, 'Accept': 'application/json' },
                body: JSON.stringify({ title, content })
            });
            const data = await resp.json();
            if (!data.ok) {
                statusEl.textContent = '❌ ' + (data.error || '质检失败');
                return;
            }
            resBox.classList.remove('hidden');
            const badge = document.getElementById('sz-score-badge');
            const passLbl = document.getElementById('sz-pass-label');
            badge.textContent = data.score + ' / 100';
            if (data.passed) {
                badge.className = 'inline-flex items-center rounded-full bg-emerald-100 px-3.5 py-1 font-mono text-lg font-bold text-emerald-800';
                passLbl.textContent = '✅ 通过山子高科合规安检门（≥85分，可直接派发）';
                passLbl.className = 'text-sm font-semibold text-emerald-700';
            } else {
                badge.className = 'inline-flex items-center rounded-full bg-amber-100 px-3.5 py-1 font-mono text-lg font-bold text-amber-800';
                passLbl.textContent = '⚠️ 建议按下方理由修改后再发（<85分）';
                passLbl.className = 'text-sm font-semibold text-amber-700';
            }
            document.getElementById('sz-score-summary').textContent = data.summary || '已完成评审。';
            const dimsEl = document.getElementById('sz-score-dims');
            dimsEl.innerHTML = (data.dimensions || []).map(d =>
                `<div class="rounded-lg border border-gray-200 bg-white p-3">
                    <div class="flex items-center justify-between text-xs font-semibold text-gray-800"><span>${d.name || ''}</span><span class="font-mono text-blue-700">${d.score ?? '-'}分</span></div>
                    <p class="mt-1 text-[11px] leading-4 text-gray-500">${d.comment || ''}</p>
                </div>`
            ).join('');
            const issuesWrap = document.getElementById('sz-score-issues-wrap');
            const issuesEl = document.getElementById('sz-score-issues');
            if (Array.isArray(data.issues) && data.issues.length > 0) {
                issuesWrap.classList.remove('hidden');
                issuesEl.innerHTML = data.issues.map(it =>
                    `<div class="rounded-lg border border-rose-200 bg-white p-3 text-xs">
                        <div class="font-bold text-rose-700">[${(it.severity || 'medium').toUpperCase()}] ${it.title || '需核实项'}</div>
                        ${it.quote ? `<div class="mt-1 rounded bg-gray-50 px-2 py-1 text-gray-600">原文：${it.quote}</div>` : ''}
                        <div class="mt-1 text-gray-700"><b>扣分理由：</b>${it.reason || ''}</div>
                        <div class="mt-1 text-emerald-700"><b>修改建议：</b>${it.suggestion || ''}</div>
                    </div>`
                ).join('');
            } else {
                issuesWrap.classList.add('hidden');
            }
            statusEl.textContent = '✅ 评分完成！';
        } catch (err) {
            statusEl.textContent = '❌ 请求异常：' + err;
        } finally {
            btnInspect.disabled = false;
        }
    });

    // 5. Select all platforms
    document.getElementById('sz-check-all')?.addEventListener('click', () => {
        const cbs = Array.from(document.querySelectorAll('.sz-plat-cb'));
        const allChecked = cbs.every(c => c.checked);
        cbs.forEach(c => { c.checked = !allChecked; });
    });

    // 6. Excel table filtering
    const fPlat = document.getElementById('sz-filter-platform');
    const fStat = document.getElementById('sz-filter-status');
    function applyFilter() {
        const pv = fPlat?.value || '';
        const sv = fStat?.value || '';
        document.querySelectorAll('.sz-ledger-row').forEach(tr => {
            const okP = !pv || tr.getAttribute('data-platform') === pv;
            const okS = !sv || tr.getAttribute('data-status') === sv;
            tr.style.display = (okP && okS) ? '' : 'none';
        });
    }
    fPlat?.addEventListener('change', applyFilter);
    fStat?.addEventListener('change', applyFilter);

    // 7. Visual Asset Tabs
    document.querySelectorAll('.sz-asset-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-asset-tab');
            document.querySelectorAll('.sz-asset-tab').forEach(b => b.classList.remove('bg-white', 'text-blue-700', 'shadow-sm'));
            btn.classList.add('bg-white', 'text-blue-700', 'shadow-sm');
            document.querySelectorAll('.sz-asset-panel').forEach(p => p.classList.add('hidden'));
            document.getElementById('sz-asset-' + target)?.classList.remove('hidden');
        });
    });
})();
</script>
