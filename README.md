# Simple Secure Python Server with Authentication

A lightweight Python-based HTTP file server with **basic authentication**, **directory navigation**, **file upload/download**, and **QR code** support for easy access from mobile devices. Ideal for securely sharing files on your local network, **without requiring admin privileges**.

## 📁 Project Structure
```
SIMPLE_PYTHON_SERVER/
│
├─ .gitignore
├─ credentials.yaml      # Stores server credentials and directory path
├─ README.md            # This README file
├─ requirements.txt     # Python dependencies
├─ server.py            # Main server code (entry point)
└─ utils.py             # Utility functions (QR, icon mapping, device detection, file size/date)
```

## 🚀 Features
- 🔒 **Basic Authentication** (Username & Password)
- 📂 **File Upload & Download** via Web Interface
- 📡 **Access from any device on the same network**
- 🖥️ **Runs on Windows without admin privileges**
- 🌐 **Auto-detects local IP for easy access**
- 💡 **Minimal dependencies** (Python built-in + PyYAML, qrcode)
- 🗂️ **Displays File Size & Creation Date** in the directory listing

## 🛠️ Installation

### **1. Clone the repository**
```bash
git clone https://github.com/ddc-init/simple-file-server.git
cd simple-file-server
```

### **2. Install the dependencies**
Make sure you have **Python 3.7+** installed, then:
```bash
pip install -r requirements.txt
```

### **3. Configure credentials.yaml**
```yaml
server:
  port: 8080
  directory: "C:\path\to\your\files"

auth:
  username: "admin"
  password: "password123"
```
- `port`: The server port (default: `8080`).
- `directory`: The folder to share over HTTP (adjust if using Linux/Mac).
- `username`/`password`: Basic Auth credentials.

## 🚀 Usage

1. **Run the server**:
   ```bash
   python server.py
   ```
2. **Check the terminal**:
   - You will see a message like:
     ```
     ✅ Server started at http://localhost:8080 and http://192.168.X.X:8080, serving C:\path\to\your\files
     🔐 Use credentials: admin / password123
     📸 Scan the QR code below to access from your smartphone:
     [QR CODE ASCII]
     ```
   - Open your browser at `http://192.168.X.X:8080` (IP varies based on your local setup).
   - Enter the **username** and **password** you set in `credentials.yaml`.
3. **Navigate folders**: click on **directories** to explore subfolders.
4. **Upload files**: choose a file from the upload form.
5. **Download files**: click on a file name to download.
6. **View file details**: each file shows its size and creation/modification date in the listing.

## ❌ Stopping the Server
Press `CTRL + C` in the terminal to stop the server.

## 🔐 Security Notice
- This project is designed for **local network use only**.
- Basic Auth credentials are **not** encrypted (no HTTPS by default).
- Avoid exposing this server directly to the internet without extra security.

## 📝 Notes
- If you want to use it on Linux/Mac, just adjust the `directory` path in `credentials.yaml`.
- The authentication uses **Basic Auth**, which is okay for internal networks but not production.

## 🤝 Contributing
Feel free to open issues or submit pull requests to improve features, fix bugs, or suggest enhancements!

## 📜 License
This project is licensed under the MIT License.

### 📩 **Author**
Developed by [github/ddc_init](https://github.com/ddc-init). Connect with me on [LinkedIn](https://www.linkedin.com/in/davide-di-cori/).
