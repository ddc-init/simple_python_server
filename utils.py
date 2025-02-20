import os
import socket
import fnmatch
import qrcode
from urllib.parse import unquote, quote
import datetime

def format_size(size_bytes: int) -> str:
    """
    Convert a file size in bytes to a human-readable string.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes // 1024} KB"
    elif size_bytes < 1024**3:
        return f"{round(size_bytes / (1024**2), 2)} MB"
    else:
        return f"{round(size_bytes / (1024**3), 2)} GB"

def get_creation_time(path: str) -> str:
    """
    Return creation time (Windows) or last-modified time (Linux/Mac)
    as a formatted string 'YYYY-MM-DD HH:MM:SS'.
    """
    # If you're on Windows, os.path.getctime is indeed the creation time;
    # on Linux/Mac, it is the last metadata change time, so you might prefer getmtime.
    timestamp = os.path.getctime(path)  # or os.path.getmtime(path)
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def find_directory(directory_name):
    """
    Search for the given directory name starting from C:\\.
    If found, returns the absolute path to that directory.
    Otherwise, returns None.
    """
    print(f"🔍 Searching for directory: {directory_name}...")
    for root, dirs, _ in os.walk("C:\\"):
        if fnmatch.filter(dirs, os.path.basename(directory_name)):
            found_path = os.path.join(root, os.path.basename(directory_name))
            print(f"✅ Found directory: {found_path}")
            return found_path
    print("❌ Directory not found.")
    return None

def get_local_ip():
    """
    Attempts to determine the local IP address by connecting
    to a well-known address (8.8.8.8) and checking the socket's
    own address.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception:
        return "localhost"

def generate_qr_code(url):
    """
    Generates a QR code for the given URL using the qrcode library.
    Prints the QR code as ASCII in the terminal.
    """
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)

def get_file_icon(filename):
    """
    Returns an emoji icon based on the file extension.
    Add or modify extensions as desired.
    """
    extension = os.path.splitext(filename)[1].lower().replace('.', '')

    # Images
    if extension in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'svg', 'webp']:
        return "🖼️"

    # PDFs, text-like docs
    elif extension in ['pdf']:
        return "📄"
    elif extension in ['txt', 'md', 'csv', 'log']:
        return "📝"

    # Archives / compressed
    elif extension in ['zip', 'rar', '7z', 'tar', 'gz', 'bz2']:
        return "📦"

    # Executables / scripts
    elif extension in ['exe', 'msi', 'bin', 'sh', 'deb', 'apk']:
        return "⚙️"

    # Office documents
    elif extension in ['doc', 'docx', 'odt']:
        return "📄"
    elif extension in ['xls', 'xlsx', 'ods']:
        return "📊"
    elif extension in ['ppt', 'pptx', 'odp']:
        return "📈"

    # Audio
    elif extension in ['mp3', 'wav', 'flac', 'aac', 'wma', 'ogg']:
        return "🎵"

    # Video
    elif extension in ['avi', 'mp4', 'mkv', 'mov', 'wmv', 'flv']:
        return "📽️"

    # Code files
    elif extension in ['py']:
        return "🐍"     # Python
    elif extension in ['js']:
        return "✨"     # JavaScript
    elif extension in ['ts']:
        return "✨"     # TypeScript
    elif extension in ['html', 'htm']:
        return "🌐"     # HTML
    elif extension in ['css']:
        return "🎨"     # CSS
    elif extension in ['cpp', 'hpp', 'h', 'cc', 'cxx']:
        return "💻"     # C/C++
    elif extension in ['java']:
        return "☕"     # Java
    elif extension in ['cs']:
        return "♯"      # C#
    elif extension in ['php']:
        return "🐘"     # PHP
    elif extension in ['go']:
        return "🐹"     # Go (Gopher)
    elif extension in ['rb']:
        return "💎"     # Ruby
    elif extension in ['swift']:
        return "🐦"     # Swift
    elif extension in ['scala']:
        return "🔺"     # Scala
    elif extension in ['dart']:
        return "🎯"     # Dart
    elif extension in ['rs']:
        return "🦀"     # Rust
    elif extension in ['lua']:
        return "🌙"     # Lua
    elif extension in ['json', 'yaml', 'yml', 'xml']:
        return "🗒️"     # Data/config

    # Disc images
    elif extension in ['iso', 'img']:
        return "💿"

    # Default icon for unknown extensions
    return "❓"

def identify_device(user_agent):
    """
    Basic detection of device type based on user-agent string.
    For demonstration: Android, iPhone, macOS, Windows, Linux, or unknown.
    """
    ua = user_agent.lower()
    if "android" in ua:
        return "📱 Android Device"
    elif "iphone" in ua:
        return "📱 iPhone"
    elif "mac" in ua:
        return "🖥️ macOS"
    elif "windows nt" in ua:
        return "💻 Windows PC"
    elif "linux" in ua:
        return "🐧 Linux Device"
    else:
        return f"🌐 Unknown Device ({user_agent})"
