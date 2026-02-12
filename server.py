#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import http.server, socketserver, base64, os, yaml, time
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote, parse_qs
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

# Sicurezza: Rate limiting + Validazione file
FAILED_ATTEMPTS = {}  # {ip: [timestamp, ...]}
ALLOWED_EXTENSIONS = {
    '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.mp3', '.mp4', '.avi', '.mov', '.mkv', '.flv',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.py', '.js', '.json', '.xml', '.html', '.css', '.cpp', '.java', '.c', '.h'
}
MAX_ATTEMPTS = 5
ATTEMPT_WINDOW = 900  # 15 minuti in secondi

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

    # ------- helper autenticazione con rate limiting ----------------------
    def _check_rate_limit(self):
        """Controlla rate limiting per autenticazione fallita (5 tentativi / 15 min)"""
        ip = self.client_address[0]
        now = time.time()
        
        if ip not in FAILED_ATTEMPTS:
            FAILED_ATTEMPTS[ip] = []
        
        # Rimuovi tentativi oltre la finestra
        FAILED_ATTEMPTS[ip] = [ts for ts in FAILED_ATTEMPTS[ip] if now - ts < ATTEMPT_WINDOW]
        
        # Se troppi tentativi, blocca
        if len(FAILED_ATTEMPTS[ip]) >= MAX_ATTEMPTS:
            return False, f"🚫 Troppi tentativi falliti da {ip}. Riprova tra 15 minuti."
        return True, ""
    
    def _ok_auth(self) -> bool:
        h = self.headers.get("Authorization", "")
        if not h.startswith("Basic "):
            return False
        try:
            user, pwd = base64.b64decode(h[6:]).decode().split(":", 1)
            auth_ok = user == USERNAME and pwd == PASSWORD
            
            if not auth_ok:
                # Incrementa contatore fallimenti
                ip = self.client_address[0]
                FAILED_ATTEMPTS[ip].append(time.time())
                print(f"⚠️  Auth fallita da {ip} ({len(FAILED_ATTEMPTS[ip])}/{MAX_ATTEMPTS} tentativi)")
            else:
                # Pulisci i tentativi falliti se auth riuscita
                ip = self.client_address[0]
                if ip in FAILED_ATTEMPTS:
                    FAILED_ATTEMPTS[ip] = []
            
            return auth_ok
        except Exception:
            return False

    def _auth_required(self):
        # Controlla rate limiting
        rate_ok, rate_msg = self._check_rate_limit()
        if not rate_ok:
            self.send_response(429)  # Too Many Requests
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body><h2>{rate_msg}</h2></body></html>".encode())
            return
        
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

        # Extract path and sorting parameters
        path_and_query = self.path.split('?', 1)
        req_path = path_and_query[0]
        query_params = parse_qs(path_and_query[1]) if len(path_and_query) > 1 else {}
        sort_by = query_params.get('sort', ['name'])[0]  # 'name' or 'size'
        sort_dir = query_params.get('dir', ['asc'])[0]   # 'asc' or 'desc'

        sub  = unquote(req_path.lstrip("/")).replace("\\", "/")
        path = os.path.join(ROOT_DIRECTORY, sub)

        if os.path.isdir(path):
            self._show_dir(path, req_path, sort_by, sort_dir)
        elif os.path.isfile(path):
            # Log del download
            file_size = os.path.getsize(path)
            print(f"📥 Download: {os.path.basename(path)} ({format_size(file_size)}) da {self.client_address[0]}")
            self.path = self.path.replace("\\", "/")
            try:
                super().do_GET()
            except (BrokenPipeError, ConnectionResetError):
                # Client ha interrotto il download (normale con file grandi su mobile)
                pass
            except Exception as e:
                print(f"⚠️  Errore durante download: {type(e).__name__}: {e}")
        else:
            self.send_error(404, "Not found")

    # ------- POST (upload con parser streaming) ----------------------------
    def do_POST(self):
        if not self._ok_auth():
            self._auth_required(); return
        
        # Controlla rate limiting anche durante upload
        rate_ok, rate_msg = self._check_rate_limit()
        if not rate_ok:
            self.send_response(429)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body><h2>{rate_msg}</h2></body></html>".encode())
            return

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
        
        # ✅ Validazione tipo file: whitelist estensioni
        _, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        if ext_lower not in ALLOWED_EXTENSIONS:
            blocked_msg = f"🚫 Tipo file non consentito: {ext}<br>Estensioni consentite: {', '.join(sorted(list(ALLOWED_EXTENSIONS)[:15]))}..."
            print(f"⚠️  Upload bloccato da {self.client_address[0]}: {filename} ({ext_lower})")
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body><h2>{blocked_msg}</h2><a href='javascript:history.back()'>Indietro</a></body></html>".encode())
            return
        
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

        # Log dell'upload con dettagli
        file_size = os.path.getsize(dpath)
        print(f"📤 Upload: {filename} ({format_size(file_size)}) da {self.client_address[0]} → {dpath}")

        self.send_response(201)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write((
            f"<html><body><h2>File '{filename}' caricato!</h2>"
            f"<a href='{self.path}'>Indietro</a></body></html>"
        ).encode())

    # ------- directory listing + frontend ----------------------------------
    def _show_dir(self, local: str, req: str, sort_by: str = 'name', sort_dir: str = 'asc'):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        up = os.path.dirname(req.rstrip("/"))
        backlink = "" if up == "" else f"<a href='{up}'>[Go&nbsp;up]</a>"

        # Build sort buttons
        sort_buttons = f"""
        <div style="margin: 20px 0; padding: 10px; background: #f5f5f5; border-radius: 5px;">
            <strong>Ordina per:</strong>
            <a href='{req}?sort=name&dir=asc' style="padding: 5px 10px; margin: 0 5px; background: {'#007bff' if sort_by=='name' and sort_dir=='asc' else '#ccc'}; color: white; text-decoration: none; border-radius: 3px;">📝 Nome (A→Z)</a>
            <a href='{req}?sort=name&dir=desc' style="padding: 5px 10px; margin: 0 5px; background: {'#007bff' if sort_by=='name' and sort_dir=='desc' else '#ccc'}; color: white; text-decoration: none; border-radius: 3px;">📝 Nome (Z→A)</a>
            <a href='{req}?sort=size&dir=asc' style="padding: 5px 10px; margin: 0 5px; background: {'#007bff' if sort_by=='size' and sort_dir=='asc' else '#ccc'}; color: white; text-decoration: none; border-radius: 3px;">📊 Dimensione (min→max)</a>
            <a href='{req}?sort=size&dir=desc' style="padding: 5px 10px; margin: 0 5px; background: {'#007bff' if sort_by=='size' and sort_dir=='desc' else '#ccc'}; color: white; text-decoration: none; border-radius: 3px;">📊 Dimensione (max→min)</a>
            <a href='{req}?sort=format&dir=asc' style="padding: 5px 10px; margin: 0 5px; background: {'#007bff' if sort_by=='format' and sort_dir=='asc' else '#ccc'}; color: white; text-decoration: none; border-radius: 3px;">📄 Formato (A→Z)</a>
            <a href='{req}?sort=format&dir=desc' style="padding: 5px 10px; margin: 0 5px; background: {'#007bff' if sort_by=='format' and sort_dir=='desc' else '#ccc'}; color: white; text-decoration: none; border-radius: 3px;">📄 Formato (Z→A)</a>
            <a href='{req}?sort=date&dir=asc' style="padding: 5px 10px; margin: 0 5px; background: {'#007bff' if sort_by=='date' and sort_dir=='asc' else '#ccc'}; color: white; text-decoration: none; border-radius: 3px;">📅 Data (vecchi→nuovi)</a>
            <a href='{req}?sort=date&dir=desc' style="padding: 5px 10px; margin: 0 5px; background: {'#007bff' if sort_by=='date' and sort_dir=='desc' else '#ccc'}; color: white; text-decoration: none; border-radius: 3px;">📅 Data (nuovi→vecchi)</a>
        </div>
        """

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

        <hr>
        {sort_buttons}
        <hr><h3>Contents</h3><ul>
        """

        try:
            items = os.listdir(local)
            
            # Sort items based on parameters
            if sort_by == 'size':
                # Sort by file size (with name as secondary sort), directories get size 0
                def get_sort_key(item):
                    path = os.path.join(local, item)
                    try:
                        size = os.path.getsize(path) if os.path.isfile(path) else 0
                    except:
                        size = 0
                    return (size, item)
                items = sorted(items, key=get_sort_key, reverse=(sort_dir == 'desc'))
            elif sort_by == 'format':
                # Sort by file extension/format
                def get_sort_key(item):
                    path = os.path.join(local, item)
                    if os.path.isdir(path):
                        ext = ''
                    else:
                        ext = os.path.splitext(item)[1].lower()
                    return (ext, item)
                items = sorted(items, key=get_sort_key, reverse=(sort_dir == 'desc'))
            elif sort_by == 'date':
                # Sort by modification date
                def get_sort_key(item):
                    path = os.path.join(local, item)
                    try:
                        mtime = os.path.getmtime(path)
                    except:
                        mtime = 0
                    return (mtime, item)
                items = sorted(items, key=get_sort_key, reverse=(sort_dir == 'desc'))
            else:
                # Sort by name (default)
                items = sorted(items, reverse=(sort_dir == 'desc'))
            
            for item in items:
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

# Verifica se la porta è già in uso e prova a liberarla
import socket
def check_port_available(port):
    """Controlla se una porta è disponibile"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        sock.bind(("", port))
        sock.close()
        return True
    except OSError:
        sock.close()
        return False

if not check_port_available(PORT):
    print(f"⚠️  Porta {PORT} già in uso. Cerco di liberarla...")
    import subprocess
    try:
        # Trova e uccidi il processo che usa la porta
        result = subprocess.run(['lsof', '-ti', f':{PORT}'], 
                              capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                subprocess.run(['kill', '-9', pid], timeout=5)
                print(f"   Terminato processo {pid}")
            time.sleep(1)
        
        if not check_port_available(PORT):
            print(f"❌ Impossibile liberare la porta {PORT}")
            print(f"   Esegui manualmente: lsof -ti:{PORT} | xargs kill -9")
            exit(1)
        else:
            print(f"✅ Porta {PORT} ora disponibile")
    except Exception as e:
        print(f"❌ Errore durante la liberazione della porta: {e}")
        exit(1)

os.chdir(ROOT_DIRECTORY)
print(f"✅  URL: http://localhost:{PORT}  ({SERVER_URL})")
print(f"📂  Path condiviso: {ROOT_DIRECTORY}")
print(f"🔐  Credenziali: {USERNAME}/{PASSWORD}")
print(f"⚙️   Cambia path: {SERVER_URL}/set_root")
print("📸  QR code:"); generate_qr_code(SERVER_URL)

try:
    with ThreadingHTTPServer(("", PORT), AuthHandler) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\n\n👋 Server fermato dall'utente")
except Exception as e:
    print(f"\n\n❌ Errore del server: {e}")
    exit(1)
