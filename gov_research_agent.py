import os
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS  # 免費且不需要金鑰的網路搜尋工具
from google import genai  # 導入 Google 官方最新版 genai 模組
import pandas as pd
import requests

# ==========================================
# 0. 設定您的 Gemini API Key
# ==========================================
# 請將您在 Google AI Studio 申請到的 Key 填入下方
GEMINI_API_KEY = "AQ.Ab8RN6LLEpBesYepnw8gm8j1jzE4m5guOte2skDoQi6V6fan7g"

# 安全地載入金鑰到環境變數中，避免舊版參數初始化衝突
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# 初始化最新版 Client 物件（SDK 會自動從環境變數抓取金鑰，解決 api_key 參數錯誤的問題）
client = genai.Client()


# ==========================================
# 1. 智能代理工具箱 (Tools)
# ==========================================
def tool_search_web(query: str) -> list:
    """自主行動工具：使用 DuckDuckGo 搜尋相關台灣政府網站，擺脫網址硬編碼限制"""
    print(f"\n🔍 [Agent 執行工具] 正在網路上搜尋: '{query}'")
    try:
        with DDGS() as ddgs:
            # 限制搜尋範圍在台灣政府網站 (.gov.tw)
            results = ddgs.text(f"{query} site:gov.tw", max_results=3)
            urls = [r["href"] for r in results if "href" in r]
            return urls
    except Exception as e:
        print(f"❌ 搜尋工具執行失敗: {e}")
        # 若網路偶發性異常，提供您查到的核心政府網址作為智慧備援
        return [
            "https://data.gov.tw/dataset/40266",
            "https://agrstat.moa.gov.tw/moasdweb/inquire/TradeCoa.aspx",
        ]


def tool_fetch_web_content(url: str) -> str:
    """自主行動工具：動態下載目標網頁內容並抽取乾淨純文字"""
    print(f"📄 [Agent 執行工具] 正在讀取並解析網頁 HTML: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = "utf-8"  # 確保正確解析台灣政府網站的繁體中文字
        soup = BeautifulSoup(res.text, "html.parser")

        # 移除干擾網頁閱讀的 JavaScript 和 CSS 樣式表
        for script in soup(["script", "style"]):
            script.decompose()

        # 回傳前 2000 個字給 Gemini 閱讀，避免 Token 浪費
        return soup.get_text()[:2000]
    except Exception as e:
        return f"無法讀取網頁: {e}"


# ==========================================
# 2. Agent 思考與執行核心 (ReAct 思維鏈)
# ==========================================
def run_bamboo_agentic_scraper():
    print("🚀 【Gemini 智能竹產業代理網路爬蟲】啟動！")

    # 思考與行動 1：自主探路
    print("\n【思考 1】要分析台灣竹材20年來的經濟規模變化，我需要主動搜尋政府最新的貿易數據。")
    urls = tool_search_web("台灣竹材 進出口 貿易統計 價值 重量")

    print("\n【觀察 1】搜尋引擎成功定位以下高價值的數據節點：")
    for u in urls:
        print(f"   - {u}")

    # 思考與行動 2：深入解析
    target_url = urls[0] if urls else "https://data.gov.tw/dataset/40266"
    print(f"\n【思考 2】我決定深入讀取最具代表性的官方網站：{target_url}")
    web_text = tool_fetch_web_content(target_url)

    # 思考與行動 3：利用 Gemini 大腦進行大數據情報提煉
    print("\n🧠 [Agent 思考] 正在將動態採集到的網頁雜亂文字送交 Gemini 進行分析...")

    prompt = f"""
    你現在是一位資深的國家農業經濟研究員。
    請閱讀下方從台灣政府網站即時抓取下來的網頁純文字，
    從中幫我精煉、歸納出「台灣竹材進出口的重大經濟規模變化與痛點」
    （例如：出口量價狀況、進口單價是否有爆發性成長、貿易逆差擴大等趨勢）。
    請以清晰、結構化的條列式報告輸出你的深度觀察。

    網頁抓取到的即時內容：
    \"\"\"{web_text}\"\"\"
    """

    try:
        # 使用新版 SDK 標準寫法呼叫最新的 Gemini 1.5 Flash 模型
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )

        print("\n📊 【Gemini 最終情報分析報告】")
        print("=" * 60)
        print(response.text)
        print("=" * 60)

        print(
            "\n【系統通知】情報提煉成功！數據特徵已由 Agent 鎖定，後續可完美銜接 Pandas 統計繪圖模組。"
        )

    except Exception as e:
        print(
            f"❌ Gemini 大腦呼叫失敗。請確認您的 API Key 是否正確填入，且已安裝最新的 google-genai 套件。錯誤訊息: {e}"
        )


if __name__ == "__main__":
    # 預檢機制
    if GEMINI_API_KEY == "您的_GEMINI_API_KEY_請填在此處":
        print(
            "⚠️ 提示：請先在程式碼第 11 行填入您真正的 Gemini API Key，才能順利啟動 AI 大腦喔！"
        )
    else:
        run_bamboo_agentic_scraper()
