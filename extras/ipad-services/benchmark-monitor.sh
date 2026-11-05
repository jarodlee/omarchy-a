set -euo pipefail
python3 - <<'PY'
import importlib.util,sys,time,tempfile,sqlite3,json,statistics,gzip
from pathlib import Path
sys.path.insert(0,'/opt/ipad-battery-monitor')
spec=importlib.util.spec_from_file_location('monitor_benchmark','/opt/ipad-battery-monitor/battery-monitor.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def measure(fn,n):
 wall=[];cpu=[]
 for _ in range(n):
  a=time.perf_counter();b=time.process_time();fn();cpu.append((time.process_time()-b)*1000);wall.append((time.perf_counter()-a)*1000)
 return {'mean_wall_ms':round(statistics.mean(wall),3),'mean_cpu_ms':round(statistics.mean(cpu),3),'max_wall_ms':round(max(wall),3)}
collector=m.SystemCollector()
def sample():return m.snapshot(),collector.collect()
result={'sampling':measure(sample,30),'temporary_test_database':True}
with tempfile.TemporaryDirectory(prefix='monitor-benchmark-',dir='/var/lib/omarchy-maintenance') as temp:
 m.DATABASE=Path(temp)/'fixture.sqlite3';m.initialize();now=int(time.time());start=now-1439*60
 battery=m.snapshot();system=collector.collect();system['boot_id']='benchmark-only';system['network_key']='benchmark0'
 battery_rows=[];system_rows=[]
 for i in range(1440):
  b={**battery,'timestamp':start+i*60};battery_rows.append(tuple(b[k] for k in ('timestamp','capacity','current_uA','temperature_deciC','input_limit_uA','status')))
  s={**system,'timestamp':start+i*60,'cpu_percent':float(i%31)*3,'load_1':(i%20)/10,'load_5':(i%15)/10,
      'net_rx_Bps':546.13,'net_tx_Bps':273.07,'disk_read_Bps':136.53,'disk_write_Bps':273.07,
      'net_rx_bytes':349000000+i*32768,'net_tx_bytes':137000000+i*16384,
      'disk_read_bytes':500000000+i*8192,'disk_write_bytes':900000000+i*16384}
  system_rows.append(tuple(s[k] for k in m.COLUMNS))
 with m.connection() as db:db.executemany('INSERT INTO samples VALUES (?,?,?,?,?,?)',battery_rows)
 before=m.DATABASE.stat().st_size
 with m.connection() as db:db.executemany('INSERT INTO system_samples VALUES ('+','.join('?' for _ in m.COLUMNS)+')',system_rows)
 result.update(system_history_rows=1440,system_history_disk_bytes=m.DATABASE.stat().st_size-before,whole_fixture_database_bytes=m.DATABASE.stat().st_size)
 def history():
  m.HISTORY_CACHE.clear();return m.history_payload(24)
 result['uncached_24h_history']=measure(history,10)
 h=history();d=m.current_payload();d.update(history=h['history'],system={'current':d['system']['current'],'history':h['system_history'],'summary':h['summary']},display_interval_seconds=h['display_interval_seconds'],window_start=h['window_start'],window_end=h['window_end'])
 payload=json.dumps(d,separators=(',',':')).encode()
 result.update(display_system_points=len(h['system_history']),display_battery_points=len(h['history']),full_history_json_bytes=len(payload),full_history_gzip_bytes=len(gzip.compress(payload)),current_json_bytes=len(json.dumps(m.current_payload(),separators=(',',':')).encode()))
 def io():
  return int(next(s.split(':')[1] for s in Path('/proc/self/io').read_text().splitlines() if s.startswith('write_bytes:')))
 written_before=io();counter=[0]
 with m.connection() as writer:
  def save():
   counter[0]+=1;b,s=sample();b['timestamp']=now+counter[0];s['timestamp']=b['timestamp'];m.record(b,s,writer)
  result['record']=measure(save,10);result['process_write_bytes_per_record']=(io()-written_before)//10
 # record includes sampling. This projection excludes page requests and is not a 24-hour CPU observation.
 result['projected_sampling_and_record_cpu_percent_one_core']=round(result['record']['mean_cpu_ms']/60000*100,5)
print(json.dumps(result))
PY
