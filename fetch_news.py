import os
import json
import feedparser
from datetime import datetime, timezone
from pathlib import Path
from ai_analyzer import analyze_news

# ========== 国际财经新闻源配置 ==========
SOURCES = {
    "reuters": {
        "name": "Reuters",
        "name_cn": "路透社",
        "rss": "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en",
    },
    "bloomberg": {
        "name": "Bloomberg",
        "name_cn": "彭博社",
        "rss": "https://news.google.com/rss/search?q=site:bloomberg.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    },
    "wsj": {
        "name": "Wall Street Journal",
        "name_cn": "华尔街日报",
        "rss": "https://news.google.com/rss/search?q=site:wsj.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    },
    "ft": {
        "name": "Financial Times",
        "name_cn": "金融时报",
        "rss": "https://news.google.com/rss/search?q=site:ft.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    },
    "cnbc": {
        "name": "CNBC",
        "name_cn": "CNBC",
        "rss": "https://news.google.com/rss/search?q=site:cnbc.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    },
#   "scmp": {
#       "name": "South China Morning Post",
#       "name_cn": "南华早报",
#       "rss": "https://news.google.com/rss/search?q=site:scmp.com+when:1d&hl=en-US&gl=US&ceid=US:en",
#   },
    "BBC": {
        "name": "BBC",
        "name_cn": "BBC",
        "rss": "http://feeds.bbci.co.uk/news/rss.xml",
    },
    "NYT": {
        "name": "NYT",
        "name_cn": "纽约时报",
        "rss": "https://plink.anyfeeder.com/nytimes/cn",
    },
}

OUTPUT_DIR = Path(__file__).parent
MAX_ARTICLES = 10  # 每个源最多取多少条


def fetch_source(key, config):
    """抓取单个新闻源（带伪造 User-Agent，防止 RSS 请求被拦截）"""
    print(f"  正在抓取 {config['name_cn']} ({config['name']})...")
    articles = []
    
    try:
        # 设置请求头伪装成真实浏览器，避免 Google News RSS 请求超时或被拒
        request_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        feed = feedparser.parse(config["rss"], request_headers=request_headers)
        
        for entry in feed.entries[:MAX_ARTICLES]:
            title = entry.get("title", "").strip()
            # 自动清洗 Google News 等来源后缀（如 "Title - Reuters" -> "Title"）
            if " - " in title:
                title = title.rsplit(" - ", 1)[0].strip()

            articles.append({
                "title": title,
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", ""),
                "source": config["name_cn"],  # 👈 写入中文来源名，供 AI 和前端渲染识别
            })
            
        print(f"  ✅ {config['name_cn']}: 获取到 {len(articles)} 篇文章")
        return articles
    except Exception as e:
        print(f"  ❌ {config['name_cn']}: 抓取失败 - {e}")
        return []


def generate_markdown(all_data):
    """生成包含所有 8 个源的 Markdown 摘要文件"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M 北京时间")
    lines = [
        f"# 📰 每日全球财经与国际新闻摘要",
        f"**更新时间：{now}**",
        "",
        "> 来源：路透社 · 彭博社 · 华尔街日报 · 金融时报 · CNBC · 南华早报 · BBC · 纽约时报",
        "",
        "---",
        "",
    ]

    emoji_map = {
        "reuters": "🔴", 
        "bloomberg": "🟢", 
        "wsj": "🔵", 
        "ft": "🟡", 
        "cnbc": "🟠", 
#       "scmp": "🟣", 
        "BBC": "🇬🇧", 
        "NYT": "🇺🇸"
    }

    for key, articles in all_data.items():
        cfg = SOURCES[key]
        emoji = emoji_map.get(key, "📌")
        lines.append(f"## {emoji} {cfg['name_cn']} ({cfg['name']})")
        lines.append("")
        if not articles:
            lines.append("> ⚠️ 本次未获取到文章")
            lines.append("")
            continue
        for i, a in enumerate(articles, 1):
            title = a["title"]
            url = a["url"]
            lines.append(f"{i}. [{title}]({url})")
        lines.append("")

    lines.append("---")
    lines.append(f"*自动生成于 {now}*")
    return "\n".join(lines)


def main():
    print(f"🚀 开始抓取国际新闻... ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})")
    print()

    all_data = {}
    for key, config in SOURCES.items():
        articles = fetch_source(key, config)
        all_data[key] = articles

    # 1. 收集所有 8 个数据源的文章
    all_articles = []
    for key in SOURCES:
        all_articles.extend(all_data[key])

    # 2. 读取 Prompt
    prompt_path = OUTPUT_DIR / "ai_analysis_prompt.txt"
    prompt_text = ""
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read().strip()
        print(f"📄 成功读取分析 Prompt（共 {len(prompt_text)} 字）")
    else:
        print("⚠️ 未找到 ai_analysis_prompt.txt，将使用默认 Prompt 进行分析")

    print(f"开始对全部 8 个源共 {len(all_articles)} 篇文章进行 AI 分析与宏观总结...")

    # 3. 调用 AI 分析（获得总结段落、重要新闻、感兴趣新闻）
    summary_analysis, important_news, interest_news = analyze_news(all_articles, prompt_text)

    # 4. 保存 JSON 文件（供网页前端调用显示）
    json_path = OUTPUT_DIR / "news.json"
    json_data = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "updated_beijing": datetime.now().strftime("%Y-%m-%d %H:%M 北京时间"),
        "summary_analysis": summary_analysis,
        "important": important_news,
        "interest": interest_news,
        "sources": {
            key: {
                "name": SOURCES[key]["name"],
                "name_cn": SOURCES[key]["name_cn"],
                "count": len(all_data[key]),
                "articles": all_data[key],
            }
            for key in SOURCES
        }
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print("✅ news.json 保存成功！")

    # 5. 保存 Markdown 文件
    md_path = OUTPUT_DIR / "news.md"
    md_content = generate_markdown(all_data)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print("✅ news.md 保存成功！")

    total = sum(len(v) for v in all_data.values())
    print(f"\n✅ 全部完成！共获取 {total} 篇文章（已完整覆盖 8 个国际媒体源）")


if __name__ == "__main__":
    main()
