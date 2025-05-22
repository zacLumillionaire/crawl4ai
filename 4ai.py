from flask import Flask, request, jsonify
import asyncio
from crawl4ai import AsyncWebCrawler
from tenacity import retry, stop_after_attempt, wait_fixed
import re
import traceback
import threading
from tenacity import RetryError

app = Flask(__name__)
crawl_lock = threading.Lock()  # 🔒 全域鎖

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

# 🔁 非同步爬蟲
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def crawl4ai_with_retry(url: str) -> str:
    try:
        print(f"[DEBUG] 開始 AsyncWebCrawler 抓取：{url}")
        async with AsyncWebCrawler(strategy="httpx", verbose=True) as crawler:
            result = await crawler.arun(url=url)
            print(f"[DEBUG] 抓取成功，開始清洗")

            if not result.markdown or result.markdown.strip() == "":
                raise ValueError("抓不到內容")

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

    with crawl_lock:
        try:
            print(f"[DEBUG] 執行 asyncio.run 爬蟲：{url}")
            cleaned = asyncio.run(crawl4ai_with_retry(url))
            return jsonify({"markdown": cleaned})

        except RetryError as re:
            last_exc = re.last_attempt.exception()
            if isinstance(last_exc, ValueError) and "抓不到內容" in str(last_exc):
                print(f"[INFO] 網頁無內容（已重試）: {url}")
                return '', 204  # 204 No Content

            print(f"[ERROR] 最後一次重試仍失敗：{type(last_exc).__name__} - {last_exc}")
            return jsonify({"error": f"Retry failed: {type(last_exc).__name__} - {last_exc}"}), 500

        except Exception as e:
            print(f"[ERROR] 發生未知錯誤：{e}")
            traceback.print_exc()
            return jsonify({"error": f"Crawl failed: {type(e).__name__} - {e}"}), 500

# 🚀 本地啟動用
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)