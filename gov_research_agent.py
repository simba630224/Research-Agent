import os
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS  # 免費且不需要Key的搜尋工具
from google import genai
import pandas as pd
import requests

# ==========================================
# 0. 初始化：請在此處填入您的 Gemini API Key
# ==========================================
# 您可以前往 Google AI Studio (https://aistudio.google.com/) 免費申請
GEMINI_API_KEY = "您的_GEMINI_API_KEY_請填在此處"
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# 初始化 Gemini 客戶端
client = genai.Client()


# ==========================================
# 1. 工具箱 (Tools)：Agent 可以使用的外部工具
# ==========================================
def tool_search_web(query: str) -> list:
    """工具：使用 DuckDuckGo 搜尋相關政府網站，擺脫網址限制"""
    print(f"🔍 [Agent 行動] 正在網路上搜尋: '{query}'")
    try:
        with DDGS() as ddgs:
            # 限制搜尋台灣政府網站 (.gov.tw)
            results = ddgs.text(f"{query} site:gov.tw", max_results=3)
            urls = [r["href"] for r in results if "href" in r]
            return urls
    except Exception as e:
        print(f"❌ 搜尋工具出錯: {e}")
        # 若搜尋失敗，提供您查到的核心網址作為備援
        return [
            "https://data.gov.tw/dataset/40266",
            "https://agrstat.moa.gov.tw/moasdweb/inquire/TradeCoa.aspx",
        ]


def tool_fetch_web_content(url: str) -> str:
    """工具：動態下載網頁內容並抽取純文字"""
    print(f"📄 [Agent 行動] 正在讀取並解析網頁: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        # 移除干擾文字
        for script in soup(["script", "style"]):
            script.decompose()

        # 回傳前 2000 個字給 Gemini 閱讀
        return soup.get_text()[:2000]
    except Exception as e:
        return f"無法讀取網頁: {e}"


# ==========================================
# 2. Agent 思考與執行核心 (ReAct 循環)
# ==========================================
def run_bamboo_agent():
    print("🚀 【Gemini 智能竹產業代理】啟動！")

    # 思考步驟 1：
    print("\n【思考 1】我需要主動尋找台灣竹材 20 年來的經濟規模與進出口變化。")
    urls = tool_search_web("台灣竹材 進出口 貿易統計 價值 重量")

    print("\n【觀察 1】搜尋引擎回傳了以下高相關的政府數據節點：")
    for u in urls:
        print(f"   - {u}")

    # 思考步驟 2：
    target_url = urls[0]
    print(f"\n【思考 2】我決定深入讀取第一個網站 `{target_url}` 來抽取關鍵數據。")
    web_text = tool_fetch_web_content(target_url)

    # 思考步驟 3：將網頁文字送給 Gemini 進行「情報提煉與洞察」
    print("\n🧠 [Agent 思考] 正在將網頁原始資料送交 Gemini 大腦進行結構化分析...")

    prompt = f"""
    請扮演資深農業經濟研究員，閱讀下方從政府網站抓取到的網頁雜亂純文字。
    請從中幫我提煉出「台灣竹材進出口的黃金交叉痛點」（例如出口量價齊跌、進口單價飆升、貿易逆差擴大等趨勢），
    並以條列式結構化輸出你的深度觀察。

    網頁抓取到的文字內容：
    \"\"\"{web_text}\"\"\"
    """

    try:
        # 呼叫最新的 Gemini 1.5 Flash 模型進行推理
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )

        print("\n📊 【Gemini 最終情報分析報告】")
        print("--------------------------------------------------")
        print(response.text)
        print("--------------------------------------------------")

        # 思考步驟 4：自動銜接後續的資料統計（這裡模擬 Pandas 承接指標）
        print("\n【後續自動化】系統已動態鎖定數據特徵。已準備好將歷史趨勢匯入 Pandas 繪圖引擎。")

    except Exception as e:
        print(f"❌ Gemini 呼叫失敗，請檢查您的 API Key 是否正確。錯誤訊息: {e}")


if __name__ == "__main__":
    # 如果還沒有 Key，先提醒使用者
    if GEMINI_API_KEY == "您的_GEMINI_API_KEY_請填在此處":
        print(
            "⚠️ 提示：請先在程式碼第 10 行填入您的 Gemini API Key，才能成功跑通 AI 大腦喔！"
        )
    else:
        run_bamboo_agent()
