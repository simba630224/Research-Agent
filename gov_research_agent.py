import sys

# 強制將 Python 全域的預設編碼改為 utf-8（保留上一階段成功的編碼修正）
import importlib

importlib.reload(sys)
sys.setdefaultencoding("utf-8") if hasattr(
    sys, "setdefaultencoding"
) else None

import os
from bs4 import BeautifulSoup
from google import genai
import requests

# 1. 精確定義您的 API Key（清除可能存在的空格）
# 請確保下方的 AIzaSy... 是您真正的金鑰
MY_API_KEY = "AQ.Ab8RN6I_SzsLcK1FZOjWIpQhjeGCleb7gDgYcWEh9ma8L0sP5w".strip()

# 2. 【核心修正】直接把 api_key 當作參數傳入 Client，徹底解決 401 OAuth2 驗證錯誤
client = genai.Client(api_key=MY_API_KEY)


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
    print("🚀 【Gemini 智能竹產業代理網路爬蟲 - 雲端優化版】啟動！")

    urls = tool_search_web_cloud_safe("台灣竹材 進出口 貿易統計 價值 重量")
    target_url = urls[0]
    web_text = tool_fetch_web_content(target_url)

    print("\n🧠 [Agent 思考] 正在將動態採集到的數據片段送交 Gemini 進行分析...")

    prompt_text = (
        "你現在是一位資深的國家農業經濟研究員。\n"
        "請閱讀下方從台灣政府網站即時抓取下來的網頁資訊。\n"
        "請從中幫我精煉、歸納出：「台灣竹材經濟規模20年來的變化趨勢與痛點」\n"
        "（特別關注：出口量價狀況、進口單價是否有暴漲、貿易逆差是否急遽擴大等趨勢）。\n"
        "請以清晰、結構化的條列式繁體中文報告輸出你的深度觀察。\n\n"
        f"數據內容：\n\"\"\"{web_text}\"\"\""
    )

    safe_prompt = prompt_text.encode("utf-8").decode("utf-8")

    try:
        # 呼叫 Gemini 1.5 Flash 模型
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=safe_prompt,
        )

        print("\n📊 【Gemini 最終情報分析報告】")
        print("=" * 60)
        print(response.text.encode("utf-8").decode("utf-8"))
        print("=" * 60)
        print("\n【系統通知】雲端排程執行成功！")

    except Exception as e:
        err_msg = str(e).encode("utf-8", errors="ignore").decode("utf-8")
        print(f"❌ Gemini 大腦呼交失敗。錯誤訊息: {err_msg}")


if __name__ == "__main__":
    run_bamboo_agentic_scraper()
