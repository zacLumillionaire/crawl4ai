from flask import Flask, request, jsonify
import asyncio
from crawl4ai import AsyncWebCrawler
from tenacity import retry, stop_after_attempt, wait_fixed
import re
from threading import Thread
import traceback

app = Flask(__name__)

# 🧹 清洗 markdown
def clean_markdown(raw_text: str) -> str:
    raw_text = re.sub(r"\[!\[.*?\]\(.*?\)\]\(javascript:.*?\)", "", raw_text)
    raw_text = re.sub(r"!\[\]\(.*?\)", "", raw_text)
    raw_text = re.split(r"##\s*連絡詢問", raw_text)[0]
    raw_text = re.sub(r"\[([^\]]*?)\]\((?:https?|javascript).*?\)", r"\1", raw_text)
    raw_text = re.sub(r"(https?|ftp):\/\/[^\s\)\]\}]+", "", raw_text)
    raw_text = re.sub(r"\.concat\([^\)]*\)", "", raw_text)
    raw_text = re.sub(r"encodeURIComponent\([^\)]*\)", "", raw_text)
    raw_text = re.sub(r"document\.title", "", raw_text)
    raw_text = re.sub(r"javascript:[^ \n\)]*", "", raw_text)
    raw_text = re.sub(r"[\\]?\)+[;)]*", "", raw_text)
    raw_text = re.sub(r"^\s*\*\s*$", "", raw_text, flags=re.MULTILINE)
    raw_text = re.sub(r"\n{2,}", "\n\n", raw_text)
    raw_text = re.sub(r" {2,}", " ", raw_text)
    h2_start = raw_text.find("# ")
    if h2_start != -1:
        raw_text = raw_text[h2_start:]
    return raw_text.strip()

# 🔁 非同步爬蟲（有 retry + debug）
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def crawl4ai_with_retry(url: str) -> str:
    try:
        print(f"[DEBUG] 開始 AsyncWebCrawler 抓取：{url}")
        async with AsyncWebCrawler(strategy="httpx", verbose=True) as crawler:
            result = await crawler.arun(url=url)
            print(f"[DEBUG] 抓取成功，開始清洗")
            return clean_markdown(result.markdown)
    except Exception as e:
        print(f"[ERROR] 爬蟲內部例外：{type(e).__name__} - {e}")
        raise

# 📬 API 端點
@app.route('/crawl4ai_once', methods=['POST'])
def crawl4ai_once():
    data = request.get_json(force=True)
    url = data.get("url")

    if not url:
        return jsonify({"error": "Missing 'url'"}), 400

    result_container = {}

    # 🧵 使用 Thread 包 asyncio.run
    def do_crawl():
        try:
            print(f"[DEBUG] Thread 開始執行爬蟲")
            result = asyncio.run(crawl4ai_with_retry(url))
            result_container["cleaned"] = result
            print(f"[DEBUG] 爬蟲成功，資料已儲存")
        except Exception as e:
            traceback.print_exc()
            print(f"[ERROR] Thread 發生錯誤：{type(e).__name__} - {e}")
            result_container["error"] = f"Crawl failed: {type(e).__name__} - {e}"

    thread = Thread(target=do_crawl)
    thread.start()
    thread.join(timeout=30)  # ⏳ 延長等待時間

    if "error" in result_container:
        return jsonify({"error": result_container["error"]}), 500

    return jsonify({"markdown": result_container["cleaned"]})

# 🚀 本地端啟動用
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)