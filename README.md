# Simple Secure File Server with Authentication

A lightweight Python-based HTTP file server with basic authentication. It allows file sharing over a local network with a built-in web interface for uploading and downloading files. No admin privileges required.

## 🚀 Features
- 🔒 **Basic Authentication** (Username & Password)
- 📂 **File Upload & Download** via Web Interface
- 📡 **Access from any device on the same network**
- 🖥️ **Runs on Windows without admin privileges**
- 🌐 **Auto-detects local IP for easy access**
- 💡 **Minimal dependencies, works with Python built-in modules**

---

## 🛠️ Installation

### **1. Clone the repository**
```bash
git clone https://github.com/ddc-init/simple-file-server.git
cd simple-file-server
```

### **2. Run the server**
Make sure you have **Python 3.7+** installed. Then, run:
```bash
python server.py
```

### **3. Access the Web Interface**
Once the server starts, it will display something like:

```
✅ Server started at http://localhost:8080 and http://192.168.X.X:8080
🔐 Use credentials: admin / password123
```
Open a browser and go to `http://192.168.X.X:8080` (replace with your actual local IP).

---

## 📌 Usage

### **Uploading Files**
1. Open `http://192.168.X.X:8080` in your browser.
2. Select a file and click **Upload**.
3. The file will be saved in the server directory.

### **Downloading Files**
- The web page lists all available files.
- Click on any file to download it.

---

## 🔧 Configuration
You can modify the settings in `simple_python_server.py`:

```python
PORT = 8080  # Change the port if needed
USERNAME = "admin"  # Set your own username
PASSWORD = "password123"  # Set a secure password
DIRECTORY = r"C:\path\to\your\files"  # Change the directory for file storage
```

---

## ❌ Stopping the Server
Press `CTRL + C` in the terminal to stop the server.

---

## 📝 Notes
- This project is designed for **local network use only** and is not secure for public deployment.
- If you want to use it on Linux/Mac, make sure to adjust the `DIRECTORY` path.
- The authentication uses **Basic Auth**, which is suitable for internal networks but not for production use.

---

## 📜 License
This project is licensed under the MIT License.

---

## 🤝 Contributing
Feel free to submit pull requests or report issues! 🎉

---

### 📩 **Author**
Developed by [github/ddc_init](https://github.com/ddc-init). Connect with me on [LinkedIn](https://www.linkedin.com/in/davide-di-cori/).

