import http.server
import socketserver
import base64
import os
import socket
from urllib.parse import unquote

# Configuration
PORT = 8080  # Change the port if needed
USERNAME = "admin"  # Set your username
PASSWORD = "password123"  # Set a secure password
DIRECTORY = r"C:\path\to\your\files"  # Path to the directory to be served

def get_local_ip():
    """Automatically finds the local IP of the PC"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception:
        return "localhost"

LOCAL_IP = get_local_ip()

class AuthHandler(http.server.SimpleHTTPRequestHandler):
    def do_HEAD(self):
        """Responds with an authentication request if not authenticated"""
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="File Server"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_AUTHHEAD(self):
        """Requests authentication if credentials are incorrect or missing"""
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="File Server"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Authentication required!')

    def do_GET(self):
        """Handles GET requests with authentication"""
        auth_header = self.headers.get('Authorization')

        if auth_header is None or not self.is_authenticated(auth_header):
            self.do_AUTHHEAD()
            return

        if self.path == "/":
            self.show_upload_page()
        else:
            super().do_GET()

    def do_POST(self):
        """Handles file upload with authentication"""
        auth_header = self.headers.get('Authorization')

        if auth_header is None or not self.is_authenticated(auth_header):
            self.do_AUTHHEAD()
            return

        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' in content_type:
            boundary = content_type.split("boundary=")[-1].encode()
            raw_data = self.rfile.read(int(self.headers['Content-Length']))
            
            # Find the start of the file data
            parts = raw_data.split(boundary)
            for part in parts:
                if b'filename="' in part:
                    header, file_data = part.split(b"\r\n\r\n", 1)
                    filename = header.split(b'filename="')[1].split(b'"')[0].decode()
                    filename = unquote(filename)

                    file_path = os.path.join(DIRECTORY, os.path.basename(filename))

                    with open(file_path, "wb") as f:
                        f.write(file_data.strip(b"\r\n--"))

                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f"<html><body><h2>File {filename} successfully uploaded!</h2><a href='/'>Go back</a></body></html>".encode())
                    return

        self.send_response(400)
        self.end_headers()
        self.wfile.write(b"Error uploading the file.")

    def is_authenticated(self, auth_header):
        """Checks if the user has entered the correct credentials"""
        encoded_credentials = auth_header.split(' ')[-1]  # Removes 'Basic '
        decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
        username, password = decoded_credentials.split(":", 1)

        return username == USERNAME and password == PASSWORD

    def show_upload_page(self):
        """Displays the HTML page for file uploads"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html_content = f"""
        <html>
        <head>
            <title>File Server</title>
        </head>
        <body>
            <h2>Upload File</h2>
            <form enctype="multipart/form-data" method="post">
                <input type="file" name="file" required>
                <input type="submit" value="Upload">
            </form>

            <h2>Available Files</h2>
            <ul>
        """

        files = os.listdir(DIRECTORY)
        for file in files:
            file_path = f"http://{LOCAL_IP}:{PORT}/{file}"
            html_content += f'<li><a href="{file_path}" download>{file}</a></li>'

        html_content += """
            </ul>
        </body>
        </html>
        """

        self.wfile.write(html_content.encode())

# Change the current directory to serve files without requiring admin privileges
os.chdir(DIRECTORY)

# Start the HTTP server on the specified port
with socketserver.TCPServer(("", PORT), AuthHandler) as httpd:
    print(f"✅ Server started at http://localhost:{PORT} and http://{LOCAL_IP}:{PORT}, serving {DIRECTORY}")
    print(f"🔐 Use credentials: {USERNAME} / {PASSWORD}")
    httpd.serve_forever()
