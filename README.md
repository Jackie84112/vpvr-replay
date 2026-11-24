# SOXX 分段 VPVR 回放

網頁：https://jackie84112.github.io/vpvr-replay/

以「當時看得到的資料」重播 2026 年下跌與反彈各階段：每個階段的 VPVR 與均線只用該階段終點以前的資料。

重建：
```
python fetch.py        # 抓 Yahoo 日線/小時線 → raw/
python build_data.py   # → data.json（副圖資料讀 ../總經網站/data）
python make_html.py    # template.html + data.json → index.html
```
