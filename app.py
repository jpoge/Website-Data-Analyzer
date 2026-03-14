import re
import json
import time
from collections import Counter
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
    'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
    'his', 'its', 'our', 'their', 'what', 'which', 'who', 'when', 'where',
    'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most',
    'other', 'some', 'such', 'no', 'not', 'only', 'same', 'so', 'than',
    'too', 'very', 's', 't', 'just', 'as', 'if', 'then', 'now', 'also',
    'get', 'got', 'like', 'one', 'two', 'new', 'use', 'used', 'using',
    'back', 'after', 'before', 'well', 'way', 'even', 'still', 'many',
    'much', 'any', 'here', 'there', 'www', 'com', 'http', 'https', 'amp',
    'utm', 'via', 'per', 'nbsp', 'page', 'site', 'web', 'click', 'read',
    'see', 'go', 'make', 'take', 'know', 'think', 'come', 'want', 'look',
    'need', 'say', 'said', 'time', 'year', 'day', 'people', 'home', 'work',
    'us', 'its', 'been', 'over', 'also', 'first', 'last', 'long', 'great',
    'little', 'own', 'right', 'big', 'high', 'low', 'next', 'never',
    'always', 'three', 'four', 'five', 'while', 'since', 'without', 'under',
    'between', 'through', 'during', 'part', 'place', 'world', 'point',
}

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def fetch_page(url, timeout=15):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.text, resp.url
    except Exception as e:
        return None, str(e)


def extract_posts(soup, base_url):
    """Extract individual posts/articles from page."""
    posts = []
    selectors = [
        'article',
        '[class*="post-item"]',
        '[class*="blog-post"]',
        '[class*="article-item"]',
        '[class*="entry"]',
        '[class*="list-item"]',
        '.thread-item',
        '.comment',
        '.card',
    ]

    for selector in selectors:
        try:
            items = soup.select(selector)
        except Exception:
            continue
        if len(items) >= 2:
            for item in items[:60]:
                text = item.get_text(separator=' ', strip=True)
                if len(text) < 50:
                    continue

                post = {
                    'text': text[:3000],
                    'links': [],
                    'title': '',
                    'date': '',
                    'author': '',
                    'tags': [],
                    'word_count': len(text.split()),
                }

                # Title
                for tag in ['h1', 'h2', 'h3', 'h4']:
                    h = item.find(tag)
                    if h:
                        post['title'] = h.get_text(strip=True)[:200]
                        break

                # Links
                post['links'] = [
                    urljoin(base_url, a['href'])
                    for a in item.find_all('a', href=True)
                ][:10]

                # Date — prefer <time datetime="...">
                for t in item.find_all('time'):
                    dt = t.get('datetime', '') or t.get_text(strip=True)
                    if dt:
                        post['date'] = dt[:50]
                        break
                if not post['date']:
                    date_patterns = [
                        r'\d{4}-\d{2}-\d{2}',
                        r'\d{1,2}/\d{1,2}/\d{2,4}',
                        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}',
                    ]
                    for pattern in date_patterns:
                        m = re.search(pattern, text, re.IGNORECASE)
                        if m:
                            post['date'] = m.group(0)
                            break

                # Author
                for cls in ['author', 'byline', 'by-line', 'by', 'writer', 'username', 'user']:
                    auth = item.find(class_=re.compile(cls, re.I))
                    if auth:
                        post['author'] = auth.get_text(strip=True)[:100]
                        break

                # Tags
                for cls in ['tag', 'label', 'category', 'badge', 'topic']:
                    tags = item.find_all(class_=re.compile(cls, re.I))
                    post['tags'] = [
                        t.get_text(strip=True)
                        for t in tags[:10]
                        if 1 < len(t.get_text(strip=True)) < 50
                    ]
                    if post['tags']:
                        break

                posts.append(post)

            if posts:
                break

    return posts


def extract_links(soup, base_url):
    """Extract and categorize all links."""
    base_domain = urlparse(base_url).netloc
    internal = []
    external = []
    by_domain = Counter()

    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:'):
            continue
        try:
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
        except Exception:
            continue
        if parsed.scheme not in ('http', 'https'):
            continue

        text = a.get_text(strip=True)[:120]
        domain = parsed.netloc
        by_domain[domain] += 1

        if domain == base_domain or domain.endswith('.' + base_domain):
            internal.append({'url': full_url, 'text': text})
        else:
            external.append({'url': full_url, 'text': text, 'domain': domain})

    return {'internal': internal, 'external': external, 'by_domain': by_domain}


def extract_metadata(soup, url):
    meta = {
        'title': '',
        'description': '',
        'keywords': [],
        'og': {},
        'canonical': url,
    }

    title_tag = soup.find('title')
    if title_tag:
        meta['title'] = title_tag.get_text(strip=True)

    for m in soup.find_all('meta'):
        name = m.get('name', m.get('property', '')).lower()
        content = m.get('content', '')
        if name == 'description':
            meta['description'] = content[:500]
        elif name == 'keywords':
            meta['keywords'] = [k.strip() for k in content.split(',')][:20]
        elif name.startswith('og:'):
            meta['og'][name[3:]] = content[:200]

    canonical = soup.find('link', rel='canonical')
    if canonical:
        meta['canonical'] = canonical.get('href', url)

    return meta


def extract_headings(soup):
    headings = []
    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        for h in soup.find_all(tag):
            text = h.get_text(strip=True)
            if text and len(text) > 2:
                headings.append({'level': int(tag[1]), 'text': text[:200]})
    return headings


def tokenize(text):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return [w for w in words if w not in STOP_WORDS]


def extract_bigrams(words):
    return [(words[i], words[i + 1]) for i in range(len(words) - 1)]


def detect_site_type(soup, url, posts):
    scores = {
        'blog': 0, 'forum': 0, 'news': 0,
        'ecommerce': 0, 'social': 0, 'wiki': 0,
        'docs': 0, 'portfolio': 0,
    }
    url_lower = url.lower()

    if any(x in url_lower for x in ['blog', 'post', 'article']):
        scores['blog'] += 3
    if any(x in url_lower for x in ['forum', 'board', 'thread', 'discuss']):
        scores['forum'] += 3
    if any(x in url_lower for x in ['shop', 'store', 'product', 'cart']):
        scores['ecommerce'] += 3
    if any(x in url_lower for x in ['wiki', 'docs', 'documentation']):
        scores['wiki'] += 3
        scores['docs'] += 2
    if any(x in url_lower for x in ['news', 'press', 'media', 'daily']):
        scores['news'] += 3

    if soup.find_all('article'):
        scores['blog'] += 1
    if soup.find_all(class_=re.compile(r'(reply|thread-count|post-count)', re.I)):
        scores['forum'] += 2
    if soup.find_all(class_=re.compile(r'(price|add-to-cart|buy-now)', re.I)):
        scores['ecommerce'] += 2
    if soup.find_all(class_=re.compile(r'(tweet|like-count|retweet|follow)', re.I)):
        scores['social'] += 2

    if len(posts) >= 2:
        has_dates = sum(1 for p in posts if p['date'])
        has_authors = sum(1 for p in posts if p['author'])
        if has_dates > len(posts) * 0.3:
            scores['blog'] += 1
            scores['news'] += 1
        if has_authors > len(posts) * 0.3:
            scores['blog'] += 1
            scores['forum'] += 1

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'general'


POSITIVE_WORDS = {
    'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic',
    'love', 'best', 'awesome', 'nice', 'perfect', 'beautiful', 'happy',
    'helpful', 'easy', 'fast', 'better', 'top', 'free', 'win', 'success',
    'useful', 'powerful', 'smart', 'clean', 'simple', 'fun', 'impressive',
    'innovative', 'elegant', 'recommend', 'outstanding', 'superb', 'enjoy',
}
NEGATIVE_WORDS = {
    'bad', 'terrible', 'awful', 'horrible', 'worst', 'hate', 'ugly',
    'slow', 'broken', 'failed', 'error', 'bug', 'problem', 'issue',
    'wrong', 'difficult', 'hard', 'expensive', 'annoying', 'useless',
    'poor', 'weak', 'missing', 'lack', 'crash', 'spam', 'frustrating',
    'disappointing', 'confusing', 'complicated', 'unreliable', 'waste',
}


def classify_sentiment(text):
    words = set(re.findall(r'\b[a-z]+\b', text.lower()))
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    if pos + neg == 0:
        return 'neutral'
    ratio = pos / (pos + neg)
    if ratio > 0.6:
        return 'positive'
    if ratio < 0.4:
        return 'negative'
    return 'mixed'


def extract_years(text):
    return re.findall(r'\b(20[0-2]\d|199\d)\b', text)


def analyze_patterns(data):
    all_text = data.get('all_text', '')
    posts = data.get('posts', [])
    links = data.get('links', {})
    headings = data.get('headings', [])
    metadata = data.get('metadata', {})

    words = tokenize(all_text)
    word_counts = Counter(words)
    bigram_counts = Counter(extract_bigrams(words))

    # Tag & author frequency
    all_tags = []
    all_authors = []
    sentiments = Counter()
    lengths = []

    for post in posts:
        all_tags.extend(post.get('tags', []))
        if post.get('author'):
            all_authors.append(post['author'])
        sentiments[classify_sentiment(post['text'])] += 1
        lengths.append(post.get('word_count', len(post['text'].split())))

    tag_counts = Counter(all_tags)
    author_counts = Counter(all_authors)

    # Year activity
    year_counts = Counter(extract_years(all_text))
    for post in posts:
        year_counts.update(extract_years(post.get('date', '')))

    domain_counts = links.get('by_domain', Counter())
    base_domain = urlparse(data.get('url', '')).netloc

    # --- Build interesting findings ---
    findings = []

    if word_counts:
        top5 = word_counts.most_common(5)
        findings.append({
            'type': 'top_keywords',
            'title': f'Top Keyword: "{top5[0][0]}"',
            'detail': f'Appears {top5[0][1]} times. Top 5 terms: {", ".join(f"{w} ({c})" for w, c in top5)}',
            'importance': 'high',
            'icon': '🔑',
        })

    if bigram_counts:
        top = bigram_counts.most_common(1)[0]
        phrase = f"{top[0][0]} {top[0][1]}"
        top5b = [f"{b[0]} {b[1]} ({c})" for b, c in bigram_counts.most_common(5)]
        findings.append({
            'type': 'top_phrases',
            'title': f'Key Phrase: "{phrase}"',
            'detail': f'Repeated {top[1]}×. Top phrases: {", ".join(top5b)}',
            'importance': 'high',
            'icon': '💬',
        })

    if author_counts:
        top_author = author_counts.most_common(1)[0]
        findings.append({
            'type': 'top_author',
            'title': f'Most Active Author: {top_author[0]}',
            'detail': (
                f'{top_author[0]} has {top_author[1]} post(s). '
                f'Total unique authors found: {len(author_counts)}.'
            ),
            'importance': 'medium',
            'icon': '✍️',
        })

    if tag_counts:
        top3 = tag_counts.most_common(3)
        findings.append({
            'type': 'popular_topics',
            'title': 'Most Popular Topics/Tags',
            'detail': f'{", ".join(f"{t} ({c})" for t, c in top3)}',
            'importance': 'medium',
            'icon': '🏷️',
        })

    total_s = sum(sentiments.values())
    if total_s > 0:
        dominant = sentiments.most_common(1)[0]
        pct = round(dominant[1] / total_s * 100)
        findings.append({
            'type': 'sentiment',
            'title': f'Tone: Mostly {dominant[0].capitalize()} ({pct}%)',
            'detail': (
                f'Positive: {sentiments["positive"]}, '
                f'Negative: {sentiments["negative"]}, '
                f'Mixed: {sentiments["mixed"]}, '
                f'Neutral: {sentiments["neutral"]} posts'
            ),
            'importance': 'medium',
            'icon': '😊' if dominant[0] == 'positive' else ('😟' if dominant[0] == 'negative' else '😐'),
        })

    ext_domain_counts = Counter(l['domain'] for l in links.get('external', []))
    if ext_domain_counts:
        top3e = ext_domain_counts.most_common(3)
        findings.append({
            'type': 'external_sources',
            'title': 'Most Referenced External Sites',
            'detail': f'{", ".join(f"{d} ({c} links)" for d, c in top3e)}',
            'importance': 'medium',
            'icon': '🔗',
        })

    if year_counts:
        top_years = year_counts.most_common(3)
        findings.append({
            'type': 'activity_years',
            'title': f'Peak Activity Year: {top_years[0][0]}',
            'detail': f'Year mentions: {", ".join(f"{y} ({c})" for y, c in top_years)}',
            'importance': 'low',
            'icon': '📅',
        })

    if lengths:
        avg_len = sum(lengths) // len(lengths)
        short = sum(1 for l in lengths if l < 50)
        medium = sum(1 for l in lengths if 50 <= l <= 200)
        long_ = sum(1 for l in lengths if l > 200)
        findings.append({
            'type': 'content_length',
            'title': f'Avg Post Length: {avg_len} words',
            'detail': (
                f'Short (<50w): {short}, Medium (50-200w): {medium}, Long (>200w): {long_}. '
                f'Range: {min(lengths)}–{max(lengths)} words.'
            ),
            'importance': 'low',
            'icon': '📏',
        })

    # Concentration pattern
    if words:
        top3_sum = sum(c for _, c in word_counts.most_common(3))
        concentration = top3_sum / len(words) * 100
        if concentration > 8:
            findings.append({
                'type': 'focused_content',
                'title': f'Highly Focused Content ({concentration:.1f}% top-3 density)',
                'detail': (
                    f'Top 3 keywords account for {concentration:.1f}% of all meaningful words — '
                    'this site has very concentrated topic coverage.'
                ),
                'importance': 'high',
                'icon': '🎯',
            })

    order = {'high': 0, 'medium': 1, 'low': 2}
    findings.sort(key=lambda x: order.get(x['importance'], 3))

    return {
        'stats': {
            'total_words': len(words),
            'unique_words': len(word_counts),
            'posts_found': len(posts),
            'internal_links': len(links.get('internal', [])),
            'external_links': len(links.get('external', [])),
            'headings_found': len(headings),
            'site_type': data.get('site_type', 'general'),
            'page_title': metadata.get('title', ''),
            'description': metadata.get('description', ''),
            'authors_found': len(author_counts),
            'tags_found': len(tag_counts),
        },
        'word_freq': [{'word': w, 'count': c} for w, c in word_counts.most_common(25)],
        'bigram_freq': [
            {'phrase': f"{b[0]} {b[1]}", 'count': c}
            for b, c in bigram_counts.most_common(15)
        ],
        'link_domains': [
            {'domain': d, 'count': c}
            for d, c in domain_counts.most_common(12)
            if d
        ],
        'tag_freq': [{'tag': t, 'count': c} for t, c in tag_counts.most_common(20)],
        'author_freq': [{'author': a, 'count': c} for a, c in author_counts.most_common(10)],
        'year_activity': [
            {'year': y, 'count': c}
            for y, c in sorted(year_counts.items())
            if y
        ],
        'sentiment': dict(sentiments),
        'interesting_findings': findings,
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/scrape', methods=['POST'])
def scrape_endpoint():
    body = request.get_json(silent=True) or {}
    url = body.get('url', '').strip()
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    max_pages = max(1, min(int(body.get('max_pages', 1)), 5))

    try:
        html, final_url = fetch_page(url)
        if not html:
            return jsonify({'error': f'Could not fetch page: {final_url}'}), 400

        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style', 'noscript', 'iframe', 'svg']):
            tag.decompose()

        all_text = soup.get_text(separator=' ', strip=True)
        posts = extract_posts(soup, final_url)
        links = extract_links(soup, final_url)
        headings = extract_headings(soup)
        metadata = extract_metadata(soup, final_url)
        site_type = detect_site_type(soup, final_url, posts)

        crawled_urls = [final_url]

        if max_pages > 1:
            candidates = [
                l['url'] for l in links['internal']
                if l['url'] not in crawled_urls
            ][:max_pages - 1]

            for sub_url in candidates:
                time.sleep(0.4)
                sub_html, sub_final = fetch_page(sub_url)
                if not sub_html:
                    continue
                sub_soup = BeautifulSoup(sub_html, 'html.parser')
                for tag in sub_soup(['script', 'style', 'noscript', 'iframe']):
                    tag.decompose()
                all_text += ' ' + sub_soup.get_text(separator=' ', strip=True)
                posts.extend(extract_posts(sub_soup, sub_final))
                sub_links = extract_links(sub_soup, sub_final)
                links['internal'].extend(sub_links['internal'])
                links['external'].extend(sub_links['external'])
                links['by_domain'].update(sub_links['by_domain'])
                crawled_urls.append(sub_final)

        analysis = analyze_patterns({
            'url': final_url,
            'all_text': all_text,
            'posts': posts,
            'links': links,
            'headings': headings,
            'metadata': metadata,
            'site_type': site_type,
        })

        analysis['crawled_urls'] = crawled_urls
        analysis['sample_posts'] = [
            {k: v for k, v in p.items() if k != 'links'}
            for p in posts[:8]
        ]
        analysis['headings_sample'] = headings[:25]

        return jsonify({'success': True, 'data': analysis})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
