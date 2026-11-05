import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

spec=importlib.util.spec_from_file_location('taxonomy_server',Path(__file__).with_name('taxonomy-server.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=module.Store(self.temp.name)
        self.site=Path(self.temp.name)/'site';self.site.mkdir();(self.site/'index.html').write_text('site')
        self.server=module.Server(('127.0.0.1',0),self.site,self.store,'https://math.ghtxx.cn')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
        self.addCleanup(self.temp.cleanup);self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.password='fixture-password-only-0123456789'
        self.admin=self.store.register({'username':'admin_fixture','password':self.password},self.store.bootstrap.read_text())
        self.token=self.store.session(self.admin)

    def call(self,path,body=None,token=None,origin='https://math.ghtxx.cn',method='POST'):
        h={'Origin':origin,'Content-Type':'application/json'}
        if token:h['Cookie']=module.SESSION_COOKIE+'='+token
        r=urllib.request.Request(self.url+path,headers=h,data=json.dumps(body or {}).encode() if method!='GET' else None,method=method)
        try:f=urllib.request.urlopen(r,timeout=10)
        except urllib.error.HTTPError as e:f=e
        with f:
            raw=f.read()
            try:d=json.loads(raw)
            except ValueError:d=raw.decode()
            return f.status,d,f.headers

    def second(self):
        status,d,_=self.call('/api/invites',token=self.token);self.assertEqual(status,200)
        u=self.store.register({'username':'other_fixture','password':self.password,'invite':d['invite']})
        return u,self.store.session(u)

    def test_unauthenticated_and_origin_boundaries(self):
        self.assertEqual(self.call('/api/state/read')[0],401)
        self.assertEqual(self.call('/api/state/read',token=self.token,origin='https://other.ghtxx.cn')[0],403)
        self.assertEqual(self.call('/api/me',token=self.token,method='GET')[0],404)
        self.assertEqual(self.call('/../learning.sqlite3',method='GET')[0],404)

    def test_isolation_and_server_derived_identity(self):
        other,token=self.second()
        data={'cnmChildren.v1':json.dumps({'v':1,'children':[{'id':'private-child'}]})}
        self.assertEqual(self.call('/api/state',{'revision':0,'data':data,'user_id':other['id']},self.token,method='PUT')[0],200)
        self.assertEqual(self.call('/api/state/read',token=token)[1]['data'],{})
        self.assertEqual(self.call('/api/state/read',token=self.token)[1]['data'],data)
        self.assertEqual(self.call('/api/invites',token=token)[0],403)

    def test_invite_single_use_and_setup_closed(self):
        _,d,_=self.call('/api/invites',token=self.token)
        self.store.register({'username':'first_fixture','password':self.password,'invite':d['invite']})
        with self.assertRaises(module.Problem):self.store.register({'username':'third_fixture','password':self.password,'invite':d['invite']})
        self.assertEqual(self.call('/api/auth/setup',{'username':'new_admin','password':self.password})[0],403)
        self.assertFalse(self.store.bootstrap.exists())

    def test_login_session_flags_and_logout(self):
        status,_,headers=self.call('/api/auth/login',{'username':'admin_fixture','password':self.password})
        self.assertEqual(status,200)
        cookie=headers.get_all('Set-Cookie')[0]
        for flag in ['__Host-','Secure','HttpOnly','SameSite=Strict','Path=/']:self.assertIn(flag,cookie)
        self.assertNotIn(self.password,self.store.path.read_bytes().decode(errors='ignore'))
        self.assertEqual(self.call('/api/auth/logout',token=self.token)[0],200)
        self.assertEqual(self.call('/api/state/read',token=self.token)[0],401)

    def test_compare_and_swap_conflict_no_lost_update(self):
        uid=self.admin['id']
        def write(v):
            try:self.store.put_state(uid,{'revision':0,'data':{'cnmChildren.v1':json.dumps({'writer':v})}});return 200
            except module.Problem as e:return e.status
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(write,[1,2]))
        self.assertEqual(sorted(results),[200,409]);self.assertEqual(self.store.get_state(uid)['revision'],1)

    def test_limits_private_no_cache_and_expiration(self):
        self.assertEqual(self.call('/api/state',{'revision':0,'data':{'arbitrary':'{}'}},self.token,method='PUT')[0],400)
        self.assertEqual(self.call('/api/state',{'revision':0,'data':{'cnmChildren.v1':'not json'}},self.token,method='PUT')[0],400)
        _,_,h=self.call('/api/state/read',token=self.token);self.assertEqual(h['Cache-Control'],'no-store')
        with self.store.connect() as c:c.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.call('/api/state/read',token=self.token)[0],401)

    def test_bootstrap_and_backup(self):
        with tempfile.TemporaryDirectory() as root:
            first=module.Store(root);key=first.bootstrap.read_text()
            self.assertFalse(first.valid_bootstrap('invalid'));self.assertFalse(first.valid_bootstrap('无效授权'));self.assertTrue(first.valid_bootstrap(key))
            first.register({'username':'initial_admin','password':self.password},key)
            self.assertFalse(first.valid_bootstrap(key))
        self.store.put_state(self.admin['id'],{'revision':0,'data':{'cnmChildren.v1':'{"v":1}'}})
        self.store.backup();backup=next((Path(self.temp.name)/'backups').glob('*.sqlite3'))
        self.assertEqual(backup.stat().st_mode&0o777,0o600)
        with sqlite3.connect(backup) as c:self.assertEqual(c.execute('SELECT revision FROM states').fetchone()[0],1)

if __name__=='__main__':unittest.main()
