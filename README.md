# 台／美股市值前十每日投資訊報

這個專案可用 GitHub Actions 每日執行，將台股市值前二十名與美股市值前十名的價格、技術指標、20／50 日新高新低、公開新聞／研究資訊連結及 50 字內摘要寫入 Google Sheet。市值只用來排序，不會寫入報表。

> 不是個人化投資建議。程式不會評估你的財務狀況、風險承受度或持倉；請自行查證資料並諮詢持牌專業人士。

## 你需要設定的 GitHub Secrets

| 名稱 | 必填 | 說明 |
| --- | --- |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 是 | Google service account 的完整 JSON 金鑰內容 |
| `GOOGLE_SHEET_ID` | 是 | 試算表網址中 `/d/` 與下一個 `/` 間的 ID |
| `OPENAI_API_KEY` | 否 | 設定後用 OpenAI 產生中文 50 字摘要；未設定時使用規則式摘要 |
| `OPENAI_MODEL` | 否 | 預設 `gpt-4o-mini` |
| `TW_TICKERS` | 否 | 以逗號分隔的台股候選池，例如 `2330.TW,2317.TW`；程式會從中依市值排序選前十 |

## Google Sheet 設定

1. 在 Google Cloud 啟用 **Google Sheets API**，建立 service account 與 JSON 金鑰。
2. 將目標試算表分享給 service account JSON 內的 `client_email`，權限選「編輯者」。
3. 於 GitHub repository 的 **Settings → Secrets and variables → Actions** 新增上表 secrets。
4. 將這些檔案推送到 GitHub。workflow 預設每天台北時間 08:15 執行，也可以從 Actions 頁面手動執行。

## 資料與限制

- 股價／市值與技術指標來自 Yahoo Finance（經 `yfinance`）。美股和台股皆先在候選池中依當日取得的市值排序。美股候選池涵蓋大型股；台股候選池可用 `TW_TICKERS` 擴充，以提高「全市場前十」的完整性。
- 研究資訊採 Google News RSS 搜尋結果；此為公開媒體／券商文章索引，**不是**付費券商報告或已驗證目標價。每列保留來源 URL 以便覆核。
- `買進／觀望／減碼` 是由 RSI、均線與 MACD 的透明規則產生的訊號，僅供研究流程排序，絕非交易指令。

## 本機執行

```bash
python -m pip install -r requirements.txt
$env:GOOGLE_SERVICE_ACCOUNT_JSON = Get-Content service-account.json -Raw
$env:GOOGLE_SHEET_ID = '你的Sheet ID'
python stock_report.py
```

每個月會自動建立一張分頁，例如 `Daily Report 2026-08`。同一天、同一市場、同一股票代號再次執行時會更新該列；不同交易日則會新增資料，方便保留歷史紀錄。

每月約 20 個交易日、台股 20 檔與美股 10 檔，約 600 列資料，因此工作表不會隨年數累積而明顯變慢。舊版的 `Daily Report` 分頁會保留，不會被刪除或改寫。

## 技術訊號與新高新低欄位

`判斷依據` 欄會直接顯示每一檔股票符合的條件；其中 RSI 只作為內部判斷，不顯示為欄位。

| 技術訊號 | 判斷條件 |
| --- | --- | --- |
| 偏多 | 收盤價 > MA20 > MA50、MACD > 0、RSI < 70 |
| 偏空／過熱 | 收盤價 < MA20 < MA50 且 MACD < 0，或 RSI > 75 |
| 盤整 | 不符合前兩種條件 |

「創20日新高／新低」與「創50日新高／新低」各為獨立欄位；當日收盤價嚴格高於前 20／50 個交易日最高收盤價時顯示新高，嚴格低於前 20／50 個交易日最低收盤價時顯示新低。平手不算創新高或新低。

摘要不會包含公司名稱或股票代號。
