#!/usr/bin/env python3
from __future__ import annotations
import argparse, http.server, socketserver, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser(description='Build and serve Promo Intelligence Lab locally')
    ap.add_argument('--port',type=int,default=8081); ap.add_argument('--no-build',action='store_true'); a=ap.parse_args()
    if not a.no_build:
        r=subprocess.run([sys.executable,str(ROOT/'build_promo_lab.py')],cwd=ROOT)
        if r.returncode: return r.returncode
    path=ROOT/'promo_lab.html'
    if not path.exists(): print('ไม่พบ promo_lab.html'); return 2
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self,fmt,*args): print('LAB_HTTP='+fmt%args)
    class Server(socketserver.TCPServer): allow_reuse_address=True
    print(f'PROMO_LAB_URL=http://127.0.0.1:{a.port}/promo_lab.html')
    print('กด Ctrl+C เมื่อต้องการหยุด')
    import os; os.chdir(ROOT)
    with Server(('127.0.0.1',a.port),Handler) as s:
        try:s.serve_forever()
        except KeyboardInterrupt: pass
    return 0
if __name__=='__main__': raise SystemExit(main())
