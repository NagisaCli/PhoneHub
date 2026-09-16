import os
import sys
import json
import mimetypes
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse
import tempfile
import cgi

# Ensure current dir in path
CURRENT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(CURRENT_DIR))

import adb_helper
import notif_sync

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class PhoneHubHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status_code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message, status_code=400):
        self._send_json({"success": False, "error": message}, status_code)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            html_file = CURRENT_DIR / "index.html"
            if not html_file.exists():
                self._send_error("index.html not found", 404)
                return
            content = html_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        elif path == "/api/status":
            st = adb_helper.get_device_status()
            self._send_json(st)
            return

        elif path == "/api/apps":
            cat = query.get("cat", ["3"])[0]
            apps = adb_helper.list_installed_apps(category=cat)
            self._send_json({"success": True, "apps": apps})
            return

        elif path == "/api/diagnostics":
            diag = adb_helper.get_deep_diagnostics()
            self._send_json({"success": True, "diagnostics": diag})
            return

        elif path == "/api/sms":
            sms_list = adb_helper.get_sms_messages(limit=30)
            self._send_json({"success": True, "sms": sms_list})
            return

        elif path == "/api/fs/list":
            remote_path = query.get("path", ["/sdcard"])[0]
            hidden = query.get("hidden", ["0"])[0] == "1"
            data = adb_helper.list_directory_full(remote_path=remote_path, show_hidden=hidden)
            self._send_json(data)
            return

        elif path == "/api/fs/preview":
            remote_path = query.get("path", [""])[0]
            data = adb_helper.get_image_preview_b64(remote_path)
            self._send_json(data)
            return

        self._send_error("Not Found", 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        ctype = self.headers.get("Content-Type", "")

        # Handle multipart upload
        if path == "/api/files/upload" or path == "/api/fs/upload":
            if "multipart/form-data" not in ctype:
                self._send_error("Expected multipart/form-data")
                return

            try:
                # Parse multipart
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST',
                             'CONTENT_TYPE': self.headers['Content-Type']}
                )
                if "file" not in form:
                    self._send_error("No file uploaded")
                    return

                target_dir = "/sdcard/Download"
                if "target_dir" in form:
                    target_dir = form.getfirst("target_dir") or "/sdcard/Download"

                file_item = form["file"]
                filename = file_item.filename or "uploaded_file"
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(file_item.file.read())
                    tmp_path = tmp.name

                res = adb_helper.push_file_to_directory(tmp_path, target_dir, filename)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                self._send_json(res)
            except Exception as e:
                self._send_error(str(e))
            return

        # Handle JSON POST
        length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(length)
        payload = {}
        if post_body:
            try:
                payload = json.loads(post_body.decode("utf-8"))
            except Exception:
                pass

        if path == "/api/action":
            action = payload.get("action", "")
            res = adb_helper.execute_action(action)
            self._send_json(res)
            return

        elif path == "/api/input":
            text = payload.get("text", "")
            res = adb_helper.send_text_input(text)
            self._send_json(res)
            return

        elif path == "/api/apps/action":
            pkg = payload.get("pkg", "")
            act = payload.get("action", "")
            res = adb_helper.app_action(pkg, act)
            self._send_json(res)
            return

        elif path == "/api/files/pull-latest":
            res = adb_helper.pull_latest_photo_to_desktop()
            self._send_json(res)
            return

        elif path == "/api/clean":
            clean_type = payload.get("type", "")
            res = adb_helper.clean_system(clean_type)
            self._send_json(res)
            return

        elif path == "/api/notif/test":
            notif_sync.pop_windows_toast("PhoneHub 手机通知同步测试", "当手机收到微信、短信或验证码时，将在此处自动弹出！")
            self._send_json({"success": True, "message": "已发送 Windows 测试通知"})
            return

        elif path == "/api/notif/toggle":
            if notif_sync.listener.running:
                notif_sync.listener.stop()
            else:
                notif_sync.listener.start()
            self._send_json({"success": True, "running": notif_sync.listener.running})
            return

        elif path == "/api/sms/send":
            num = payload.get("number", "")
            body = payload.get("body", "")
            res = adb_helper.send_sms(num, body)
            self._send_json(res)
            return

        elif path == "/api/quick-app":
            app_key = payload.get("app", "")
            res = adb_helper.launch_quick_app(app_key)
            self._send_json(res)
            return

        elif path == "/api/fs/pull":
            remote_path = payload.get("path", "")
            res = adb_helper.pull_file_or_dir(remote_path)
            self._send_json(res)
            return

        elif path == "/api/fs/delete":
            remote_path = payload.get("path", "")
            res = adb_helper.delete_remote_item(remote_path)
            self._send_json(res)
            return

        elif path == "/api/fs/mkdir":
            remote_dir = payload.get("dir", "/sdcard")
            name = payload.get("name", "")
            res = adb_helper.make_remote_directory(remote_dir, name)
            self._send_json(res)
            return

        elif path == "/api/fs/rename":
            remote_path = payload.get("path", "")
            new_name = payload.get("new_name", "")
            res = adb_helper.rename_remote_item(remote_path, new_name)
            self._send_json(res)
            return

        elif path == "/api/fs/batch-pull":
            paths = payload.get("paths", [])
            res = adb_helper.batch_pull_files(paths)
            self._send_json(res)
            return

        elif path == "/api/fs/batch-delete":
            paths = payload.get("paths", [])
            res = adb_helper.batch_delete_items(paths)
            self._send_json(res)
            return

        elif path == "/api/dial":
            number = payload.get("number", "")
            res = adb_helper.dial_phone_number(number)
            self._send_json(res)
            return

        self._send_error("Not Found", 404)

    def log_message(self, format, *args):
        # Quiet logger
        pass

def run_server(port=18080):
    # Auto-start notification listener
    try:
        notif_sync.listener.start()
    except Exception as e:
        print(f"Error starting notif listener: {e}")

    server = ThreadedHTTPServer(("127.0.0.1", port), PhoneHubHandler)
    print(f"PhoneHub Server running at http://127.0.0.1:{port}/")
    server.serve_forever()

if __name__ == "__main__":
    port = 18080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)
