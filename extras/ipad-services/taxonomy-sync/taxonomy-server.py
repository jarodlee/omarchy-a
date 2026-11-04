#!/usr/bin/env python3
"""Authenticated, revisioned per-user storage for the static taxonomy site."""
import argparse
import hashlib
import hmac
import http.cookies
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import threading
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

KEYS = {'cnmChildren.v1', 'cnmChildren.records.v1', 'cnmBlind.local.v1',
        'cnmDiagnose.settings.v2', 'cnmDiagnose.seen.v1'} | {
    p+'Diagnose.session.'+v for p,v in [('cnm','v2'),('cne','v2'),('cnp','v2'),
    ('cnc','v2'),('cns','v1'),('cnd','v1'),('cnh','v1'),('cng','v1'),('cnb','v1')]}
MAX_BODY = 10 * 1024 * 1024
SESSION_COOKIE = '__Host-cnm_session'
BOOT_COOKIE = '__Host-cnm_bootstrap'

class Problem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

class Store:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / 'learning.sqlite3'
        self.bootstrap = self.root / 'setup-token'
        with self.connect() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL, password TEXT NOT NULL, admin INTEGER NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS states(user_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                data TEXT NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS invites(token TEXT PRIMARY KEY, expires REAL NOT NULL, used INTEGER NOT NULL);
            ''')
            empty = c.execute('SELECT count(*) FROM users').fetchone()[0] == 0
        self.path.chmod(0o600)
        if empty and not self.bootstrap.exists():
            fd=os.open(self.bootstrap, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
            with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32))
        self.rates = {}
        self.rate_lock = threading.Lock()
        self.password_slots = threading.BoundedSemaphore(2)

    def connect(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def initialized(self):
        with self.connect() as c:return bool(c.execute('SELECT 1 FROM users LIMIT 1').fetchone())

    def valid_bootstrap(self, token):
        return (isinstance(token,str) and token.isascii() and not self.initialized() and self.bootstrap.exists() and
                hmac.compare_digest(self.bootstrap.read_text().strip(), token or ''))

    def throttle(self, address):
        now=time.time()
        with self.rate_lock:
            self.rates={k:v for k,v in self.rates.items() if v[0]>now-600}
            at,count=self.rates.get(address,(now,0))
            if count>=20:raise Problem(429,'尝试次数过多，请十分钟后再试。')
            if len(self.rates)>10000:raise Problem(503,'登录服务繁忙，请稍后重试。')
            self.rates[address]=(at,count+1)

    def password_hash(self, password, salt):
        if not self.password_slots.acquire(blocking=False):raise Problem(503,'登录服务繁忙，请稍后重试。')
        try:return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
        finally:self.password_slots.release()

    def credentials(self, body):
        name=body.get('username','')
        password=body.get('password','')
        if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9_.@+\-]{3,80}',name):
            raise Problem(400,'账号请使用 3–80 位小写字母、数字或邮箱字符。')
        if not isinstance(password,str) or not 10<=len(password)<=256:
            raise Problem(400,'密码长度应为 10–256 个字符。')
        try:password.encode('utf-8')
        except UnicodeEncodeError:raise Problem(400,'密码包含无效字符，请重新输入。')
        return name,password

    def register(self, body, bootstrap_token=None):
        name,password=self.credentials(body)
        salt=secrets.token_hex(16)
        hashed=self.password_hash(password,salt)
        uid=str(uuid.uuid4())
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            empty=not c.execute('SELECT 1 FROM users LIMIT 1').fetchone()
            if bootstrap_token is not None:
                if not empty or not self.valid_bootstrap(bootstrap_token):raise Problem(403,'初始化授权无效或已使用。')
                admin=1
            else:
                code=body.get('invite','')
                if not isinstance(code,str) or not code.isascii() or len(code)>128:raise Problem(400,'邀请码格式错误。')
                invite=c.execute('SELECT * FROM invites WHERE token=?',(digest(code),)).fetchone()
                if empty or not invite or invite['used'] or invite['expires']<=time.time():
                    raise Problem(403,'邀请码无效、过期或已使用。')
                c.execute('UPDATE invites SET used=1 WHERE token=?',(digest(code),))
                admin=0
            try:c.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(uid,name,salt,hashed,admin,time.time()))
            except sqlite3.IntegrityError:raise Problem(409,'账号已存在，请换一个或登录。')
            c.execute('INSERT INTO states VALUES(?,0,?,?)',(uid,'{}',time.time()))
        if admin:self.bootstrap.unlink(missing_ok=True)
        return {'id':uid,'username':name,'admin':bool(admin)}

    def login(self, body):
        name,password=self.credentials(body)
        with self.connect() as c:u=c.execute('SELECT * FROM users WHERE name=?',(name,)).fetchone()
        salt=u['salt'] if u else '00'*16
        check=self.password_hash(password,salt)
        if not u or not hmac.compare_digest(u['password'],check):raise Problem(401,'账号或密码不正确。')
        return {'id':u['id'],'username':u['name'],'admin':bool(u['admin'])}

    def session(self, user):
        token=secrets.token_urlsafe(32)
        with self.connect() as c:
            c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            c.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),user['id'],time.time()+7*86400))
        return token

    def user(self, token):
        if not token:return None
        with self.connect() as c:
            u=c.execute('SELECT u.id,u.name,u.admin FROM sessions s JOIN users u ON u.id=s.user_id '
                        'WHERE s.token=? AND s.expires>?',(digest(token),time.time())).fetchone()
        return {'id':u['id'],'username':u['name'],'admin':bool(u['admin'])} if u else None

    def get_state(self, uid):
        with self.connect() as c:r=c.execute('SELECT * FROM states WHERE user_id=?',(uid,)).fetchone()
        if not r:raise Problem(404,'账号记录不存在。')
        return {'revision':r['revision'],'data':json.loads(r['data'])}

    def put_state(self, uid, body):
        revision=body.get('revision')
        data=body.get('data')
        if type(revision) is not int or revision<0 or not isinstance(data,dict) or set(data)-KEYS:
            raise Problem(400,'同步数据格式错误。')
        for value in data.values():
            if not isinstance(value,str):raise Problem(400,'记录格式错误。')
            try:json.loads(value)
            except (ValueError,RecursionError):raise Problem(400,'记录不是有效 JSON。')
        encoded=json.dumps(data,ensure_ascii=False)
        if len(encoded.encode())>8*1024*1024:raise Problem(413,'单个账号记录不能超过 8 MB，请先导出旧记录。')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            cur=c.execute('UPDATE states SET revision=revision+1,data=?,updated=? '
                          'WHERE user_id=? AND revision=?',(encoded,time.time(),uid,revision))
            if cur.rowcount!=1:raise Problem(409,'另一台设备已更新记录。本机修改已保留，请处理同步冲突。')
        return {'revision':revision+1}

    def backup(self):
        folder=self.root/'backups';folder.mkdir(exist_ok=True,mode=0o700)
        p=folder/(time.strftime('%Y-%m-%d')+'.sqlite3')
        with self.connect() as src,sqlite3.connect(p) as dst:src.backup(dst)
        p.chmod(0o600)
        for old in sorted(folder.glob('*.sqlite3'))[:-7]:old.unlink()

class Server(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=16
    def __init__(self, address, site, store, origin):
        self.site=Path(site).resolve();self.store=store;self.origin=origin
        self.slots=threading.BoundedSemaphore(12)
        self.api_slots=threading.BoundedSemaphore(2)
        super().__init__(address,Handler)
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):request.close();return
        try:super().process_request(request,address)
        except BaseException:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(args[2].site),**kwargs)
    def setup(self):
        super().setup();self.connection.settimeout(20)
    def log_message(self,fmt,*args):
        # Never log bodies, credentials, cookies or private learning records.
        pass
    def list_directory(self,path):self.send_error(404);return None
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"frame-ancestors 'none'; object-src 'none'; base-uri 'self'")
        if self.path.startswith('/api/') or self.path in ['/account.html','/assets/server-sync.js','/sw.js']:
            self.send_header('Cache-Control','no-store')
        super().end_headers()
    def cookie(self,name):
        try:
            jar=http.cookies.SimpleCookie();jar.load(self.headers.get('Cookie',''))
            return jar[name].value if name in jar else None
        except http.cookies.CookieError:return None
    def json(self,status,data,cookies=()):
        b=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(b)))
        for cookie in cookies:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(b)
    def body(self):
        if self.headers.get('Transfer-Encoding'):raise Problem(400,'不支持该请求编码。')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise Problem(415,'请提交 JSON。')
        try:length=int(self.headers.get('Content-Length','-1'))
        except ValueError:raise Problem(400,'请求长度错误。')
        limit=MAX_BODY if self.command=='PUT' and self.path=='/api/state' else 16384
        if not 0<=length<=limit:raise Problem(413,'请求过大。')
        try:b=json.loads(self.rfile.read(length))
        except (ValueError,RecursionError):raise Problem(400,'JSON 格式错误。')
        if not isinstance(b,dict):raise Problem(400,'请求格式错误。')
        return b
    def auth(self):
        u=self.server.store.user(self.cookie(SESSION_COOKIE))
        if not u:raise Problem(401,'请先登录。')
        return u
    def api(self,method):
        if not self.server.api_slots.acquire(blocking=False):
            self.close_connection=True
            return self.json(503,{'error':'账号同步暂时繁忙，请稍后重试。'})
        try:return self.api_request(method)
        finally:self.server.api_slots.release()
    def api_request(self,method):
        try:
            path=self.path.split('?')[0];s=self.server.store
            if method!='GET' and self.headers.get('Origin')!=self.server.origin:
                raise Problem(403,'请求来源不正确，请刷新本站后重试。')
            if method=='GET' and path=='/api/health':return self.json(200,{'ok':True,'storage':'sqlite','initialized':s.initialized()})
            if method=='POST' and path=='/api/me':
                self.body()
                return self.json(200,{'user':s.user(self.cookie(SESSION_COOKIE)),
                'setupRequired':not s.initialized(),'canSetup':s.valid_bootstrap(self.cookie(BOOT_COOKIE)),
                'keys':sorted(KEYS)})
            if method=='POST' and path.startswith('/api/auth/'):
                s.throttle(self.headers.get('CF-Connecting-IP') or self.client_address[0])
                b=self.body();cookie=[]
                if path=='/api/auth/bootstrap':
                    if not isinstance(b.get('token'),str) or not s.valid_bootstrap(b['token']):raise Problem(403,'初始化授权无效。')
                    return self.json(200,{'ok':True},[f'{BOOT_COOKIE}={b["token"]}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=900'])
                if path=='/api/auth/setup':u=s.register(b,bootstrap_token=self.cookie(BOOT_COOKIE) or '')
                elif path=='/api/auth/register':u=s.register(b)
                elif path=='/api/auth/login':u=s.login(b)
                elif path=='/api/auth/logout':
                    token=self.cookie(SESSION_COOKIE)
                    if token:
                        with s.connect() as c:c.execute('DELETE FROM sessions WHERE token=?',(digest(token),))
                    return self.json(200,{'ok':True},[f'{SESSION_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0'])
                else:raise Problem(404,'接口不存在。')
                token=s.session(u)
                cookie=[f'{SESSION_COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=604800',
                        f'{BOOT_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0']
                return self.json(200,{'user':u},cookie)
            u=self.auth()
            if path=='/api/state/read' and method=='POST':
                self.body()
                return self.json(200,s.get_state(u['id']))
            if path=='/api/state/version' and method=='POST':
                self.body()
                with s.connect() as c:r=c.execute('SELECT revision FROM states WHERE user_id=?',(u['id'],)).fetchone()
                return self.json(200,{'revision':r['revision']})
            if path=='/api/state' and method=='PUT':return self.json(200,s.put_state(u['id'],self.body()))
            if path=='/api/invites' and method=='POST':
                self.body()
                if not u['admin']:raise Problem(403,'只有管理员能生成邀请码。')
                token=secrets.token_urlsafe(24)
                with s.connect() as c:
                    c.execute('DELETE FROM invites WHERE used=1 OR expires<?',(time.time(),))
                    c.execute('INSERT INTO invites VALUES(?,?,0)',(digest(token),time.time()+7*86400))
                return self.json(200,{'invite':token,'expiresInDays':7})
            raise Problem(404,'接口不存在。')
        except Problem as e:self.json(e.status,{'error':e.message})
        except (OSError,sqlite3.Error):self.json(503,{'error':'存储暂时不可用，请稍后重试。本机修改请保留。'})
    def do_GET(self):
        if self.path.split('?')[0].startswith('/api/'):return self.api('GET')
        super().do_GET()
    def do_HEAD(self):
        if self.path.split('?')[0].startswith('/api/'):return self.send_error(405)
        super().do_HEAD()
    def do_POST(self):self.api('POST')
    def do_PUT(self):self.api('PUT')

def main():
    p=argparse.ArgumentParser();p.add_argument('--site',default='/opt/cn-math-taxonomy/current')
    p.add_argument('--state',default='/var/lib/cn-math-taxonomy');p.add_argument('--port',type=int,default=3002)
    p.add_argument('--origin',default='https://math.ghtxx.cn');p.add_argument('--backup',action='store_true')
    a=p.parse_args();os.umask(0o077);store=Store(a.state)
    if a.backup:store.backup();return
    Server(('127.0.0.1',a.port),a.site,store,a.origin).serve_forever()

if __name__=='__main__':main()
