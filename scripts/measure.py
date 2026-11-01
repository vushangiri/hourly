"""Repeatable local CPU/payload measurements; not a network or DB benchmark."""
from pathlib import Path
import gzip,json,statistics,time,sys
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hourly.domain import timestamps,calculate,period_range
root=Path(__file__).resolve().parents[1]
samples=[]
for _ in range(1000):
    t=time.perf_counter_ns()
    a,b=timestamps(date(2026,10,4),'00:00','04:00','Australia/Sydney')
    calculate(a,b,0,'25.00')
    period_range(date(2026,11,1),'Month',0)
    samples.append((time.perf_counter_ns()-t)/1000)
result={'scope':'local pure-domain call bundle; not DB/HTTP/mobile latency',
        'samples':len(samples),'median_microseconds':round(statistics.median(samples),2),
        'p95_microseconds':round(sorted(samples)[949],2),'assets':{}}
for name in ['app.js','app.css','auth.js','sw.js']:
    data=(root/'hourly/static'/name).read_bytes()
    result['assets'][name]={'bytes':len(data),'gzip_bytes':len(gzip.compress(data))}
print(json.dumps(result,indent=2))
