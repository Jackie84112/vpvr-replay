"""抓 Yahoo 日線（3 年）與小時線（730 天）→ raw/<代號>_1d.json、raw/<代號>_1h.json"""
import requests, json, os
UA={'User-Agent':'Mozilla/5.0'}
TICKERS=['SOXX','QQQ','SPY','0050.TW','AMD','TSM','2454.TW']
os.makedirs('raw',exist_ok=True)
def get(t, interval, rng):
    r=requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{t}',params={'interval':interval,'range':rng,'includePrePost':'false'},headers=UA,timeout=30)
    r.raise_for_status(); return r.json()
for t in TICKERS:
    json.dump(get(t,'1d','3y'),open(f'raw/{t}_1d.json','w'))
    json.dump(get(t,'60m','730d'),open(f'raw/{t}_1h.json','w'))
    print('ok',t)
