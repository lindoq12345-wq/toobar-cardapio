from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from toobar.service import AppError, ToobarService


ROOT = Path(__file__).parent
DB_PATH = Path(os.environ.get("TOOBAR_DB_PATH", ROOT / "data" / "toobar.sqlite3"))
SERVICE = ToobarService(DB_PATH)

LOCAL_MENU_ASSETS = {
    "petiscos": ("#d7332a", "#efb23e", "PETISCO"),
    "pratos": ("#2d8d69", "#f2c879", "PRATO"),
    "drinks": ("#27313d", "#d7332a", "DRINK"),
    "bebidas": ("#efb23e", "#27313d", "GELADA"),
}


class ToobarHandler(SimpleHTTPRequestHandler):
    server_version = "ToobarHTTP/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_post(parsed)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def handle_api_get(self, parsed) -> None:
        try:
            if parsed.path == "/api/health":
                self.send_json({"status": "ok", "service": "toobar"})
            elif parsed.path.startswith("/api/assets/menu/"):
                self.send_menu_asset(parsed.path)
            elif parsed.path == "/api/menu":
                category = parse_qs(parsed.query).get("category", [None])[0]
                self.send_json({"items": SERVICE.menu(category)})
            elif parsed.path == "/api/me":
                self.send_json({"user": SERVICE.current_user(self.session_token())})
            elif parsed.path == "/api/orders":
                self.send_json({"orders": SERVICE.orders_for_user(self.session_token())})
            else:
                raise AppError("Rota nao encontrada.", 404)
        except AppError as exc:
            self.send_error_json(exc.message, exc.status)

    def send_menu_asset(self, path: str) -> None:
        name = Path(path).stem
        primary, accent, label = LOCAL_MENU_ASSETS.get(name, LOCAL_MENU_ASSETS["petiscos"])
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="560" viewBox="0 0 480 560">
<rect width="480" height="560" fill="{primary}"/>
<circle cx="380" cy="118" r="112" fill="{accent}" opacity=".82"/>
<circle cx="98" cy="438" r="132" fill="#fff8ec" opacity=".2"/>
<rect x="86" y="178" width="308" height="214" rx="22" fill="#fff8ec" opacity=".95"/>
<rect x="128" y="222" width="224" height="28" rx="14" fill="{primary}" opacity=".26"/>
<rect x="128" y="270" width="224" height="28" rx="14" fill="{primary}" opacity=".26"/>
<rect x="128" y="318" width="150" height="28" rx="14" fill="{primary}" opacity=".26"/>
<text x="240" y="474" text-anchor="middle" font-family="Arial, sans-serif" font-size="48" font-weight="800" fill="#fff8ec">{label}</text>
</svg>""".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(svg)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(svg)

    def handle_api_post(self, parsed) -> None:
        try:
            payload = self.read_json()
            if parsed.path == "/api/auth/register":
                result = SERVICE.register(
                    payload.get("name", ""),
                    payload.get("email", ""),
                    payload.get("password", ""),
                )
                self.send_session(result["token"])
                self.send_json({"user": result["user"]}, status=201)
            elif parsed.path == "/api/auth/login":
                result = SERVICE.login(payload.get("email", ""), payload.get("password", ""))
                self.send_session(result["token"])
                self.send_json({"user": result["user"]})
            elif parsed.path == "/api/auth/logout":
                SERVICE.logout(self.session_token())
                self.clear_session()
                self.send_json({"ok": True})
            elif parsed.path == "/api/orders":
                self.send_json({"order": SERVICE.create_order(self.session_token(), payload)}, status=201)
            else:
                raise AppError("Rota nao encontrada.", 404)
        except AppError as exc:
            self.send_error_json(exc.message, exc.status)
        except json.JSONDecodeError:
            self.send_error_json("JSON invalido.", 400)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def session_token(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie"))
        morsel = cookie.get("toobar_session")
        return morsel.value if morsel else None

    def send_session(self, token: str) -> None:
        self.extra_cookie = f"toobar_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800"

    def clear_session(self) -> None:
        self.extra_cookie = "toobar_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"

    def send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if hasattr(self, "extra_cookie"):
            self.send_header("Set-Cookie", self.extra_cookie)
            del self.extra_cookie
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: int) -> None:
        self.send_json({"error": message}, status=status)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), ToobarHandler)
    print(f"Toobar rodando em http://{host}:{port}")
    print(f"Banco SQLite: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    run(port=int(os.environ.get("PORT", "8000")))
