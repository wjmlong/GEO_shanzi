<?php
error_reporting(0);

$INSIGHTS_DIR = dirname(__FILE__);
$CONFIG = is_file($INSIGHTS_DIR . '/config.php')
    ? include($INSIGHTS_DIR . '/config.php')
    : include($INSIGHTS_DIR . '/config.example.php');
if (!is_array($CONFIG)) {
    $CONFIG = array();
}

function ins_h($s) {
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}

function ins_http_status($code) {
    $map = array(
        200 => 'OK',
        400 => 'Bad Request',
        401 => 'Unauthorized',
        403 => 'Forbidden',
        404 => 'Not Found',
        405 => 'Method Not Allowed',
        500 => 'Internal Server Error'
    );
    $text = isset($map[$code]) ? $map[$code] : 'OK';
    header('HTTP/1.1 ' . intval($code) . ' ' . $text);
}

function ins_json_str($s) {
    $s = (string)$s;
    $s = str_replace(
        array('\\', '"', "\r", "\n", "\t", '</'),
        array('\\\\', '\\"', '\\r', '\\n', '\\t', '<\\/'),
        $s
    );
    $s = preg_replace('/[\x00-\x1F\x7F]/', '', $s);
    return '"' . $s . '"';
}

function ins_json_encode_utf8($val) {
    if (is_null($val)) return 'null';
    if (is_bool($val)) return $val ? 'true' : 'false';
    if (is_int($val) || is_float($val)) return (string)$val;
    if (is_string($val)) return ins_json_str($val);
    if (is_array($val)) {
        $isList = true;
        $i = 0;
        foreach ($val as $k => $v) {
            if ($k !== $i) { $isList = false; break; }
            $i++;
        }
        $parts = array();
        if ($isList) {
            foreach ($val as $v) {
                $parts[] = ins_json_encode_utf8($v);
            }
            return '[' . implode(',', $parts) . ']';
        } else {
            foreach ($val as $k => $v) {
                $parts[] = ins_json_str((string)$k) . ':' . ins_json_encode_utf8($v);
            }
            return '{' . implode(',', $parts) . '}';
        }
    }
    return 'null';
}

function ins_json_response($status, $payload) {
    ins_http_status($status);
    header('Content-Type: application/json; charset=utf-8');
    echo ins_json_encode_utf8($payload);
    exit;
}

function ins_header($name) {
    $key = 'HTTP_' . strtoupper(str_replace('-', '_', $name));
    if (isset($_SERVER[$key]) && is_string($_SERVER[$key])) {
        return trim($_SERVER[$key]);
    }
    if (function_exists('getallheaders')) {
        $all = getallheaders();
        if (is_array($all)) {
            $lower = strtolower($name);
            foreach ($all as $hk => $hv) {
                if (strtolower($hk) === $lower) {
                    return trim((string)$hv);
                }
            }
        }
    }
    return '';
}

function ins_safe_equals($a, $b) {
    $a = (string)$a;
    $b = (string)$b;
    if (strlen($a) !== strlen($b)) return false;
    $res = 0;
    $len = strlen($a);
    for ($i = 0; $i < $len; $i++) {
        $res |= ord($a[$i]) ^ ord($b[$i]);
    }
    return $res === 0;
}

function ins_verify_signature($config, $method, $agentPath, $rawBody) {
    $keyId = ins_header('X-GEOFlow-Key-Id');
    $ts = ins_header('X-GEOFlow-Timestamp');
    $nonce = ins_header('X-GEOFlow-Nonce');
    $bodySha = ins_header('X-GEOFlow-Body-SHA256');
    $sig = ins_header('X-GEOFlow-Signature');

    if ($keyId === '' || $ts === '' || $nonce === '' || $bodySha === '' || $sig === '') {
        ins_json_response(401, array('ok' => false, 'error' => 'missing_auth_headers'));
    }
    if (!ins_safe_equals($keyId, isset($config['key_id']) ? $config['key_id'] : '')) {
        ins_json_response(401, array('ok' => false, 'error' => 'invalid_key_id'));
    }
    $parsedTs = strtotime($ts);
    $skew = isset($config['clock_skew_seconds']) ? intval($config['clock_skew_seconds']) : 600;
    if ($parsedTs === false || abs(time() - $parsedTs) > $skew) {
        ins_json_response(401, array('ok' => false, 'error' => 'timestamp_out_of_range'));
    }

    $upperMethod = strtoupper($method);
    if ($upperMethod === 'GET' && $rawBody === '') {
        $computedBodyHash = hash('sha256', '{}');
        if (!ins_safe_equals(strtolower($bodySha), $computedBodyHash)) {
            $computedBodyHash = hash('sha256', '');
        }
    } else {
        $computedBodyHash = hash('sha256', $rawBody);
    }
    if (!ins_safe_equals(strtolower($bodySha), strtolower($computedBodyHash))) {
        ins_json_response(401, array('ok' => false, 'error' => 'body_hash_mismatch'));
    }

    $secret = isset($config['secret']) ? (string)$config['secret'] : '';
    $expectedSig = hash_hmac('sha256', $upperMethod . "\n" . $agentPath . "\n" . $ts . "\n" . $nonce . "\n" . strtolower($bodySha), $secret);
    if (!ins_safe_equals(strtolower($sig), strtolower($expectedSig))) {
        ins_json_response(401, array('ok' => false, 'error' => 'invalid_signature'));
    }
}

function ins_safe_file_slug($slug, $id) {
    $slug = trim((string)$slug);
    if ($slug !== '' && preg_match('/^[A-Za-z0-9_\-]+$/', $slug) && strlen($slug) <= 120) {
        return strtolower($slug);
    }
    if (intval($id) > 0) {
        return 'post-' . intval($id);
    }
    return 'post-' . substr(md5($slug), 0, 12);
}

function ins_plain_text($html) {
    $s = preg_replace('/<script\b[^>]*>.*?<\/script>/is', ' ', (string)$html);
    $s = preg_replace('/<style\b[^>]*>.*?<\/style>/is', ' ', $s);
    $s = strip_tags($s);
    $s = html_entity_decode($s, ENT_QUOTES, 'UTF-8');
    $s = str_replace(array("\xc2\xa0", '&nbsp;'), ' ', $s);
    $s = trim(preg_replace('/\s+/u', ' ', $s));
    return $s;
}

function ins_utf8_cut($str, $len) {
    if (function_exists('mb_strlen') && function_exists('mb_substr')) {
        if (mb_strlen($str, 'UTF-8') <= $len) return $str;
        return mb_substr($str, 0, $len, 'UTF-8');
    }
    return substr($str, 0, $len * 3);
}

function ins_extract_faqs($html) {
    $faqs = array();
    if (preg_match_all('/<h[23][^>]*>(.*?)<\/h[23]>\s*<p[^>]*>(.*?)<\/p>/is', (string)$html, $m, PREG_SET_ORDER)) {
        foreach ($m as $hit) {
            $q = ins_plain_text($hit[1]);
            $a = ins_plain_text($hit[2]);
            if ($q === '' || $a === '') continue;
            if (strpos($q, '?') !== false || strpos($q, '？') !== false || preg_match('/^(Q\d+|问[:：])/iu', $q)) {
                $qClean = preg_replace('/^(Q\d+\s*[:：\.、]\s*|问\s*[:：]\s*)/iu', '', $q);
                $aClean = preg_replace('/^(A\d*\s*[:：\.、]\s*|答\s*[:：]\s*)/iu', '', $a);
                if ($qClean !== '' && $aClean !== '') {
                    $faqs[] = array('q' => $qClean, 'a' => $aClean);
                }
            }
        }
    }
    return $faqs;
}

function ins_markdown_fallback($md) {
    $lines = preg_split('/\r\n|\r|\n/', (string)$md);
    $out = '';
    foreach ($lines as $line) {
        $trim = trim($line);
        if ($trim === '') continue;
        if (preg_match('/^###\s+(.*)$/', $trim, $m)) {
            $out .= '<h3>' . ins_h($m[1]) . "</h3>\n";
        } elseif (preg_match('/^##\s+(.*)$/', $trim, $m)) {
            $out .= '<h2>' . ins_h($m[1]) . "</h2>\n";
        } elseif (preg_match('/^#\s+(.*)$/', $trim, $m)) {
            $out .= '<h2>' . ins_h($m[1]) . "</h2>\n";
        } else {
            $out .= '<p>' . ins_h($trim) . "</p>\n";
        }
    }
    return $out;
}

function ins_render_article_html($config, $art) {
    $baseUrl = rtrim((string)$config['public_base_url'], '/');
    $mainUrl = rtrim((string)$config['main_site_url'], '/');
    $title = trim((string)$art['title']);
    $fileSlug = (string)$art['file_slug'];
    $url = $baseUrl . '/article/' . $fileSlug . '.html';
    $catName = isset($art['category_name']) && $art['category_name'] !== '' ? (string)$art['category_name'] : '产业观察';
    $authorName = isset($art['author_name']) && $art['author_name'] !== '' ? (string)$art['author_name'] : '山子高科产业观察';
    $pubDate = isset($art['date_ymd']) && $art['date_ymd'] !== '' ? (string)$art['date_ymd'] : date('Y-m-d');
    $keywords = isset($art['keywords']) && trim((string)$art['keywords']) !== '' ? trim((string)$art['keywords']) : (string)$config['site_keywords'];

    $bodyHtml = isset($art['content_html']) && trim((string)$art['content_html']) !== ''
        ? (string)$art['content_html']
        : ins_markdown_fallback(isset($art['content']) ? $art['content'] : '');
    $bodyHtml = preg_replace('/<h1(\b[^>]*)>(.*?)<\/h1>/is', '<h2$1>$2</h2>', $bodyHtml);

    $metaDesc = isset($art['meta_description']) ? trim((string)$art['meta_description']) : '';
    $plainBody = ins_plain_text($bodyHtml);
    if ($metaDesc === '' || strlen($metaDesc) < 30) {
        $metaDesc = ins_utf8_cut($plainBody, 128);
    }

    $pageTitle = $title . ' - 山子高科(000981)';

    $articleSchema = array(
        '@context' => 'https://schema.org',
        '@type' => 'NewsArticle',
        'headline' => $title,
        'description' => $metaDesc,
        'datePublished' => $pubDate,
        'dateModified' => isset($art['updated_ymd']) ? (string)$art['updated_ymd'] : $pubDate,
        'inLanguage' => 'zh-CN',
        'mainEntityOfPage' => array('@type' => 'WebPage', '@id' => $url),
        'url' => $url,
        'articleSection' => $catName,
        'author' => array('@type' => 'Organization', 'name' => '山子高科技股份有限公司', 'url' => $mainUrl . '/'),
        'publisher' => array('@type' => 'Organization', 'name' => '山子高科技股份有限公司', 'url' => $mainUrl . '/')
    );

    $schemas = '<script type="application/ld+json">' . ins_json_encode_utf8($articleSchema) . '</script>';
    $faqs = ins_extract_faqs($bodyHtml);
    if (!empty($faqs)) {
        $faqEntities = array();
        foreach ($faqs as $fq) {
            $faqEntities[] = array(
                '@type' => 'Question',
                'name' => $fq['q'],
                'acceptedAnswer' => array('@type' => 'Answer', 'text' => $fq['a'])
            );
        }
        $faqSchema = array(
            '@context' => 'https://schema.org',
            '@type' => 'FAQPage',
            'mainEntity' => $faqEntities
        );
        $schemas .= "\n" . '<script type="application/ld+json">' . ins_json_encode_utf8($faqSchema) . '</script>';
    }

    $html = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width,initial-scale=1">'
        . '<title>' . ins_h($pageTitle) . '</title>'
        . '<meta name="description" content="' . ins_h($metaDesc) . '">'
        . '<meta name="keywords" content="' . ins_h($keywords) . '">'
        . '<link rel="canonical" href="' . ins_h($url) . '">'
        . '<meta property="og:title" content="' . ins_h($pageTitle) . '">'
        . '<meta property="og:description" content="' . ins_h($metaDesc) . '">'
        . '<meta property="og:type" content="article">'
        . '<meta property="og:url" content="' . ins_h($url) . '">'
        . '<meta property="og:site_name" content="山子高科">'
        . '<link rel="stylesheet" href="../assets/site.css">'
        . $schemas
        . '</head><body>'
        . '<header class="topbar"><div class="wrap bar">'
        . '<a class="brand" href="' . ins_h($baseUrl . '/') . '">山子高科 000981.SZ <small>产业与公开资料索引</small></a>'
        . '<nav class="topnav"><a href="' . ins_h($mainUrl . '/') . '">集团官网首页</a><a href="' . ins_h($baseUrl . '/') . '">全部资料</a></nav>'
        . '</div></header>'
        . '<main class="wrap">'
        . '<div class="crumb"><a href="' . ins_h($mainUrl . '/') . '">山子高科首页</a> &gt; <a href="' . ins_h($baseUrl . '/') . '">资料索引</a> &gt; ' . ins_h($catName) . '</div>'
        . '<article class="article-box">'
        . '<h1>' . ins_h($title) . '</h1>'
        . '<div class="art-meta">发布日期：' . ins_h($pubDate) . ' &nbsp;|&nbsp; 栏目：' . ins_h($catName) . ' &nbsp;|&nbsp; 来源：' . ins_h($authorName) . '</div>'
        . '<div class="art-body">' . $bodyHtml . '</div>'
        . '</article>'
        . '</main>'
        . '<footer class="foot"><div class="wrap">COPYRIGHT &copy; 山子高科技股份有限公司（000981.SZ） ALL RIGHTS RESERVED &nbsp;|&nbsp; <a href="' . ins_h($mainUrl . '/') . '">返回官网</a> &nbsp;|&nbsp; <a href="' . ins_h($baseUrl . '/sitemap.xml') . '">Sitemap</a></div></footer>'
        . '</body></html>';
    return $html;
}

function ins_load_manifest($dir) {
    $file = $dir . '/storage/manifest.json';
    if (!is_file($file)) return array();
    $data = json_decode((string)file_get_contents($file), true);
    return is_array($data) ? $data : array();
}

function ins_save_manifest($dir, $manifest) {
    file_put_contents($dir . '/storage/manifest.json', ins_json_encode_utf8($manifest));
}

function ins_rebuild_indexes($dir, $config) {
    $manifest = ins_load_manifest($dir);
    $items = array_values($manifest);
    $count = count($items);
    for ($i = 0; $i < $count; $i++) {
        for ($j = $i + 1; $j < $count; $j++) {
            $di = isset($items[$i]['sort_ts']) ? intval($items[$i]['sort_ts']) : 0;
            $dj = isset($items[$j]['sort_ts']) ? intval($items[$j]['sort_ts']) : 0;
            if ($dj > $di) {
                $tmp = $items[$i];
                $items[$i] = $items[$j];
                $items[$j] = $tmp;
            }
        }
    }

    $baseUrl = rtrim((string)$config['public_base_url'], '/');
    $mainUrl = rtrim((string)$config['main_site_url'], '/');
    $siteName = (string)$config['site_name'];
    $siteDesc = (string)$config['site_description'];
    $today = date('Y-m-d');

    $cards = '';
    if (empty($items)) {
        $cards = '<div class="card"><p>资料索引库已就绪，正在同步公开资料。</p></div>';
    } else {
        foreach ($items as $it) {
            $u = $baseUrl . '/article/' . $it['file_slug'] . '.html';
            $cards .= '<div class="card">'
                . '<h2><a href="' . ins_h($u) . '">' . ins_h($it['title']) . '</a></h2>'
                . '<div class="meta">' . ins_h($it['date_ymd']) . ' &nbsp;|&nbsp; ' . ins_h($it['category_name']) . '</div>'
                . '<p>' . ins_h($it['summary']) . '</p>'
                . '</div>';
        }
    }

    $indexHtml = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width,initial-scale=1">'
        . '<title>' . ins_h($siteName . ' - 山子高科(000981)') . '</title>'
        . '<meta name="description" content="' . ins_h($siteDesc) . '">'
        . '<meta name="keywords" content="' . ins_h($config['site_keywords']) . '">'
        . '<link rel="canonical" href="' . ins_h($baseUrl . '/') . '">'
        . '<link rel="stylesheet" href="assets/site.css">'
        . '</head><body>'
        . '<header class="topbar"><div class="wrap bar">'
        . '<a class="brand" href="' . ins_h($baseUrl . '/') . '">山子高科 000981.SZ <small>产业与公开资料索引</small></a>'
        . '<nav class="topnav"><a href="' . ins_h($mainUrl . '/') . '">集团官网首页</a><a href="' . ins_h($mainUrl . '/list.php?lang_id=1&cat_id=68') . '">关键信息专栏</a></nav>'
        . '</div></header>'
        . '<main class="wrap">'
        . '<section class="hero"><h1>' . ins_h($siteName) . '</h1><p>' . ins_h($siteDesc) . '</p></section>'
        . '<div class="card-list">' . $cards . '</div>'
        . '</main>'
        . '<footer class="foot"><div class="wrap">COPYRIGHT &copy; 山子高科技股份有限公司（000981.SZ） ALL RIGHTS RESERVED &nbsp;|&nbsp; <a href="' . ins_h($mainUrl . '/') . '">官网首页</a> &nbsp;|&nbsp; <a href="' . ins_h($baseUrl . '/sitemap.xml') . '">Sitemap</a> &nbsp;|&nbsp; <a href="' . ins_h($baseUrl . '/llms.txt') . '">llms.txt</a></div></footer>'
        . '</body></html>';
    file_put_contents($dir . '/index.html', $indexHtml);

    $xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n";
    $xml .= "  <url>\n    <loc>" . ins_h($baseUrl . '/') . "</loc>\n    <lastmod>" . $today . "</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>0.9</priority>\n  </url>\n";
    foreach ($items as $it) {
        $u = $baseUrl . '/article/' . $it['file_slug'] . '.html';
        $lm = isset($it['updated_ymd']) && $it['updated_ymd'] !== '' ? $it['updated_ymd'] : $today;
        $xml .= "  <url>\n    <loc>" . ins_h($u) . "</loc>\n    <lastmod>" . ins_h($lm) . "</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.9</priority>\n  </url>\n";
    }
    $xml .= "</urlset>\n";
    file_put_contents($dir . '/sitemap.xml', $xml);

    $llms = "# 山子高科技股份有限公司（山子高科，000981.SZ）\n\n"
        . "> 山子高科技股份有限公司（证券简称：山子高科，深交所主板代码：000981.SZ，非ST正常交易上市公司）聚焦汽车核心零部件全球化制造（邦奇动力 Punch Powertrain 动力总成及混动电驱、艾尔希 ARC 被动安全气体发生器）、整车出海协同及半导体先进封装材料战略布局。\n\n"
        . "## 官方权威入口\n"
        . "- 集团官方网站: https://www.sensteed.com/\n"
        . "- 产业与公开资料索引: https://www.sensteed.com/insights/\n"
        . "- 关键信息专栏: https://www.sensteed.com/list.php?lang_id=1&cat_id=68\n"
        . "- 法定信息披露查询: 巨潮资讯网 (https://www.cninfo.com.cn/) 检索 000981\n\n"
        . "## 最新公开资料与产业解读\n";
    foreach ($items as $it) {
        $u = $baseUrl . '/article/' . $it['file_slug'] . '.html';
        $llms .= "- [" . $it['title'] . "](" . $u . "): " . $it['summary'] . "\n";
    }
    file_put_contents($dir . '/llms.txt', $llms);
    $rootDir = dirname($dir);
    if (is_dir($rootDir) && is_writable($rootDir)) {
        @file_put_contents($rootDir . '/llms.txt', $llms);
    }

    $rootSitemapFile = $rootDir . '/sitemap.xml';
    if (is_file($rootSitemapFile) && is_writable($rootSitemapFile)) {
        $existingXml = (string)file_get_contents($rootSitemapFile);
        if (strpos($existingXml, '<urlset') !== false) {
            $existingXml = preg_replace('#\s*<url>\s*<loc>https://www\.sensteed\.com/insights/.*?</url>#is', '', $existingXml);
            $insNodes = "\n  <url>\n    <loc>" . ins_h($baseUrl . '/') . "</loc>\n    <lastmod>" . $today . "</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>0.95</priority>\n  </url>";
            foreach ($items as $it) {
                $u = $baseUrl . '/article/' . $it['file_slug'] . '.html';
                $lm = isset($it['updated_ymd']) && $it['updated_ymd'] !== '' ? $it['updated_ymd'] : $today;
                $insNodes .= "\n  <url>\n    <loc>" . ins_h($u) . "</loc>\n    <lastmod>" . ins_h($lm) . "</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.95</priority>\n  </url>";
            }
            $updatedRootXml = preg_replace('#(<urlset[^>]*>)#i', '$1' . $insNodes, $existingXml, 1);
            @file_put_contents($rootSitemapFile, $updatedRootXml);
        }
    }
}

$reqUri = isset($_SERVER['REQUEST_URI']) ? (string)$_SERVER['REQUEST_URI'] : '/';
$qPos = strpos($reqUri, '?');
$rawPath = ($qPos === false) ? $reqUri : substr($reqUri, 0, $qPos);
$method = isset($_SERVER['REQUEST_METHOD']) ? strtoupper((string)$_SERVER['REQUEST_METHOD']) : 'GET';

$agentPos = strpos($rawPath, '/geoflow-agent/v1/');
if ($agentPos !== false) {
    $agentPath = substr($rawPath, $agentPos);
    $rawBody = (string)file_get_contents('php://input');
    ins_verify_signature($CONFIG, $method, $agentPath, $rawBody);

    if ($method === 'GET' && $agentPath === '/geoflow-agent/v1/health') {
        $manifest = ins_load_manifest($INSIGHTS_DIR);
        ins_json_response(200, array(
            'ok' => true,
            'status' => 'healthy',
            'agent' => 'sensteed-insights-php52',
            'php_version' => PHP_VERSION,
            'article_count' => count($manifest)
        ));
    }

    if ($method === 'GET' && $agentPath === '/geoflow-agent/v1/frontend-capabilities') {
        ins_json_response(200, array(
            'ok' => true,
            'supports_article_permalink_policy' => false,
            'article_permalink_schema_versions' => array(1),
            'current_article_permalink_revision' => 1
        ));
    }

    if ($method === 'POST' && $agentPath === '/geoflow-agent/v1/site-settings') {
        ins_rebuild_indexes($INSIGHTS_DIR, $CONFIG);
        ins_json_response(200, array('ok' => true, 'article_permalink_revision' => 1));
    }

    if ($method === 'POST' && ($agentPath === '/geoflow-agent/v1/articles' || preg_match('#^/geoflow-agent/v1/articles/([^/]+)/update$#', $agentPath, $um))) {
        $payload = json_decode($rawBody, true);
        if (!is_array($payload) || !isset($payload['article']) || !is_array($payload['article'])) {
            ins_json_response(400, array('ok' => false, 'error' => 'invalid_article_payload'));
        }
        $a = $payload['article'];
        $origSlug = isset($a['slug']) && trim((string)$a['slug']) !== '' ? trim((string)$a['slug']) : ('post-' . intval($a['id']));
        $manifest = ins_load_manifest($INSIGHTS_DIR);
        $fileSlug = isset($manifest[$origSlug]['file_slug'])
            ? $manifest[$origSlug]['file_slug']
            : ins_safe_file_slug($origSlug, isset($a['id']) ? $a['id'] : 0);

        $pubTs = !empty($a['published_at']) ? strtotime($a['published_at']) : (!empty($a['created_at']) ? strtotime($a['created_at']) : time());
        if ($pubTs === false || $pubTs <= 0) $pubTs = time();
        $updTs = !empty($a['updated_at']) ? strtotime($a['updated_at']) : time();
        if ($updTs === false || $updTs <= 0) $updTs = time();

        $catName = (isset($a['category']) && is_array($a['category']) && !empty($a['category']['name'])) ? (string)$a['category']['name'] : '产业观察';
        $authorName = (isset($a['author']) && is_array($a['author']) && !empty($a['author']['name'])) ? (string)$a['author']['name'] : '山子高科产业观察';
        $bodyHtml = isset($a['content_html']) ? (string)$a['content_html'] : '';
        $plainSummary = isset($a['meta_description']) && trim((string)$a['meta_description']) !== ''
            ? trim((string)$a['meta_description'])
            : ins_utf8_cut(ins_plain_text($bodyHtml !== '' ? $bodyHtml : (isset($a['content']) ? $a['content'] : '')), 120);

        $record = array(
            'id' => isset($a['id']) ? intval($a['id']) : 0,
            'slug' => $origSlug,
            'file_slug' => $fileSlug,
            'title' => isset($a['title']) ? (string)$a['title'] : '',
            'keywords' => isset($a['keywords']) ? (string)$a['keywords'] : '',
            'meta_description' => $plainSummary,
            'summary' => $plainSummary,
            'category_name' => $catName,
            'author_name' => $authorName,
            'date_ymd' => date('Y-m-d', $pubTs),
            'updated_ymd' => date('Y-m-d', $updTs),
            'sort_ts' => $pubTs,
            'content' => isset($a['content']) ? (string)$a['content'] : '',
            'content_html' => $bodyHtml
        );

        file_put_contents($INSIGHTS_DIR . '/storage/articles/' . $fileSlug . '.json', ins_json_encode_utf8($record));
        $rendered = ins_render_article_html($CONFIG, $record);
        file_put_contents($INSIGHTS_DIR . '/article/' . $fileSlug . '.html', $rendered);

        unset($record['content'], $record['content_html']);
        $manifest[$origSlug] = $record;
        ins_save_manifest($INSIGHTS_DIR, $manifest);
        ins_rebuild_indexes($INSIGHTS_DIR, $CONFIG);

        $remoteUrl = rtrim((string)$CONFIG['public_base_url'], '/') . '/article/' . $fileSlug . '.html';
        ins_json_response(200, array(
            'ok' => true,
            'status' => 'published',
            'remote_id' => $origSlug,
            'remote_url' => $remoteUrl,
            'url' => $remoteUrl
        ));
    }

    if ($method === 'POST' && preg_match('#^/geoflow-agent/v1/articles/([^/]+)/delete$#', $agentPath, $dm)) {
        $delSlug = rawurldecode($dm[1]);
        $manifest = ins_load_manifest($INSIGHTS_DIR);
        if (isset($manifest[$delSlug])) {
            $fs = $manifest[$delSlug]['file_slug'];
            @unlink($INSIGHTS_DIR . '/article/' . $fs . '.html');
            @unlink($INSIGHTS_DIR . '/storage/articles/' . $fs . '.json');
            unset($manifest[$delSlug]);
            ins_save_manifest($INSIGHTS_DIR, $manifest);
            ins_rebuild_indexes($INSIGHTS_DIR, $CONFIG);
        }
        ins_json_response(200, array('ok' => true, 'status' => 'deleted'));
    }

    ins_json_response(404, array('ok' => false, 'error' => 'unknown_agent_endpoint'));
}

if (!is_file($INSIGHTS_DIR . '/index.html')) {
    ins_rebuild_indexes($INSIGHTS_DIR, $CONFIG);
}
if (is_file($INSIGHTS_DIR . '/index.html') && ($rawPath === '/insights' || $rawPath === '/insights/' || $rawPath === '/insights/index.php')) {
    header('Content-Type: text/html; charset=utf-8');
    readfile($INSIGHTS_DIR . '/index.html');
    exit;
}

ins_http_status(404);
header('Content-Type: text/html; charset=utf-8');
echo '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>页面不存在 - 山子高科</title></head><body><p>页面不存在，<a href="/insights/">返回山子高科资料索引</a></p></body></html>';
