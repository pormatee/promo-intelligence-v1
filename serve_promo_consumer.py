#!/usr/bin/env python3
from __future__ import annotations
import argparse, http.server, socketserver, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma','no-cache')
        self.send_header('Expires','0')
        super().end_headers()
class ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address=True

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--host',default='127.0.0.1'); ap.add_argument('--port',type=int,default=8082); ap.add_argument('--no-build',action='store_true'); a=ap.parse_args()
    if not a.no_build:
        r=subprocess.run([sys.executable,str(ROOT/'build_promo_consumer.py')],cwd=ROOT)
        if r.returncode: return r.returncode
    handler=lambda *args,**kwargs: Handler(*args,directory=str(ROOT),**kwargs)
    with ReuseTCPServer((a.host,a.port),handler) as httpd:
        print(f'PROMO_CONSUMER_URL=http://{a.host}:{a.port}/promo_consumer.html?v=1.8', flush=True)
        print('CACHE_MODE=NO_STORE', flush=True)
        try:httpd.serve_forever()
        except KeyboardInterrupt:print('\nหยุด server')
    return 0
if __name__=='__main__': raise SystemExit(main())
