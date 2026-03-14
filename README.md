# DataScraper — Web Pattern Analyzer

A local webapp that scrapes any website, organizes the content, and surfaces the most interesting patterns for you to review.

## Features

- **Content extraction** — finds posts, articles, headings, links, authors, tags, and dates
- **Pattern analysis** — word/phrase frequency, sentiment, year activity, link destinations
- **Ranked findings** — key insights sorted by importance (high → medium → low)
- **Visual results** — bar charts, doughnut chart, tag pills, and author leaderboard
- **Multi-page crawl** — optionally follow internal links to scrape 1–5 pages per run

Works best on blogs, news sites, forums, and content-heavy pages. JavaScript-rendered SPAs may return limited results since the scraper uses static HTML parsing.

## Setup

**Requirements:** Python 3.8+

1. Clone or download this folder.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Start the server:
   ```
   python app.py
   ```
4. Open **http://localhost:5000** in your browser.

On Windows you can also double-click `run.bat` — it installs dependencies and starts the server automatically.

## Usage

1. Paste any URL into the input field (e.g. `https://news.ycombinator.com`).
2. Choose how many pages to crawl (1 = fast, 5 = thorough).
3. Click **Analyze Site** and wait a few seconds.

### Results breakdown

| Section | What it shows |
|---|---|
| **Overview** | Word count, posts found, link counts, authors, tags |
| **Interesting Findings** | Auto-generated insights ranked by importance |
| **Top Keywords** | Most frequent meaningful words |
| **Common Phrases** | Most repeated two-word combinations (bigrams) |
| **Content Sentiment** | Share of posts that are positive / negative / mixed / neutral |
| **Activity by Year** | Years most referenced in content and dates |
| **Link Destinations** | Most linked-to domains (internal + external) |
| **Topics & Tags** | Most used tags or categories found on the page |
| **Authors** | Most prolific authors/usernames detected |
| **Sample Posts** | Preview of extracted post content with metadata |
| **Page Structure** | Heading hierarchy (H1–H6) |

## Project structure

```
DataScraper/
├── app.py              # Flask backend — scraping, extraction, pattern analysis
├── requirements.txt    # Python dependencies
├── run.bat             # Windows one-click launcher
└── templates/
    └── index.html      # Frontend (Tailwind CSS + Chart.js, no build step)
```

## Dependencies

| Package | Purpose |
|---|---|
| Flask | Web server and routing |
| requests | HTTP fetching |
| beautifulsoup4 | HTML parsing |
| lxml | Fast HTML parser (used by BeautifulSoup) |

All frontend assets (Tailwind CSS, Chart.js) are loaded from CDN — no npm or build step needed.

## Limitations

- **Static HTML only** — sites that load content via JavaScript (React, Vue, etc.) will show limited results.
- **Rate limiting** — multi-page crawls add a 0.4s delay between requests to be polite. Some sites may still block scrapers.
- **Sentiment** — uses a simple word-matching approach, not a full NLP model. Results are approximate.
- **Post detection** — uses CSS selector heuristics to find post-like elements. Unusual site structures may yield fewer results.
