"""Launch the local, sign-in-free Word Runner site in the default browser."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import functools
import sys
import webbrowser


DIST = Path(__file__).resolve().parent / "dist"


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    for name in ("index.html", "app.js", "words.json"):
        if not (DIST / name).is_file():
            print(f"Thieu tep tro choi: {name}")
            return 1

    handler = functools.partial(NoCacheHandler, directory=str(DIST))
    server = None
    for port in range(8765, 8775):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), handler)
            break
        except OSError:
            continue
    if server is None:
        print("Khong the mo cong cuc bo. Hay dong cac ban Word Runner dang chay.")
        return 1

    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Word Runner dang chay tai {url}")
    print("Giu cua so nay mo khi choi. Nhan Ctrl+C hoac dong cua so de dung.")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
