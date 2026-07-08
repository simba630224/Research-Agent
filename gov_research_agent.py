import sys

# 【核心修正 1】在程式最開頭，強制將 Python 全域的預設編碼改為 utf-8
import importlib

importlib.reload(sys)
sys.setdefaultencoding("utf-8") if hasattr(
    sys, "setdefaultencoding"
) else None

import os
from bs4 import BeautifulSoup
from google import genai
import requests

# 1. 確保金鑰完全是乾淨的字串，清除所有可能的隱形空格
GEMINI_API_KEY = "您的真正AIzaSy金鑰字串放這裡".strip()
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# 2. 初始化 Client
client = genai.Client()


def tool_search_web_cloud_safe(query: str) -> list:
    """雲端安全版搜尋工具"""
    print(f"\n🔍 [Agent 執行工具] 正在網路上搜尋: '{query}'")
    return [
        "https://data.gov.tw/dataset/40266",
        "https://agrstat.moa.gov.tw/moasdweb/inquire/TradeCoa.aspx",
    ]


def tool_fetch_web_content(url: str) -> str:
    """核心工具：動態下載目標網頁內容並抽取乾淨純文字"""
    print(f"📄 [Agent 執行工具] 正在讀取並解析網頁 HTML: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        for script in soup(["script", "style"]):
            script.decompose()

        return soup.get_text()[:2500]
    except Exception as e:
        return f"無法讀取網頁: {e}"


def run_bamboo_agentic_scraper():
    print("🚀 【Gemini 智能竹產業代理網路爬蟲 - 雲端版】啟動！")

    urls = tool_search_web_cloud_safe("台灣竹材 進出口 貿易統計 價值 重量")
    target_url = urls[0]
    web_text = tool_fetch_web_content(target_url)

    print("\n🧠 [Agent 思考] 正在將動態採集到的數據片段送交 Gemini 進行分析...")

    # 【核心修正 2】將所有 Prompt 中文字串明確宣告為 UTF-8 編碼
    prompt_text = (
        "你現在是一位資深的國家農業經濟研究員。\n"
        "請閱讀下方從台灣政府網站即時抓取下來的網頁資訊。\n"
        "請從中幫我精煉、歸納出：「台灣竹材經濟規模20年來的變化趨勢與痛點」\n"
        "（特別關注：出口量價狀況、進口單價是否有暴漲、貿易逆差是否急遽擴大等趨勢）。\n"
        "請以清晰、結構化的條列式繁體中文報告輸出你的深度觀察。\n\n"
        f"數據內容：\n\"\"\"{web_text}\"\"\""
    )

    # 強制將字串進行 utf-8 編碼與解碼，確保傳入 SDK 時絕對不帶有 ascii 特徵
    safe_prompt = prompt_text.encode("utf-8").decode("utf-8")

    try:
        # 使用新版 SDK 標準寫法呼叫最新的 Gemini 1.5 Flash 模型
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=safe_prompt,
        )

        print("\n📊 【Gemini 最終情報分析報告】")
        print("=" * 60)
        # 確保輸出到 GitHub 日誌時也是 UTF-8
        print(response.text.encode("utf-8").decode("utf-8"))
        print("=" * 60)
        print("\n【系統通知】雲端排程執行成功！")

    except Exception as e:
        # 捕捉底層錯誤並強制轉碼輸出
        err_msg = str(e).encode("utf-8", errors="ignore").decode("utf-8")
        print(f"❌ Gemini 大腦呼交失敗。錯誤訊息: {err_msg}")


if __name__ == "__main__":
    run_bamboo_agentic_scraper()
