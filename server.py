#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import http.server, socketserver, base64, os, yaml, time
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote
from utils import (find_directory, get_local_ip, generate_qr_code, get_file_icon,
                   identify_device, format_size, get_creation_time)

###############################################################################
# CONFIGURAZIONE
###############################################################################

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
cfg_path    = os.path.join(SCRIPT_DIR, "credentials.yaml")

with open(cfg_path, encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

PORT           = cfg["server"]["port"]
ROOT_DIRECTORY = os.path.abspath(os.path.expanduser(cfg["server"]["directory"]))
USERNAME       = cfg["auth"]["username"]
PASSWORD       = cfg["auth"]["password"]

if not os.path.exists(ROOT_DIRECTORY):
    print("⚠️  Directory non trovata, la cerco…")
    ROOT_DIRECTORY = find_directory(ROOT_DIRECTORY)
if not ROOT_DIRECTORY:
    print("❌  Nessuna directory valida — esco.")
    exit(1)

LOCAL_IP   = get_local_ip()
SERVER_URL = f"http://{LOCAL_IP}:{PORT}"

###############################################################################
# SERVER MULTITHREAD
###############################################################################

class ThreadingHTTPServer(ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

###############################################################################
# HANDLER
###############################################################################

class AuthHandler(http.server.SimpleHTTPRequestHandler):

    # ------- helper autenticazione -----------------------------------------
    def _ok_auth(self) -> bool:
        h = self.headers.get("Authorization", "")
        if not h.startswith("Basic "):
            return False
        try:
            user, pwd = base64.b64decode(h[6:]).decode().split(":", 1)
            return user == USERNAME and pwd == PASSWORD
        except Exception:
            return False

    def _auth_required(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="File Server"')
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    # ------- GET -----------------------------------------------------------
    def do_GET(self):
        if not self._ok_auth():
            self._auth_required(); return

        ua = self.headers.get("User-Agent", "unknown")
        print(f"📱 {self.client_address[0]} – {identify_device(ua)}")

        # Quick admin page to change the served root at runtime
        if self.path.rstrip('/') == '/set_root':
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = f"""
            <html><head><meta charset="utf-8"><title>Set Root Directory</title>
            <style>
                body {{ font-family: sans-serif; padding: 20px; line-height: 1.6; }}
                input {{ padding: 8px; border: 1px solid #ccc; border-radius: 4px; }}
                button {{ padding: 8px 15px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; }}
                button:hover {{ background: #218838; }}
                .back-link {{ display: inline-block; margin-top: 20px; text-decoration: none; color: #007bff; }}
            </style>
            </head><body>
            <h2>⚙️ Set Root Directory</h2>
            <p>Current root: <code>{ROOT_DIRECTORY}</code></p>
            <form method="POST" action="/set_root">
              <label>New root path:</label><br><br>
              <input name="new_root" value="{ROOT_DIRECTORY}" style="width:80%" required>
              <button type="submit">Set root</button>
            </form>
            <p><small>Use absolute paths or relative paths (expanded from user home).</small></p>
            <a href="/" class="back-link">← Back to Files</a>
            </body></html>
            """
            self.wfile.write(html.encode())
            return

        sub  = unquote(self.path.lstrip("/")).replace("\\", "/")
        path = os.path.join(ROOT_DIRECTORY, sub)

        if os.path.isdir(path):
            self._show_dir(path, self.path)
        elif os.path.isfile(path):
            self.path = self.path.replace("\\", "/")
            super().do_GET()
        else:
            self.send_error(404, "Not found")

    # ------- POST (upload con parser streaming) ----------------------------
    def do_POST(self):
        if not self._ok_auth():
            self._auth_required(); return

        # Special handler: change served root directory at runtime
        if self.path.rstrip('/') == '/set_root':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode(errors='ignore')
            from urllib.parse import parse_qs
            params = parse_qs(body)
            new_root = params.get('new_root', [None])[0]
            if not new_root:
                self._err('Campo new_root mancante'); return
            # Expand user and make absolute if needed
            new_root = os.path.expanduser(new_root)
            if not os.path.isabs(new_root):
                new_root = os.path.join(os.path.expanduser('~'), new_root)
            try:
                os.makedirs(new_root, exist_ok=True)
                global ROOT_DIRECTORY, cfg
                ROOT_DIRECTORY = new_root
                os.chdir(ROOT_DIRECTORY)
                # persist change in credentials.yaml
                cfg['server']['directory'] = ROOT_DIRECTORY
                with open(cfg_path, 'w', encoding='utf-8') as cf:
                    yaml.safe_dump(cfg, cf, default_flow_style=False, sort_keys=False, allow_unicode=True)

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write((
                    f"<html><body><h2>Root impostato su: {ROOT_DIRECTORY}</h2>"
                    f"<a href='/'>Vai alla Home</a></body></html>"
                ).encode())
                return
            except Exception as e:
                self._err(f"Impossibile impostare la directory: {e}"); return

        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self._err("Content-Type non supportato"); return

        # es. Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryX
        bstr = ctype.split("boundary=")[-1]
        boundary = ("--" + bstr).encode()        # compreso il prefisso "--"
        boundary_end = boundary + b"--"

        # dir di destinazione
        sub   = unquote(self.path.lstrip("/")).replace("\\", "/")
        ddir  = os.path.join(ROOT_DIRECTORY, sub)
        os.makedirs(ddir, exist_ok=True)

        r = self.rfile
        # 1. scorri finché trovi la prima linea boundary
        line = r.readline()
        while line.strip() != boundary:
            if not line: self._err("Bad multipart"); return
            line = r.readline()

        # 2. leggi header della parte
        headers = {}
        while True:
            line = r.readline()
            if line in (b"\r\n", b"\n", b""): break
            k, v = line.decode().split(":", 1)
            headers[k.strip().lower()] = v.strip()

        disp = headers.get("content-disposition", "")
        # es. form-data; name="file"; filename="something.iso"
        if "filename=" not in disp:
            self._err("Campo file mancante"); return
        filename = disp.split("filename=")[-1].strip('"')
        filename = os.path.basename(unquote(filename))
        dpath    = os.path.join(ddir, filename)

        # 3. copia dati fino al prossimo boundary
        CHUNK = 1024 * 1024   # 1 MiB
        with open(dpath, "wb") as out:
            prev = r.readline()
            while True:
                curr = r.readline()
                if curr.startswith(boundary):
                    # rimuovi CRLF finale da prev
                    out.write(prev.rstrip(b"\r\n"))
                    break
                out.write(prev)
                prev = curr

        print(f"✅  Upload completato → {dpath}")

        self.send_response(201)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write((
            f"<html><body><h2>File '{filename}' caricato!</h2>"
            f"<a href='{self.path}'>Indietro</a></body></html>"
        ).encode())

    # ------- directory listing + frontend ----------------------------------
    def _show_dir(self, local: str, req: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        up = os.path.dirname(req.rstrip("/"))
        backlink = "" if up == "" else f"<a href='{up}'>[Go&nbsp;up]</a>"

        html = f"""
        <html><head><meta charset="utf-8"><title>{req}</title>
        <style>
            .admin-btn {{
                position: absolute;
                top: 20px;
                right: 20px;
                padding: 10px 15px;
                background-color: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-family: sans-serif;
                font-size: 14px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .admin-btn:hover {{
                background-color: #0056b3;
            }}
            body {{ font-family: sans-serif; padding: 20px; }}
            h2 {{ margin-top: 0; }}
        </style>
        </head><body>
        <a href="/set_root" class="admin-btn">⚙️ Set Root</a>
        <h2>Directory: {req}</h2>{backlink}<hr>

        <h3>Upload file</h3>
        <form id="uForm">
            <input type="file" id="uFile" name="file" required>
            <button type="submit">Upload</button>
        </form>

        <div id="box" style="display:none;margin:20px 0;">
            <div style="display:flex;justify-content:space-between;">
                <span id="perc">0%</span><span id="speed">0 KB/s</span>
            </div>
            <div style="height:20px;background:#eee;border-radius:10px;">
                <div id="bar" style="height:100%;width:0%;background:#4CAF50;border-radius:10px;"></div>
            </div>
        </div>

        <script>
        document.getElementById('uForm').addEventListener('submit', e => {{
            e.preventDefault();
            const f = document.getElementById('uFile').files[0];
            if (!f) return;

            const fd = new FormData();
            fd.append('file', f);

            const x = new XMLHttpRequest();
            x.open('POST', window.location.pathname);

            x.upload.onprogress = ev => {{
                if (!ev.lengthComputable) return;
                const p = (ev.loaded / ev.total * 100).toFixed(1);
                const s = (ev.loaded / (ev.timeStamp / 1000) / 1024).toFixed(1);
                document.getElementById('box').style.display = 'block';
                document.getElementById('bar').style.width  = p + '%';
                document.getElementById('perc').textContent = p + '%';
                document.getElementById('speed').textContent = s + ' KB/s';
            }};

            x.onload  = () => {{ window.location.reload(); }};
            x.onerror = () => {{ alert('Upload error'); }};
            x.send(fd);
        }});
        </script>

        <hr><h3>Contents</h3><ul>
        """

        try:
            for item in sorted(os.listdir(local)):
                p = os.path.join(local, item)
                nxt = (req.strip("/") + "/" + item).lstrip("/")
                href = "/" + quote(nxt.replace("\\", "/"))
                if os.path.isdir(p):
                    html += f"<li>📁 <a href='{href}'>{item}</a></li>"
                else:
                    icon = get_file_icon(item)
                    size = format_size(os.path.getsize(p))
                    ctim = get_creation_time(p)
                    html += (f"<li>{icon} <a download href='{href}'>{item}</a> "
                             f"<small>({size}, {ctim})</small></li>")
            html += "</ul></body></html>"
        except OSError:
            html = f"<html><body><h2>Cannot list {req}</h2></body></html>"

        self.wfile.write(html.encode())

    # ------- helper pagina errore ------------------------------------------
    def _err(self, msg:str):
        self.send_response(400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<html><body><h2>{msg}</h2></body></html>".encode())

###############################################################################
# AVVIO
###############################################################################

os.chdir(ROOT_DIRECTORY)
print(f"✅  URL: http://localhost:{PORT}  ({SERVER_URL})")
print(f"📂  Path condiviso: {ROOT_DIRECTORY}")
print(f"🔐  Credenziali: {USERNAME}/{PASSWORD}")
print(f"⚙️   Cambia path: {SERVER_URL}/set_root")
print("📸  QR code:"); generate_qr_code(SERVER_URL)

with ThreadingHTTPServer(("", PORT), AuthHandler) as httpd:
    httpd.serve_forever()
