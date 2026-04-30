import os
import http.server
import socketserver
os.chdir(r"C:\codex\bilinote_latest_v2.0.0\BillNote_frontend\dist")
class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def do_GET(self):
        if not os.path.exists(self.translate_path(self.path)):
            self.path = "/index.html"
        return super().do_GET()
with socketserver.TCPServer(("0.0.0.0", 13015), Handler) as httpd:
    httpd.serve_forever()
