"""Disposable local UI fixture; no real user credentials or learning records."""
import importlib.util
from pathlib import Path
import tempfile
import secrets
import time
import threading

root=Path(__file__).parent.resolve()
spec=importlib.util.spec_from_file_location('server',root/'taxonomy-server.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory(prefix='cnm-ui-fixture-') as state:
    store=m.Store(state)
    admin=store.register({'username':'preview_admin','password':'fixture-password-only-0123456789'},store.bootstrap.read_text())
    invite=secrets.token_urlsafe(24)
    with store.connect() as c:c.execute('INSERT INTO invites VALUES(?,?,0)',(m.digest(invite),time.time()+3600))
    student=store.register({'username':'preview_student','password':'fixture-password-only-0123456789','invite':invite})
    class PreviewHandler(m.Handler):
        # Only this disposable localhost fixture has synthetic session shortcuts.
        # Never included in production server or uploaded to the iPad.
        def do_GET(self):
            if self.path in ['/__preview/admin','/__preview/student']:
                u=admin if self.path.endswith('admin') else student
                token=store.session(u)
                self.send_response(303);self.send_header('Location','/children/')
                self.send_header('Set-Cookie',f'{m.SESSION_COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict')
                self.end_headers();return
            super().do_GET()
    server=m.Server(('127.0.0.1',38867),root/'taxonomy-account-site',store,'http://localhost:38867')
    server.RequestHandlerClass=PreviewHandler
    timer=threading.Timer(600,server.shutdown);timer.daemon=True;timer.start()
    try:server.serve_forever()
    finally:server.server_close();timer.cancel()
