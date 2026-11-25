r"""分段 VPVR 回放：raw\<代號>_1d/_1h.json → data.json
主圖 SOXX（含油價、殖利率、利差、融資副圖資料），下方 QQQ／SPY／0050 用同一套算法。
VPVR：小時 K 的量平均攤在該根高低價之間；每日小時量依日線總量等比放大（補收盤競價）。
所有 VP 起點＝6/22；半年/一年＝終點往回 6/12 個月。只用終點當天(含)以前資料。
各檔的階段日期取「該市場在該日（含）以前的最後一個交易日」（0050 遇台股休市會往前取）。"""
import json, datetime as dt, math, re, calendar
from collections import defaultdict

HIGH=dt.date(2026,6,22)
END=dt.date(2026,10,6)   # 反彈2 結束；之後為「後續」段（到最新交易日）
NODES=[('下跌','2026-07-29','6/22 → 7/29'),
       ('反彈1','2026-08-17','7/29 → 8/17'),
       ('橫盤','2026-09-18','8/17 → 9/18'),
       ('反彈2','2026-10-06','9/18 → 10/6')]
TICKERS=[('SOXX','SOXX','iShares Semiconductor ETF',-5),
         ('0050.TW','0050','元大台灣50',8),
         ('QQQ','QQQ','Invesco QQQ Trust',-5),
         ('SPY','SPY','SPDR S&P 500 ETF Trust',-5)]
STOCKS=[('AMD','AMD','Advanced Micro Devices',-5),       # 個股分頁（同算法，不含副圖）
        ('TSM','TSM','台積電 ADR（Taiwan Semiconductor）',-5),
        ('2454.TW','2454','聯發科 MediaTek',8)]

def back(e,m):
    y,mo=e.year,e.month-m
    while mo<=0: mo+=12;y-=1
    return dt.date(y,mo,min(e.day,28))+dt.timedelta(days=1)

def nice_bin(px):   # 價格級距 ≈ 股價 0.5%，取整齊數字（SOXX → 1 美元）
    raw=px*0.005
    return min([0.01,0.02,0.025,0.05,0.1,0.2,0.25,0.5,1,2,2.5,5,10],key=lambda b:abs(math.log(b/raw)))

def pivots(daily):
    """個股自動切階段（收盤價）：
    L1 下跌低點＝7/1–8/10 最低收盤；H0 高點＝6/1–L1 最高收盤；
    H2 反彈2 高點＝8/15–10/31 最高收盤；
    H1／L2：L1→H2 之間跑 4% zigzag，H1＝第一個轉折高點（反彈1 結束），L2＝H2 前最後一個轉折低點（橫盤結束）。"""
    c=[(a,x) for a,x,_ in daily]
    rng=lambda s,e:[(a,x) for a,x in c if s<=a<=e]
    L1=min(rng(dt.date(2026,7,1),dt.date(2026,8,10)),key=lambda t:t[1])
    H0=max(rng(dt.date(2026,6,1),L1[0]),key=lambda t:t[1])
    H2=max(rng(dt.date(2026,8,15),dt.date(2026,10,31)),key=lambda t:t[1])
    TH=0.04; piv=[]; up=True; ext=L1
    for t in rng(L1[0],H2[0])[1:]:
        if up:
            if t[1]>=ext[1]: ext=t
            elif t[1]<=ext[1]*(1-TH): piv.append(('H',ext)); up=False; ext=t
        else:
            if t[1]<=ext[1]: ext=t
            elif t[1]>=ext[1]*(1+TH): piv.append(('L',ext)); up=True; ext=t
    hs=[p for k,p in piv if k=='H']; ls=[p for k,p in piv if k=='L']
    if not ls: raise SystemExit(f'找不到 4% 轉折點，請手動指定階段日期')
    H1,L2=hs[0],ls[-1]
    md=lambda d:f'{d.month}/{d.day}'
    seq=[H0,L1,H1,L2,H2]
    nodes=[(k,seq[i+1][0].isoformat(),f'{md(seq[i][0])} → {md(seq[i+1][0])}') for i,k in enumerate(['下跌','反彈1','橫盤','反彈2'])]
    return H0[0],H2[0],nodes

NODE_OVERRIDE={'0050':{'橫盤':'2026-09-15'},'2454':{'橫盤':'2026-09-01'}}   # 代號 → {階段: 結束日}

def build(sym,code,name,tz,auto=False):
    P=lambda f: json.load(open(f))['chart']['result'][0]
    d=P(f'raw/{sym}_1d.json'); h=P(f'raw/{sym}_1h.json')
    dq=d['indicators']['quote'][0]; hq=h['indicators']['quote'][0]
    day=lambda t: (dt.datetime.utcfromtimestamp(t)+dt.timedelta(hours=tz)).date()
    hours=[(day(t),hq['high'][i],hq['low'][i],hq['volume'][i] or 0) for i,t in enumerate(h['timestamp']) if hq['high'][i]]
    hsum=defaultdict(float); hlast={}
    for i,t in enumerate(h['timestamp']):
        if hq['close'][i]: hlast[day(t)]=hq['close'][i]
    for a,_,_,v in hours: hsum[a]+=v
    daily=[]
    for i,t in enumerate(d['timestamp']):
        a=day(t); c=dq['close'][i]; v=dq['volume'][i] or 0
        if not c and a<dt.date.today() and a in hlast:   # Yahoo 日線最後一根常是 null → 用小時線補（今天盤中不補）
            c,v=hlast[a],hsum[a]
        if c and (not daily or daily[-1][0]!=a): daily.append((a,c,v))
    dvol={a:v for a,_,v in daily}
    closes=[c for _,c,_ in daily]
    dates=[a for a,_,_ in daily]
    td=lambda x: max(a for a in dates if a<=x)          # 該日（含）以前最後一個交易日
    def ma(n,i): return round(sum(closes[i-n+1:i+1])/n,4) if i>=n-1 else None
    if auto:
        high,end,nodes=pivots(daily)
        ov=NODE_OVERRIDE.get(code,{})                    # 個股自動轉折點的手動修正（如 2454 橫盤到 9/1）
        if ov:
            ends=[td(dt.date.fromisoformat(ov.get(k,e))).isoformat() for k,e,_ in nodes]
            md=lambda s: f"{int(s[5:7])}/{int(s[8:])}"
            nodes=[(k,ends[i],f"{md(ends[i-1]) if i else md(high.isoformat())} → {md(ends[i])}") for i,(k,_,_) in enumerate(nodes)]
    else:
        high,end=td(HIGH),td(END)
        ov=NODE_OVERRIDE.get(code,{})                    # 個別標的的階段日期例外（如 0050 橫盤到 9/15）
        ends=[ov.get(k,e) for k,e,_ in NODES]
        md=lambda s: f"{int(s[5:7])}/{int(s[8:])}"
        nodes=[(k,ends[i],f"{md(ends[i-1]) if i else '6/22'} → {md(ends[i])}") for i,(k,_,_) in enumerate(NODES)]
    BIN=nice_bin(dict((a,c) for a,c,_ in daily)[high])
    def profile(s,e):
        vol=defaultdict(float)
        for a,hi,lo,v in hours:
            if not(s<=a<=e) or v<=0: continue
            v*=dvol.get(a,hsum[a])/hsum[a] if hsum[a] else 1
            b0,b1=math.floor(lo/BIN),math.floor(hi/BIN)
            if b0==b1: vol[b0]+=v; continue
            span=hi-lo
            for b in range(b0,b1+1):
                ov=min(hi,(b+1)*BIN)-max(lo,b*BIN)
                if ov>0: vol[b]+=v*ov/span
        lo,hi=min(vol),max(vol)
        return {'start':s.isoformat(),'end':e.isoformat(),'bin':BIN,'b0':round(lo*BIN,6),
                'v':[round(vol.get(b,0)) for b in range(lo,hi+1)]}
    series=[{'d':a.isoformat(),'c':round(c,4),'ma20':ma(20,i),'ma60':ma(60,i),'ma120':ma(120,i),'ma240':ma(240,i)}
            for i,(a,c,_) in enumerate(daily) if a>=dt.date(2025,11,1)]
    last=daily[-1][0]                                   # 第五段「後續」：反彈2 結束 → 最新交易日，同樣有 VPVR／均線
    nodes=list(nodes)+[('後續',last.isoformat(),f'{end.month}/{end.day} → {last.month}/{last.day}')]
    out={'ticker':code,'name':name,'high':high.isoformat(),'end':end.isoformat(),'series':series,'nodes':[]}
    for k,e,label in nodes:
        e=td(dt.date.fromisoformat(e))
        out['nodes'].append({'key':k,'label':label,'end':e.isoformat(),
            'prof':{'wave':profile(high,e),'6m':profile(back(e,6),e),'1y':profile(back(e,12),e)}})
    print(code,'bin',BIN,[(n['key'],n['end']) for n in out['nodes']],'last',series[-1]['d'])
    return out, series

out,series=build(*TICKERS[0])

# ---- 主圖（SOXX）副圖資料
OV=json.load(open('../總經網站/data/overlay.json',encoding='utf-8'))   # FRED DGS10／BAMLC0A0CM／BAMLH0A0HYM2
OV['wti']=json.load(open('../總經網站/data/rates.json',encoding='utf-8'))['wti']   # Yahoo CL=F，與 rates.html 同源
def asof(key):
    rows=sorted(OV[key])
    last=rows[-1][0]
    def f(d):
        if d>last: return None                          # 資料源還沒出（如利差晚一天）→ 留白，不沿用前值
        v=None
        for dd,x in rows:
            if dd<=d: v=x
            else: break
        return v
    return f
for k,src in (('y10','dgs10'),('ig','oas_ig'),('hy','oas_hy'),('wti','wti')):
    f=asof(src)
    for r in series: r[k]=f(r['d'])
for r in series:                                        # SOXX 價格維持兩位小數（與先前一致）
    for k in ('c','ma20','ma60','ma120','ma240'):
        if r[k] is not None: r[k]=round(r[k],2)
# 融資餘額年增率（FINRA 月資料）：取自總經網站 margin.html 內嵌的 RAW，點放在該月月底
_h=open('../總經網站/margin.html',encoding='utf-8').read()
_raw=json.loads(re.search(r'const RAW = (\{.*?\});\n',_h).group(1))
out['margin']=[{'m':m,'d':f"{m}-{calendar.monthrange(int(m[:4]),int(m[5:]))[1]:02d}",'yoy':y}
               for m,y in zip(_raw['months'],_raw['yoy']) if m>='2025-10' and y is not None]

# ---- 下方其他 ETF（同一套算法，不含副圖與事件）
out['extras']=[build(*t)[0] for t in TICKERS[1:]]
# ---- 個股分頁
out['stocks']=[build(*t,auto=True)[0] for t in STOCKS]
json.dump(out,open('data.json','w',encoding='utf-8'),ensure_ascii=False)
