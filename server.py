import http.server
import socketserver
import base64
import os
import yaml

# Import the utility functions from utils.py
from utils import (
    find_directory,
    get_local_ip,
    generate_qr_code,
    get_file_icon,
    identify_device,
    format_size,       # <-- NEW
    get_creation_time  # <-- NEW
)

from urllib.parse import unquote, quote

###############################################################################
# LOAD CONFIGURATION
###############################################################################

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "credentials.yaml")

try:
    with open(CONFIG_PATH, "r") as file:
        config = yaml.safe_load(file)
except FileNotFoundError:
    print(f"❌ Error: Configuration file not found at {CONFIG_PATH}")
    exit(1)

PORT = config["server"]["port"]
ROOT_DIRECTORY = config["server"]["directory"]
USERNAME = config["auth"]["username"]
PASSWORD = config["auth"]["password"]

###############################################################################
# VALIDATE OR FIND DIRECTORY
###############################################################################

if not os.path.exists(ROOT_DIRECTORY):
    print(f"⚠️ Directory '{ROOT_DIRECTORY}' not found! Searching...")
    ROOT_DIRECTORY = find_directory(ROOT_DIRECTORY)

if not ROOT_DIRECTORY:
    print("❌ Could not locate a valid directory. Exiting.")
    exit(1)

###############################################################################
# PREPARE LOCAL IP & SERVER URL
###############################################################################

LOCAL_IP = get_local_ip()
SERVER_URL = f"http://{LOCAL_IP}:{PORT}"

###############################################################################
# DEFINE REQUEST HANDLER
###############################################################################

class AuthHandler(http.server.SimpleHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(401)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('WWW-Authenticate', 'Basic realm="File Server"')
        self.end_headers()

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('WWW-Authenticate', 'Basic realm="File Server"')
        self.end_headers()
        self.wfile.write(b'Authentication required!')

    def do_GET(self):
        # Check authentication
        auth_header = self.headers.get('Authorization')
        if auth_header is None or not self.is_authenticated(auth_header):
            self.do_AUTHHEAD()
            return

        # Identify device from User-Agent
        user_agent = self.headers.get('User-Agent', 'Unknown Device')
        device_type = identify_device(user_agent)
        print(f"📱 New connection: {self.client_address[0]} - Device: {device_type}")

        requested_path = self.path
        decoded_subpath = unquote(requested_path.lstrip("/")).replace('\\', '/')
        local_path = os.path.join(ROOT_DIRECTORY, decoded_subpath)

        # Serve file or show directory
        if os.path.isfile(local_path):
            self.path = requested_path.replace('\\', '/')
            super().do_GET()
        elif os.path.isdir(local_path):
            self.show_directory(local_path, requested_path)
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        # Check authentication
        auth_header = self.headers.get('Authorization')
        if auth_header is None or not self.is_authenticated(auth_header):
            self.do_AUTHHEAD()
            return

        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' in content_type:
            boundary = content_type.split("boundary=")[-1].encode()
            raw_data = self.rfile.read(int(self.headers['Content-Length']))

            requested_path = self.path
            decoded_subpath = unquote(requested_path.lstrip("/")).replace('\\', '/')
            local_dir = os.path.join(ROOT_DIRECTORY, decoded_subpath)

            parts = raw_data.split(boundary)
            for part in parts:
                if b'filename=\"' in part:
                    header, file_data = part.split(b"\r\n\r\n", 1)
                    filename = header.split(b'filename=\"')[1].split(b'\"')[0].decode()
                    filename = unquote(filename)

                    file_path = os.path.join(local_dir, os.path.basename(filename))
                    with open(file_path, "wb") as f:
                        f.write(file_data.strip(b"\r\n--"))

                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write((
                        f"<html><body>"
                        f"<h2>File '{filename}' successfully uploaded!</h2>"
                        f"<a href='{requested_path}'>Go back</a>"
                        f"</body></html>"
                    ).encode('utf-8'))
                    return

        self.send_response(400)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"Error uploading the file.")

    def is_authenticated(self, auth_header):
        # Basic Auth check
        encoded_credentials = auth_header.split(' ')[-1]
        decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
        username, password = decoded_credentials.split(":", 1)
        return username == USERNAME and password == PASSWORD

    def show_directory(self, local_path, requested_path):
        """
        Show directory contents including file size and creation time.
        """
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

        parent_path = os.path.dirname(requested_path.rstrip("/"))
        if parent_path == "":
            parent_link = ""
        else:
            parent_link = f"<a href='{parent_path}'>[Go Up]</a>"

        html_content = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>File Server - {requested_path}</title>
        </head>
        <body>
            <h2>Directory: {requested_path}</h2>
            {parent_link}
            <hr>
            <h3>Upload File</h3>
            <form enctype="multipart/form-data" method="post">
                <input type="file" name="file" required>
                <input type="submit" value="Upload">
            </form>
            <hr>
            <h3>Contents</h3>
            <ul>
        """

        try:
            for item in sorted(os.listdir(local_path)):
                item_path = os.path.join(local_path, item)
                next_url = requested_path.strip("/")
                if next_url:
                    next_url += "/" + item
                else:
                    next_url = item

                link_href = "/" + quote(next_url.replace("\\", "/"))

                if os.path.isdir(item_path):
                    # Directory
                    icon = "📁"
                    html_content += f"<li>{icon} <a href='{link_href}'>{item}</a></li>"
                else:
                    # File
                    icon = get_file_icon(item)
                    size_str = format_size(os.path.getsize(item_path))       # file size
                    ctime_str = get_creation_time(item_path)                 # creation time
                    html_content += (
                        f"<li>"
                        f"{icon} <a href='{link_href}' download>{item}</a>"
                        f" <small>({size_str}, {ctime_str})</small>"
                        f"</li>"
                    )

            html_content += "</ul></body></html>"
        except OSError:
            html_content = f"<html><head><meta charset=\"UTF-8\"></head><body><h2>Cannot list {requested_path}</h2></body></html>"

        self.wfile.write(html_content.encode('utf-8'))

###############################################################################
# START THE SERVER
###############################################################################

os.chdir(ROOT_DIRECTORY)

print(f"✅ Server started at http://localhost:{PORT} and {SERVER_URL}, serving {ROOT_DIRECTORY}")
print(f"🔐 Use credentials: {USERNAME} / {PASSWORD}")
print("📸 Scan the QR code below to access from your smartphone:")
generate_qr_code(SERVER_URL)

with socketserver.TCPServer(("", PORT), AuthHandler) as httpd:
    httpd.serve_forever()
