import os
from bs4 import BeautifulSoup
from google import genai
import requests

# 1. 確保金鑰完全是乾淨的字串，不要包含任何中文字或空格
# 請把下方的 AIzaSy... 替換成您真正的金鑰本身即可
GEMINI_API_KEY = "您的真正AIzaSy金鑰字串放這裡"

os.environ["GEMINI_API_KEY"] = str(GEMINI_API_KEY).strip()

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

    prompt = """
    你現在是一位資深的國家農業經濟研究員。
    請閱讀下方從台灣政府網站即時抓取下來的網頁資訊。
    請從中幫我精煉、歸納出：「台灣竹材經濟規模20年來的變化趨勢與痛點」
    （特別關注：出口量價狀況、進口單價是否有暴漲、貿易逆差是否急遽擴大等趨勢）。
    請以清晰、結構化的條列式繁體中文報告輸出你的深度觀察。

    數據內容：
    """ + f"\n\"\"\"{web_text}\"\"\""

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )

        print("\n📊 【Gemini 最終情報分析報告】")
        print("=" * 60)
        print(response.text)
        print("=" * 60)
        print("\n【系統通知】雲端排程執行成功！")

    except Exception as e:
        print(f"❌ Gemini 大腦呼叫失敗。錯誤訊息: {e}")


if __name__ == "__main__":
    run_bamboo_agentic_scraper()
