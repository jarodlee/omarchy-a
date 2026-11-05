import importlib.util,tempfile,os,time
from pathlib import Path
with tempfile.TemporaryDirectory() as td:
 root=Path(td);p=root/'power';(p/'battery').mkdir(parents=True);(p/'lightning').mkdir()
 for supply,values in [('battery',{'capacity':'94','status':'Discharging','current_now':'-86000','voltage_now':'4199000','temp':'259','health':'Good'}),('lightning',{'online':'1','usb_type':'Unknown SDP DCP CDP C [BrickID]','input_current_limit':'1000000'})]:
  for n,v in values.items():(p/supply/n).write_text(v)
 os.environ['BATTERY_POWER_PATH']=str(p);os.environ['BATTERY_DATABASE']=str(root/'history.sqlite3')
 spec=importlib.util.spec_from_file_location('battery_monitor',Path(__file__).with_name('battery-monitor.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 row=m.snapshot();assert row['current_uA']==-86000 and row['temperature_deciC']==259 and row['capacity']==94
 m.initialize();old={**row,'timestamp':int(time.time())-8*86400};m.record(old);m.record(row)
 rows=m.history(24);assert len(rows)==1 and rows[0]['current_uA']==-86000
 with m.connection() as c:assert c.execute('SELECT COUNT(*) FROM samples').fetchone()[0]==1
 (p/'battery/current_now').unlink();assert m.snapshot()['current_uA'] is None
 print('PASS: signed current, nullable sensor and seven-day retention')
