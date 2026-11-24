<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\AiModel;
use App\Models\Article;
use App\Models\ArticleDistribution;
use App\Models\DistributionChannel;
use App\Models\ManualPublication;
use App\Models\ManualPublicationAccount;
use App\Services\GeoFlow\AiVisibility\AiVisibilityKeywordNormalizer;
use App\Services\GeoFlow\Distribution\PlatformWeb\PlatformCatalog;
use App\Services\GeoFlow\DistributionPayloadBuilder;
use App\Services\GeoFlow\DistributionPublisherManager;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\StreamedResponse;
use Throwable;

class GeoMatrixController extends Controller
{
    private const LEGACY_INSIGHTS = [
        ['url' => 'https://www.sensteed.com/insights/article/keyinfo-304.html', 'title' => '历史关键信息归档 #304（官网专栏已静态化）', 'date' => '2026-11-23'],
        ['url' => 'https://www.sensteed.com/insights/article/keyinfo-303.html', 'title' => '历史关键信息归档 #303（官网专栏已静态化）', 'date' => '2026-11-23'],
        ['url' => 'https://www.sensteed.com/insights/article/keyinfo-302.html', 'title' => '历史关键信息归档 #302（官网专栏已静态化）', 'date' => '2026-11-18'],
        ['url' => 'https://www.sensteed.com/insights/article/keyinfo-301.html', 'title' => '历史关键信息归档 #301（官网专栏已静态化）', 'date' => '2026-11-17'],
        ['url' => 'https://www.sensteed.com/insights/article/keyinfo-300.html', 'title' => '历史关键信息归档 #300（官网专栏已静态化）', 'date' => '2026-11-16'],
        ['url' => 'https://www.sensteed.com/insights/article/keyinfo-299.html', 'title' => '历史关键信息归档 #299（官网专栏已静态化）', 'date' => '2026-11-11'],
    ];

    public static function platformMeta(object $acc): array
    {
        $name = (string) ($acc->account_name ?? '');
        $platform = (string) ($acc->platform ?? 'custom');
        $editorUrl = (string) ($acc->profile_url ?? '');
        $stoneTag = 'sz-tag-slate';
        $bronzeTag = 'sz-tag-blue';

        if (str_contains($name, '官网') || str_contains($editorUrl, 'sensteed.com')) {
            return [
                'code' => 'CH-01',
                'short_name' => '官网 · 关键信息',
                'ai_target' => '全引擎权威源',
                'summary' => '1 秒自动静态化至 sensteed.com/insights/ 并刷新 Sitemap',
                'badge' => $bronzeTag,
                'editor_url' => 'https://www.sensteed.com/insights/',
                'domain' => 'sensteed.com',
                'is_official' => true,
            ];
        }
        if ($platform === 'toutiao') {
            $editorUrl = PlatformCatalog::editorUrl('toutiao', null);
            return [
                'code' => 'CH-02',
                'short_name' => '今日头条',
                'ai_target' => '豆包核心源',
                'summary' => '优先同步过检深度专稿与问答澄清稿',
                'badge' => $bronzeTag,
                'editor_url' => $editorUrl,
                'domain' => 'toutiao.com',
                'is_official' => false,
            ];
        }
        if ($platform === 'sohu') {
            $editorUrl = PlatformCatalog::editorUrl('sohu', null);
            return [
                'code' => 'CH-03',
                'short_name' => '搜狐号',
                'ai_target' => 'DeepSeek 门户',
                'summary' => '发布业务与财报拆解长文并回填线上链接',
                'badge' => $stoneTag,
                'editor_url' => $editorUrl,
                'domain' => 'sohu.com',
                'is_official' => false,
            ];
        }
        if ($platform === 'netease') {
            $editorUrl = PlatformCatalog::editorUrl('netease', null);
            return [
                'code' => 'CH-04',
                'short_name' => '网易号',
                'ai_target' => 'DeepSeek 补位',
                'summary' => '覆盖产业协同与汽配业务增量门户收录',
                'badge' => $stoneTag,
                'editor_url' => $editorUrl,
                'domain' => '163.com',
                'is_official' => false,
            ];
        }
        if (str_contains($name, '东方财富')) {
            return [
                'code' => 'CH-05',
                'short_name' => '东方财富股吧',
                'ai_target' => '财经头号源',
                'summary' => '发表带完整标题的独立主帖或财富号文章',
                'badge' => $bronzeTag,
                'editor_url' => 'https://guba.eastmoney.com/list,000981.html',
                'domain' => 'eastmoney.com',
                'is_official' => false,
            ];
        }
        if (str_contains($name, '同花顺')) {
            return [
                'code' => 'CH-06',
                'short_name' => '同花顺社区',
                'ai_target' => '财经高覆盖源',
                'summary' => '同步标准问答与澄清主帖，避免仅回帖',
                'badge' => $stoneTag,
                'editor_url' => 'https://basic.10jqka.com.cn/000981/',
                'domain' => '10jqka.com.cn',
                'is_official' => false,
            ];
        }
        if ($platform === 'douyin') {
            return [
                'code' => 'CH-07',
                'short_name' => '抖音',
                'ai_target' => '豆包视频简介',
                'summary' => '发视频时完整填写 200 字网页摘要文字',
                'badge' => $stoneTag,
                'editor_url' => 'https://creator.douyin.com/',
                'domain' => 'douyin.com',
                'is_official' => false,
            ];
        }
        if ($platform === 'wechat') {
            return [
                'code' => 'CH-08',
                'short_name' => '微信公众号',
                'ai_target' => '元宝与官方母稿',
                'summary' => '沉淀权威图文母稿，覆盖微信与腾讯元宝',
                'badge' => $stoneTag,
                'editor_url' => 'https://mp.weixin.qq.com/',
                'domain' => 'mp.weixin.qq.com',
                'is_official' => false,
            ];
        }
        if ($platform === 'xiaohongshu') {
            return [
                'code' => 'CH-09',
                'short_name' => '小红书',
                'ai_target' => '图文日常触达',
                'summary' => '复用图文卡片触达个人投资者日常检索',
                'badge' => $stoneTag,
                'editor_url' => 'https://creator.xiaohongshu.com/',
                'domain' => 'xiaohongshu.com',
                'is_official' => false,
            ];
        }

        return [
            'code' => 'CH-00',
            'short_name' => $name ?: '扩展渠道',
            'ai_target' => '综合渠道',
            'summary' => '自定义外部传播渠道',
            'badge' => $stoneTag,
            'editor_url' => $editorUrl ?: '#',
            'domain' => '',
            'is_official' => false,
        ];
    }

    public static function matrixData(): array
    {
        $accounts = DB::table('manual_publication_accounts')
            ->where('is_active', true)
            ->orderBy('account_name')
            ->get();

        // AI citation counts from ai_visibility_sources (by exact URL & by domain)
        $urlCitations = [];
        $domainCitations = [];
        try {
            $srcRows = DB::table('ai_visibility_sources')
                ->whereNotNull('url')
                ->where('url', '!=', '')
                ->get(['url', 'domain']);
            foreach ($srcRows as $s) {
                $u = rtrim(trim((string) $s->url), '/');
                $urlCitations[$u] = ($urlCitations[$u] ?? 0) + 1;
                $dom = strtolower((string) ($s->domain ?: parse_url($u, PHP_URL_HOST) ?: ''));
                $dom = str_starts_with($dom, 'www.') ? substr($dom, 4) : $dom;
                if ($dom !== '') {
                    $domainCitations[$dom] = ($domainCitations[$dom] ?? 0) + 1;
                }
            }
        } catch (Throwable) {
        }

        $syncedOfficial = DB::table('article_distributions as d')
            ->join('articles as a', 'a.id', '=', 'd.article_id')
            ->where('d.status', 'synced')
            ->whereNotNull('d.remote_url')
            ->orderByDesc('d.id')
            ->get(['d.id', 'd.article_id', 'd.remote_url', 'd.updated_at', 'a.title', 'a.content']);

        $manualRows = DB::table('manual_publications as m')
            ->leftJoin('manual_publication_accounts as acc', 'acc.id', '=', 'm.account_id')
            ->leftJoin('articles as a', 'a.id', '=', 'm.article_id')
            ->whereIn('m.status', ['ready', 'in_progress', 'completed'])
            ->orderByDesc('m.id')
            ->get([
                'm.id', 'm.account_id', 'm.article_id', 'm.status', 'm.completion_url',
                'm.content', 'm.updated_at', 'm.completed_at',
                'acc.account_name', 'acc.platform', 'acc.profile_url',
                'a.title as article_title',
            ]);

        // Build unified Excel ledger rows
        $ledger = [];
        $accStats = [];
        foreach ($accounts as $acc) {
            $meta = self::platformMeta($acc);
            $dom = $meta['domain'];
            $accStats[$acc->id] = [
                'id' => $acc->id,
                'code' => $meta['code'],
                'name' => $acc->account_name,
                'short_name' => $meta['short_name'],
                'platform' => $acc->platform,
                'ai_target' => $meta['ai_target'],
                'summary' => $meta['summary'],
                'badge' => $meta['badge'],
                'editor_url' => $meta['editor_url'],
                'notes' => (string) ($acc->notes ?? ''),
                'is_official' => $meta['is_official'],
                'published_count' => 0,
                'pending_count' => 0,
                'citation_count' => $dom !== '' ? ($domainCitations[$dom] ?? 0) : 0,
            ];
        }

        // Official synced rows
        $officialAccId = null;
        foreach ($accStats as $aid => $st) {
            if ($st['is_official']) {
                $officialAccId = $aid;
                break;
            }
        }
        foreach ($syncedOfficial as $row) {
            $u = rtrim((string) $row->remote_url, '/');
            $cites = $urlCitations[$u] ?? 0;
            if ($officialAccId !== null) {
                $accStats[$officialAccId]['published_count']++;
            }
            $ledger[] = [
                'row_type' => 'official',
                'id' => 'dist-' . $row->id,
                'manual_publication_id' => null,
                'account_id' => $officialAccId,
                'platform_label' => '官网 · 关键信息',
                'ai_target' => '全引擎权威源',
                'badge' => 'sz-tag-blue',
                'title' => (string) $row->title,
                'content' => (string) ($row->content ?? ''),
                'status' => 'completed',
                'url' => (string) $row->remote_url,
                'editor_url' => 'https://www.sensteed.com/insights/',
                'citations' => $cites,
                'updated_at' => substr((string) $row->updated_at, 0, 16),
            ];
        }
        // Archived 6 official /insights/ articles
        foreach (self::LEGACY_INSIGHTS as $leg) {
            $u = rtrim($leg['url'], '/');
            if ($officialAccId !== null) {
                $accStats[$officialAccId]['published_count']++;
            }
            $ledger[] = [
                'row_type' => 'official_archive',
                'id' => 'leg-' . md5($u),
                'manual_publication_id' => null,
                'account_id' => $officialAccId,
                'platform_label' => '官网 · 关键信息',
                'ai_target' => '全引擎权威源',
                'badge' => 'sz-tag-blue',
                'title' => $leg['title'],
                'content' => '',
                'status' => 'completed',
                'url' => $leg['url'],
                'editor_url' => 'https://www.sensteed.com/insights/',
                'citations' => $urlCitations[$u] ?? 0,
                'updated_at' => $leg['date'],
            ];
        }

        // Manual / external matrix rows
        foreach ($manualRows as $m) {
            $aid = $m->account_id;
            $st = $accStats[$aid] ?? null;
            if ($st !== null) {
                if ($m->status === 'completed') {
                    $accStats[$aid]['published_count']++;
                } else {
                    $accStats[$aid]['pending_count']++;
                }
            }
            $url = trim((string) ($m->completion_url ?? ''));
            $cites = $url !== '' ? ($urlCitations[rtrim($url, '/')] ?? 0) : 0;
            $title = trim((string) ($m->article_title ?? ''));
            if ($title === '') {
                $firstLine = trim(strtok((string) $m->content, "\n") ?: '未命名文章');
                $title = ltrim($firstLine, "# \t");
            }
            $ledger[] = [
                'row_type' => 'manual',
                'id' => 'mp-' . $m->id,
                'manual_publication_id' => (int) $m->id,
                'account_id' => $aid,
                'platform_label' => $st ? $st['short_name'] : ((string) ($m->account_name ?: $m->platform)),
                'ai_target' => $st ? $st['ai_target'] : '外部平台',
                'badge' => $st ? $st['badge'] : 'sz-tag-slate',
                'title' => $title,
                'content' => (string) ($m->content ?? ''),
                'status' => (string) $m->status,
                'url' => $url,
                'editor_url' => $st ? $st['editor_url'] : ((string) ($m->profile_url ?? '#')),
                'citations' => $cites,
                'updated_at' => substr((string) ($m->completed_at ?: $m->updated_at), 0, 16),
            ];
        }

        // Approved articles for dropdown
        $approvedArticles = DB::table('articles')
            ->whereNull('deleted_at')
            ->whereIn('review_status', ['approved', 'auto_approved'])
            ->orderByDesc('id')
            ->limit(40)
            ->get(['id', 'title', 'status', 'updated_at']);

        // Visual asset libraries (Title Libraries, Keyword Libraries, Knowledge Bases)
        $titleLibraries = DB::table('title_libraries')->orderBy('id')->get();
        $titlesByLib = DB::table('titles')->orderByDesc('id')->get()->groupBy('library_id');
        $keywordLibraries = DB::table('keyword_libraries')->orderBy('id')->get();
        $keywordsByLib = DB::table('keywords')->orderByDesc('id')->get()->groupBy('library_id');
        $knowledgeBases = DB::table('knowledge_bases')->orderBy('id')->get(['id', 'name', 'description', 'content', 'updated_at']);

        $totalPublished = count(array_filter($ledger, fn ($r) => $r['status'] === 'completed'));
        $totalCitedUrls = count(array_filter($ledger, fn ($r) => $r['citations'] > 0));
        $totalCitationHits = array_sum(array_map(fn ($r) => $r['citations'], $ledger));

        return [
            'platforms' => array_values($accStats),
            'ledger' => $ledger,
            'approved_articles' => $approvedArticles,
            'title_libraries' => $titleLibraries,
            'titles_by_lib' => $titlesByLib,
            'keyword_libraries' => $keywordLibraries,
            'keywords_by_lib' => $keywordsByLib,
            'knowledge_bases' => $knowledgeBases,
            'summary' => [
                'total_rows' => count($ledger),
                'published_count' => $totalPublished,
                'pending_count' => count($ledger) - $totalPublished,
                'cited_urls' => $totalCitedUrls,
                'citation_hits' => $totalCitationHits,
                'citation_rate' => $totalPublished > 0 ? round(100.0 * $totalCitedUrls / $totalPublished, 1) : 0.0,
            ],
        ];
    }

    /**
     * Standalone synchronous AI quality inspection with detailed reasons & rewrite suggestions.
     */
    public function quickInspect(Request $request): JsonResponse
    {
        $data = $request->validate([
            'title' => ['required', 'string', 'min:2', 'max:250'],
            'content' => ['required', 'string', 'min:20', 'max:30000'],
        ]);

        $model = AiModel::query()->where('status', 'active')->orderBy('id')->first();
        if (! $model) {
            return response()->json(['ok' => false, 'error' => '未找到可用的 AI 模型配置'], 422);
        }

        $rawKey = (string) $model->getRawOriginal('api_key');
        if (str_starts_with($rawKey, 'enc:v1:') && class_exists(\App\Support\GeoFlow\ApiKeyCrypto::class)) {
            $apiKey = app(\App\Support\GeoFlow\ApiKeyCrypto::class)->decrypt($rawKey);
        } else {
            try {
                $apiKey = Crypt::decryptString($rawKey);
            } catch (Throwable) {
                try {
                    $apiKey = Crypt::decrypt($rawKey);
                } catch (Throwable) {
                    $apiKey = $rawKey;
                }
            }
        }
        if ($apiKey === '') {
            return response()->json(['ok' => false, 'error' => 'AI 模型密钥解密失败，请在 AI 配置器检查模型配置'], 422);
        }

        $promptTemplate = (string) (DB::table('prompts')->where('id', 10)->value('content') ?? '');
        $kbs = DB::table('knowledge_bases')->whereIn('id', [2, 3])->orderBy('id')->get(['name', 'content']);
        $kbContext = '';
        foreach ($kbs as $kb) {
            $kbContext .= "【{$kb->name}】\n" . mb_substr((string) $kb->content, 0, 3200) . "\n\n";
        }

        $systemPrompt = "你是山子高科（000981.SZ）上市公司信披合规与 GEO 内容质量评审官。请严格依据下方官方事实知识库与质检规则，对用户提交的稿件进行客观评分，给出清晰易懂的打分理由、4个维度的分项打分，以及逐条扣分原因与修改建议。\n\n"
            . "【输出格式强制要求】仅输出合法 JSON（不要 Markdown 代码块包裹），结构如下：\n"
            . '{"score": 88, "passed": true, "summary": "一段清晰易懂的总评与核心打分理由", '
            . '"dimensions": ['
            . '{"name": "事实与公告一致性", "score": 90, "comment": "简短评价"},'
            . '{"name": "信披与广告法合规", "score": 92, "comment": "简短评价"},'
            . '{"name": "业务与品牌锚点", "score": 85, "comment": "简短评价"},'
            . '{"name": "GEO结构与AI易抓度", "score": 85, "comment": "简短评价"}'
            . '], "issues": [{"severity": "high|medium|low", "title": "问题简述", "quote": "原文片段", "reason": "扣分理由", "suggestion": "具体修改建议"}]}';

        $userPrompt = "=== 质检规则参考 ===\n" . mb_substr($promptTemplate, 0, 2200)
            . "\n\n=== 山子高科官方事实知识库（唯一准绳） ===\n" . $kbContext
            . "\n=== 待评测文章 ===\n标题：" . $data['title'] . "\n\n正文：\n" . mb_substr($data['content'], 0, 8000);

        $endpoint = rtrim((string) $model->api_url, '/') . '/chat/completions';
        try {
            $resp = Http::withToken($apiKey)->timeout(60)->post($endpoint, [
                'model' => (string) $model->model_id,
                'temperature' => 0.2,
                'messages' => [
                    ['role' => 'system', 'content' => $systemPrompt],
                    ['role' => 'user', 'content' => $userPrompt],
                ],
            ]);
            if (! $resp->successful()) {
                return response()->json(['ok' => false, 'error' => '模型调用失败 (HTTP ' . $resp->status() . ')'], 502);
            }
            $rawText = (string) ($resp->json('choices.0.message.content') ?? '');
            $clean = trim($rawText);
            if (preg_match('/```(?:json)?\s*(\{.*\})\s*```/s', $clean, $m)) {
                $clean = $m[1];
            } elseif (preg_match('/(\{.*\})/s', $clean, $m)) {
                $clean = $m[1];
            }
            $parsed = json_decode($clean, true);
            if (! is_array($parsed) || ! isset($parsed['score'])) {
                return response()->json([
                    'ok' => true,
                    'score' => 80,
                    'passed' => false,
                    'summary' => mb_substr($rawText, 0, 800),
                    'dimensions' => [],
                    'issues' => [],
                ]);
            }
            $score = max(0, min(100, (int) $parsed['score']));
            return response()->json([
                'ok' => true,
                'score' => $score,
                'passed' => $score >= 85,
                'summary' => (string) ($parsed['summary'] ?? ''),
                'dimensions' => is_array($parsed['dimensions'] ?? null) ? $parsed['dimensions'] : [],
                'issues' => is_array($parsed['issues'] ?? null) ? $parsed['issues'] : [],
            ]);
        } catch (Throwable $e) {
            return response()->json(['ok' => false, 'error' => '质检超时或异常：' . $e->getMessage()], 500);
        }
    }

    /**
     * Quick dispatch an uploaded/dragged or existing article to Official Website + selected external platforms.
     */
    public function quickDispatch(
        Request $request,
        DistributionPublisherManager $publisherManager,
        DistributionPayloadBuilder $payloadBuilder,
    ): RedirectResponse {
        $data = $request->validate([
            'mode' => ['required', 'in:upload,existing'],
            'article_id' => ['nullable', 'integer'],
            'title' => ['nullable', 'string', 'max:250'],
            'content' => ['nullable', 'string', 'max:50000'],
            'account_ids' => ['required', 'array', 'min:1'],
            'account_ids.*' => ['integer'],
        ]);

        $now = now();
        if ($data['mode'] === 'existing') {
            if (empty($data['article_id'])) {
                return back()->withErrors('请先在下拉框中选择一篇系统已生成的文章。');
            }
            $article = Article::query()->findOrFail((int) $data['article_id']);
        } else {
            $title = trim((string) ($data['title'] ?? ''));
            $content = trim((string) ($data['content'] ?? ''));
            if ($title === '' || $content === '') {
                return back()->withErrors('请先拖入文件或填写文章标题与正文。');
            }
            $slug = 'post-' . strtolower(Str::random(8));
            $plain = trim(preg_replace('/[#*`>\-\r\n]+/', ' ', $content));
            $excerpt = mb_substr($plain, 0, 140);
            $article = Article::query()->create([
                'title' => $title,
                'slug' => $slug,
                'excerpt' => $excerpt,
                'meta_description' => $excerpt,
                'keywords' => '山子高科,000981,邦奇动力,艾尔希ARC,半导体先进封装材料',
                'content' => $content,
                'category_id' => 1,
                'author_id' => 1,
                'status' => 'published',
                'review_status' => 'approved',
                'is_ai_generated' => 0,
                'published_at' => $now,
            ]);
        }

        $accountIds = array_map('intval', $data['account_ids']);
        $accounts = ManualPublicationAccount::query()->whereIn('id', $accountIds)->where('is_active', true)->get();
        $msgs = [];

        foreach ($accounts as $acc) {
            $meta = self::platformMeta($acc);
            if ($meta['is_official']) {
                // Direct 1-second publish to sensteed.com/insights via the active geoflow_agent channel
                $channel = DistributionChannel::query()
                    ->where('status', 'active')
                    ->orderBy('id')
                    ->get()
                    ->first(static fn (DistributionChannel $c): bool => $c->channelType() === 'geoflow_agent');
                if (! $channel) {
                    $msgs[] = '未找到启用的官网 geoflow_agent 渠道';
                    continue;
                }
                $article->load(['category:id,name,slug', 'author:id,name', 'articleImages.image']);
                $payload = $payloadBuilder->build($article);
                $payloadJson = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?: '';
                $dist = ArticleDistribution::query()->updateOrCreate(
                    ['article_id' => $article->id, 'distribution_channel_id' => $channel->id],
                    [
                        'action' => 'publish',
                        'status' => 'sending',
                        'idempotency_key' => 'quick-' . $article->id . '-' . time(),
                        'attempt_count' => 1,
                        'last_attempt_at' => $now,
                        'payload_hash' => hash('sha256', $payloadJson),
                    ]
                );
                $dist->setRelation('channel', $channel);
                $dist->setRelation('article', $article);
                try {
                    $res = $publisherManager->forChannel($channel)->publish($dist, $payload);
                    $remoteUrl = (string) ($res['remote_url'] ?? $res['url'] ?? '');
                    $dist->update([
                        'status' => 'synced',
                        'remote_id' => (string) ($res['remote_id'] ?? $article->slug),
                        'remote_url' => $remoteUrl,
                        'remote_meta' => $res,
                        'last_error_message' => null,
                    ]);
                    $article->update(['status' => 'published', 'published_at' => $article->published_at ?: $now]);
                    $msgs[] = '官网已同步上线：' . $remoteUrl;
                } catch (Throwable $e) {
                    $dist->update(['status' => 'failed', 'last_error_message' => $e->getMessage()]);
                    $msgs[] = '官网推送失败：' . $e->getMessage();
                }
            } else {
                // Create ready work order in manual_publications (bypassing AI gate for human-uploaded drafts)
                $exists = ManualPublication::query()
                    ->where('account_id', $acc->id)
                    ->where('article_id', $article->id)
                    ->whereIn('status', ['ready', 'in_progress', 'completed'])
                    ->exists();
                if (! $exists) {
                    $fullContent = '# ' . $article->title . "\n\n" . $article->content;
                    ManualPublication::query()->create([
                        'type' => ManualPublication::TYPE_POST,
                        'article_id' => $article->id,
                        'persona_id' => $acc->persona_id ?: 1,
                        'account_id' => $acc->id,
                        'assigned_admin_id' => 1,
                        'created_by_admin_id' => 1,
                        'platform' => $acc->platform,
                        'custom_platform' => $acc->custom_platform,
                        'content' => $fullContent,
                        'content_fingerprint' => hash('sha256', $fullContent),
                        'identity_snapshot' => [
                            'account' => [
                                'id' => $acc->id,
                                'name' => $acc->account_name,
                                'platform' => $acc->platform,
                            ],
                            'snapshotted_at' => $now->toIso8601String(),
                        ],
                        'status' => ManualPublication::STATUS_READY,
                        'status_changed_at' => $now,
                        'revision' => 1,
                        'publication_payload' => [
                            'title' => $article->title,
                            'body' => $article->content,
                        ],
                    ]);
                    $msgs[] = $meta['short_name'] . ' 已加入待发台账';
                } else {
                    $msgs[] = $meta['short_name'] . ' 已存在该篇记录（未重复创建）';
                }
            }
        }

        return redirect()->route('admin.distribution.index')->with('message', '派发完成：' . implode('；', $msgs));
    }

    /**
     * Save live published URL right inside the Excel table row.
     */
    public function quickReceipt(Request $request): RedirectResponse
    {
        $data = $request->validate([
            'manual_publication_id' => ['required', 'integer', 'exists:manual_publications,id'],
            'completion_url' => ['required', 'url:http,https', 'max:1000'],
        ]);

        ManualPublication::query()
            ->whereKey((int) $data['manual_publication_id'])
            ->update([
                'status' => ManualPublication::STATUS_COMPLETED,
                'completion_url' => trim((string) $data['completion_url']),
                'completed_at' => now(),
                'status_changed_at' => now(),
                'updated_at' => now(),
            ]);

        return redirect()->route('admin.distribution.index')->with('message', '已保存上线链接！系统将自动在 AI 可见性评测中追踪该链接的被翻牌次数。');
    }

    /**
     * Export Excel-compatible UTF-8 BOM CSV ledger.
     */
    public function exportLedger(): StreamedResponse
    {
        $data = self::matrixData();
        $filename = '山子高科GEO全平台发稿与被翻牌台账_' . date('Ymd_His') . '.csv';

        return response()->streamDownload(function () use ($data): void {
            $out = fopen('php://output', 'w');
            fwrite($out, "\xEF\xBB\xBF");
            fputcsv($out, ['序号', '发布平台', '目标AI引擎', '文章标题', '发布状态', '线上真实链接', 'AI被翻牌次数', '更新时间']);
            foreach ($data['ledger'] as $i => $row) {
                $statusText = $row['status'] === 'completed' ? '已上线' : '待发布';
                fputcsv($out, [
                    $i + 1,
                    $row['platform_label'],
                    $row['ai_target'],
                    $row['title'],
                    $statusText,
                    $row['url'] ?: '待回填',
                    $row['citations'],
                    $row['updated_at'],
                ]);
            }
            fclose($out);
        }, $filename, ['Content-Type' => 'text/csv; charset=UTF-8']);
    }

    public function saveTitle(Request $request): RedirectResponse
    {
        $data = $request->validate([
            'library_id' => ['required', 'integer', 'exists:title_libraries,id'],
            'title' => ['required', 'string', 'min:3', 'max:250'],
            'keyword' => ['nullable', 'string', 'max:250'],
        ]);
        $title = trim($data['title']);
        DB::table('titles')->insert([
            'library_id' => (int) $data['library_id'],
            'title' => $title,
            'keyword' => trim((string) ($data['keyword'] ?? '山子高科,000981')),
            'is_ai_generated' => 0,
            'used_count' => 0,
            'usage_count' => 0,
            'title_fingerprint' => hash('sha256', mb_strtolower($title)),
            'created_at' => now(),
        ]);
        DB::table('title_libraries')->where('id', (int) $data['library_id'])->update([
            'title_count' => DB::table('titles')->where('library_id', (int) $data['library_id'])->count(),
            'updated_at' => now(),
        ]);

        return redirect()->route('admin.distribution.index')->with('message', '已新增标题到标题库：' . $title);
    }

    public function deleteTitle(Request $request): RedirectResponse
    {
        $data = $request->validate(['title_id' => ['required', 'integer', 'exists:titles,id']]);
        $row = DB::table('titles')->where('id', (int) $data['title_id'])->first();
        if ($row) {
            DB::table('titles')->where('id', $row->id)->delete();
            DB::table('title_libraries')->where('id', $row->library_id)->update([
                'title_count' => DB::table('titles')->where('library_id', $row->library_id)->count(),
                'updated_at' => now(),
            ]);
        }

        return redirect()->route('admin.distribution.index')->with('message', '已删除该标题。');
    }

    public function saveKeyword(Request $request): RedirectResponse
    {
        $data = $request->validate([
            'library_id' => ['required', 'integer', 'exists:keyword_libraries,id'],
            'keyword' => ['required', 'string', 'min:2', 'max:100'],
        ]);
        $kw = trim($data['keyword']);
        DB::table('keywords')->insert([
            'library_id' => (int) $data['library_id'],
            'keyword' => $kw,
            'used_count' => 0,
            'usage_count' => 0,
            'created_at' => now(),
        ]);
        DB::table('keyword_libraries')->where('id', (int) $data['library_id'])->update([
            'keyword_count' => DB::table('keywords')->where('library_id', (int) $data['library_id'])->count(),
            'updated_at' => now(),
        ]);
        $topicId = ((int) $data['library_id'] === 2) ? 2 : (((int) $data['library_id'] === 3) ? 3 : 1);
        DB::table('ai_visibility_topic_keywords')->updateOrInsert(
            ['keyword_hash' => AiVisibilityKeywordNormalizer::hash($kw)],
            ['ai_visibility_topic_id' => $topicId, 'keyword' => $kw, 'created_at' => now(), 'updated_at' => now()]
        );

        return redirect()->route('admin.distribution.index')->with('message', '已新增监测关键词并同步进 AI 可见性专题：' . $kw);
    }

    public function deleteKeyword(Request $request): RedirectResponse
    {
        $data = $request->validate(['keyword_id' => ['required', 'integer', 'exists:keywords,id']]);
        $row = DB::table('keywords')->where('id', (int) $data['keyword_id'])->first();
        if ($row) {
            DB::table('keywords')->where('id', $row->id)->delete();
            DB::table('keyword_libraries')->where('id', $row->library_id)->update([
                'keyword_count' => DB::table('keywords')->where('library_id', $row->library_id)->count(),
                'updated_at' => now(),
            ]);
        }

        return redirect()->route('admin.distribution.index')->with('message', '已删除该关键词。');
    }
}
