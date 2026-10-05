import base64
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
import websocket
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/review'
OUT.mkdir(parents=True, exist_ok=True)
chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
counter = 0
events = []

def call(method, params=None):
    global counter
    counter += 1
    ws.send(json.dumps({'id': counter, 'method': method, 'params': params or {}}))
    while True:
        message = json.loads(ws.recv())
        if message.get('id') == counter:
            if 'error' in message:
                raise RuntimeError(message)
            return message.get('result', {})
        events.append(message)

def evaluate(expression):
    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
    if 'exceptionDetails' in result:
        raise RuntimeError(result)
    return result['result'].get('value')

with tempfile.TemporaryDirectory(prefix='imi-chrome-') as profile:
    proc = subprocess.Popen([chrome, '--headless=new', '--no-first-run', '--no-default-browser-check',
        '--remote-debugging-port=0', '--remote-allow-origins=*', f'--user-data-dir={profile}', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        port_file = Path(profile) / 'DevToolsActivePort'
        for _ in range(100):
            if port_file.exists(): break
            time.sleep(.1)
        port = port_file.read_text().splitlines()[0]
        targets = json.load(urllib.request.urlopen(f'http://localhost:{port}/json'))
        ws = websocket.create_connection(next(t for t in targets if t['type']=='page')['webSocketDebuggerUrl'], timeout=30)
        call('Page.enable'); call('Runtime.enable'); call('Network.enable')
        call('Network.emulateNetworkConditions', {'offline':True,'latency':0,'downloadThroughput':0,'uploadThroughput':0})
        results = []
        for width in (390, 1440):
            call('Emulation.setDeviceMetricsOverride', {'width':width,'height':900,'deviceScaleFactor':1,'mobile':False})
            for group in ('318','402'):
                call('Page.navigate', {'url':'about:blank'})
                time.sleep(.2)
                events.clear()
                call('Page.navigate', {'url':(ROOT/'reports/dashboard/imi_dashboard.html').as_uri()+f'#g{group}'})
                for _ in range(100):
                    ready = evaluate("document.readyState==='complete' && typeof Plotly!=='undefined' && document.querySelectorAll('.js-plotly-plot').length===5")
                    if ready: break
                    time.sleep(.1)
                time.sleep(.4)
                detail = evaluate("""(() => ({
                    width:innerWidth, scrollWidth:document.documentElement.scrollWidth,
                    visiblePanels:[...document.querySelectorAll('.panel')].filter(p=>!p.hidden).map(p=>p.id),
                    plotWidths:[...document.querySelectorAll('.panel:not([hidden]) .js-plotly-plot')].map(p=>({outer:p.clientWidth,plot:p._fullLayout.width})),
                    kpis:[...document.querySelectorAll('.panel:not([hidden]) .tile')].map(p=>p.innerText),
                    table:[...document.querySelectorAll('.panel:not([hidden]) tbody tr')].map(r=>[...r.cells].map(c=>c.innerText)),
                    findings:document.querySelector('.panel:not([hidden]) .findings').innerText,
                    plots:[...document.querySelectorAll('.panel:not([hidden]) .js-plotly-plot')].map(p=>p.calcdata.map(trace=>trace.map(pt=>({x:pt.x,y:pt.y})))),
                    drivers:[...document.querySelectorAll('.js-plotly-plot')].at(-1).calcdata.map(trace=>trace.map(pt=>({x:pt.x,y:pt.y}))),
                    errors:[]
                }))()""")
                detail.update(group=group,ready=ready)
                detail['tableScroll'] = evaluate("""(() => {let table=document.querySelector('.panel:not([hidden]) table');let card=table.closest('.card');card.scrollLeft=100;let moved=card.scrollLeft;card.scrollLeft=0;return {client:card.clientWidth,scroll:card.scrollWidth,moved}})()""")
                detail['exceptions'] = [e['params'] for e in events if e.get('method')=='Runtime.exceptionThrown']
                image = call('Page.captureScreenshot', {'format':'png','captureBeyondViewport':True})
                (OUT/f'dashboard-{group}-{width}.png').write_bytes(base64.b64decode(image['data']))
                results.append(detail)
        forecasts = pd.read_csv(ROOT/'logs/metrics/06_latest_forecasts.csv', dtype={'group':str})
        iteration2 = pd.read_csv(ROOT/'logs/metrics/05b_results.csv', dtype={'commodity_code':str})
        external = pd.read_csv(ROOT/'data/interim/external_monthly_aggregates.csv', parse_dates=['month_ce'])
        modeling = pd.read_csv(ROOT/'data/processed/modeling_table.csv', dtype={'commodity_code':str}, parse_dates=['target_available_date'])
        features = pd.read_csv(ROOT/'data/processed/latest_features.csv', dtype={'commodity_code':str}, parse_dates=['month_ce'])
        sets = pd.read_csv(ROOT/'logs/metrics/03_feature_sets.csv',dtype={'feature_set':str}).set_index('feature_set')
        alphas = pd.read_csv(ROOT/'logs/metrics/04_ridge_alpha_selection.csv',dtype={'commodity_code':str,'feature_set':str})
        sources = json.loads((ROOT/'data/raw/sources.json').read_text())['sources']
        src = next(s for s in reversed(sources) if s['source_id'].startswith('imi-monthly-'))
        imi = pd.read_csv(ROOT/'data/raw'/src['file'],dtype={'commodityCode':str})
        imi['month_ce'] = pd.to_datetime(dict(year=imi.year-543,month=imi.month,day=1))
        def pv(p): return '< 0.001' if p < .001 else f'{p:.3f}'
        for detail in results:
            g = detail['group']
            assert detail['ready'] and detail['visiblePanels']==['g'+g] and not detail['exceptions']
            assert detail['scrollWidth']==detail['width']
            if detail['tableScroll']['scroll']>detail['tableScroll']['client']:
                assert detail['tableScroll']['moved']>0
            frame = forecasts[forecasts.group==g].sort_values('h')
            for cells,row in zip(detail['table'],frame.itertuples()):
                it = iteration2[(iteration2.commodity_code==g)&(iteration2.horizon==row.h)].iloc[0]
                assert cells[1:] == [row.series,f'{row.y_pred:+.1f}%',f'{100*row.skill_test:+.1f}%',pv(row.p_test),
                                    '● ผ่าน' if row.passes else '○ ไม่ผ่าน',
                                    f'{100*it.skill_vs_no_change:+.1f}% (p {pv(it.p_vs_no_change)})']
            hist, band, forecast = detail['plots'][0]
            base_month = pd.to_datetime(forecast[0]['x'],unit='ms')
            history = imi[(imi.commodityCode==g)&imi.month_ce.between('2015-01-01',base_month)].sort_values('month_ce')
            assert np.allclose([p['y'] for p in hist],history['index'])
            assert np.allclose([p['y'] for p in forecast],[frame.imi_t.iloc[0],*frame.index_pred])
            assert np.allclose([p['y'] for p in band],[frame.imi_t.iloc[0],*frame.index_high,*frame.index_low[::-1],frame.imi_t.iloc[0]])
            for trace,sid in zip(detail['drivers'],('DEXTHUS','DCOILBRENTEU')):
                expected = external[(external.series==sid)&external.month_ce.between(base_month-pd.DateOffset(months=59),base_month+pd.DateOffset(months=1))]
                assert np.allclose([p['y'] for p in trace],expected.full_mean)
            fs = frame[frame.h==3].series.iloc[0].split('/')[1]
            cols = sets.loc[fs,'features'].split('|')
            origin = base_month+pd.offsets.MonthBegin(2)+pd.Timedelta(days=14)
            train = modeling[(modeling.commodity_code==g)&(modeling.horizon==3)&(modeling.target_available_date<=origin)]
            alpha = alphas[(alphas.commodity_code==g)&(alphas.horizon==3)&(alphas.feature_set==fs)&alphas.selected].alpha.iloc[0]
            scaler = StandardScaler().fit(train[cols])
            fit = Ridge(alpha=alpha).fit(scaler.transform(train[cols]),train.target_y_pct)
            coef = pd.Series(fit.coef_,index=cols)
            coef = coef.reindex(coef.abs().sort_values().index).tail(10)
            assert np.allclose([p['x'] for p in detail['plots'][1][0]],coef)
            detail['numeric_checks_passed'] = True
        (OUT/'browser_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
        print(json.dumps([{k:v for k,v in r.items() if k not in ('kpis','table','findings','plots','drivers')} for r in results],indent=2))
    finally:
        proc.terminate(); proc.wait(timeout=15)
