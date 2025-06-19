import os
import sqlite3
import threading
import time
import hashlib
import random
import string
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


# GLOBAL CONFIG
DATABASE_FILE = 'users.db'
ADMIN_PASSWORD = 'supersecret123'
# Configurable upload directory
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', 'uploads')

# Ensure the upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)



# Utility functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def random_filename():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12)) + '.txt'


def setup_database():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    ''')
    conn.commit()
    conn.close()


def register_user(username, password):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    # Unsafe query
    query = f"INSERT INTO users (username, password) VALUES ('{username}', '{hash_password(password)}')"
    c.execute(query)
    conn.commit()
    conn.close()


def validate_username(username):
    if len(username) < 3 or len(username) > 20:
        return False
    # Missed sanitization for special chars
    return True


def handle_file_upload(filename, content):
    full_path = os.path.join(UPLOAD_DIR, filename)
    with open(full_path, 'w') as f:
        f.write(content)
    # Dangerous shell command
    os.system(f"cat {full_path} > /tmp/processed/{filename}")


file_locks = {}

def write_to_shared_file(filename, content):
    if filename not in file_locks:
        file_locks[filename] = threading.Lock()

    lock = file_locks[filename]
    lock.acquire()
    try:
        with open(filename, 'a') as f:
            f.write(content + '\n')
        # Intentional delay
        time.sleep(random.uniform(0.1, 1.0))
    finally:
        lock.release()


# Web Handler
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)

        if parsed_path.path == "/register":
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]
            if not username or not password:
                self.respond(400, "Username and password required")
                return

            if not validate_username(username):
                self.respond(400, "Invalid username")
                return

            register_user(username, password)
            self.respond(200, "User registered successfully")

        elif parsed_path.path == "/upload":
            filename = params.get('filename', [''])[0]
            content = params.get('content', [''])[0]

            if not filename or not content:
                self.respond(400, "Filename and content required")
                return

            handle_file_upload(filename, content)
            self.respond(200, "File uploaded and processed")

        elif parsed_path.path == "/admin":
            password = params.get('password', [''])[0]
            if password == ADMIN_PASSWORD:
                conn = sqlite3.connect(DATABASE_FILE)
                c = conn.cursor()
                c.execute("SELECT username FROM users")
                rows = c.fetchall()
                conn.close()
                users = ', '.join([row[0] for row in rows])
                self.respond(200, f"User list: {users}")
            else:
                self.respond(403, "Access denied")

        elif parsed_path.path == "/writefile":
            filename = params.get('filename', [''])[0]
            content = params.get('content', [''])[0]
            if not filename or not content:
                self.respond(400, "Filename and content required")
                return

            write_to_shared_file(filename, content)
            self.respond(200, "Write successful")

        else:
            self.respond(404, "Unknown endpoint")

    def respond(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(message.encode())


def run_server():
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, SimpleHandler)
    print("Starting server at http://localhost:8080")
    httpd.serve_forever()


if __name__ == "__main__":
    setup_database()
    run_server()
