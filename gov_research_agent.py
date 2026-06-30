import os
import io
import requests
import pandas as pd
import pdfplumber
import google.generativeai as genai
from bs4 import BeautifulSoup
from datetime import datetime

# ==========================================
# 0. 環境變數與設定
# ==========================================
# 透過環境變數取得 API Key (GitHub Secrets)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# 從 GitHub Actions 的輸入取得關鍵字，若無則使用預設值
SEARCH_KEYWORD = os.environ.get("RESEARCH_KEYWORD", "竹產業")

if not GEMINI_API_KEY:
    print("警告：未設定 GEMINI_API_KEY，AI 摘要功能將無法使用。")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    # 使用 gemini-1.5-flash 模型，適合快速處理大量文本
    model = genai.GenerativeModel('gemini-1.5-flash')

# ==========================================
# 1. 資料獲取與解析模組
# ==========================================
def search_open_data(keyword):
    """
    透過政府資料開放平臺 API 搜尋資料集
    """
    print(f"\n[🔍 搜尋 Open Data] 關鍵字：{keyword}")
    # data.gov.tw v2 API 搜尋端點 (範例寫法)
    api_url = f"https://data.gov.tw/api/v2/iqql?query={keyword}"
    
    results = []
    try:
        response = requests.get(api_url, timeout=10)
        data = response.json()
        
        # 這裡僅示意抓取前 3 筆相關資料集
        datasets = data.get('data', {}).get('results', [])[:3]
        for item in datasets:
            title = item.get('title')
            desc = item.get('description', '')[:100] # 擷取部分描述
            provider = item.get('provider', '')
            results.append(f"資料集名稱：{title}\n提供機關：{provider}\n說明：{desc}...\n")
        
        return "\n".join(results)
    except Exception as e:
        print(f"Open Data API 查詢失敗: {e}")
        return "無法取得 Open Data。"

def parse_pdf_from_url(url):
    """
    下載 PDF 並解析文字
    """
    print(f"[📄 解析 PDF] {url}")
    try:
        response = requests.get(url, timeout=15)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            text = ""
            # 只抓前兩頁作為摘要，避免 token 過長
            for page in pdf.pages[:2]:
                text += page.extract_text() + "\n"
        return text[:1000] # 限制字數
    except Exception as e:
        print(f"PDF 解析失敗: {e}")
        return ""

def parse_excel_from_url(url):
    """
    下載 Excel/CSV 並轉為文字摘要
    """
    print(f"[📊 解析表格] {url}")
    try:
        if url.endswith('.csv'):
            df = pd.read_csv(url)
        else:
            df = pd.read_excel(url)
        # 取前 5 筆資料轉為文字，供 AI 參考
        return df.head(5).to_markdown()
    except Exception as e:
        print(f"表格解析失敗: {e}")
        return ""

# ==========================================
# 2. AI 摘要模組
# ==========================================
def generate_ai_summary(keyword, raw_text):
    """
    將爬取到的生肉資料交給 Gemini 進行統整
    """
    if not GEMINI_API_KEY or not raw_text.strip():
        return raw_text

    print("\n[🧠 進行 AI 摘要中...]")
    prompt = f"""
    你是一個專業的政策與產業研究員。請根據以下政府公開資料的初步擷取內容，
    針對關鍵字「{keyword}」撰寫一份重點摘要報告。
    
    要求：
    1. 條理分明，使用列點說明。
    2. 必須保留資料來源或機關名稱。
    3. 若資料不足以得出結論，請誠實說明「目前抓取的資料未涵蓋此部分」。
    
    【原始擷取資料】：
    {raw_text}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"AI 摘要生成失敗: {e}")
        return "AI 摘要生成失敗，請見原始資料。"

# ==========================================
# 3. 主程式
# ==========================================
def main():
    print(f"啟動自動化研究助理，研究主題：{SEARCH_KEYWORD}")
    
    # 步驟 A：蒐集各方資料 (這裡可依需求擴充 HTML 爬蟲)
    collected_data = ""
    
    # 1. 抓取 Open Data
    open_data_text = search_open_data(SEARCH_KEYWORD)
    collected_data += f"=== 政府 Open Data 搜尋結果 ===\n{open_data_text}\n\n"
    
    # (示範) 2. 如果您有特定的 PDF 或 Excel 網址，可以傳入解析
    # pdf_text = parse_pdf_from_url("https://example.com/some_budget.pdf")
    # collected_data += f"=== 相關 PDF 解析 ===\n{pdf_text}\n\n"
    
    # 步驟 B：交由 AI 摘要
    final_report = generate_ai_summary(SEARCH_KEYWORD, collected_data)
    
    # 步驟 C：輸出為 Markdown / 文字檔
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Research_Report_{SEARCH_KEYWORD}_{timestamp}.md"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# 【{SEARCH_KEYWORD}】自動化研究報告\n\n")
        f.write(f"**生成時間：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## AI 統整摘要\n")
        f.write(final_report)
        f.write("\n\n---\n## 原始抓取參考資料\n")
        f.write(collected_data)
        
    print(f"\n✅ 報告已生成：{filename}")

if __name__ == "__main__":
    main()
