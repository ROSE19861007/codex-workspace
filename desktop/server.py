"""Local-only launcher for the space editor and its DWG import bridge."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONVERTER = ROOT / "desktop" / "converter" / "convert_dxf.py"
ODA = Path(r"C:\Program Files\ODA\ODAFileConverter 27.9.0\ODAFileConverter.exe")
# Keep generated files beside the project so the local bridge works without
# requiring broad access to the user's Documents directory.
OUTPUT_ROOT = ROOT / "导入图纸"
HOST, PORT = "127.0.0.1", 8765


def safe_name(name):
    return re.sub(r"[<>:\\|?*\x00-\x1f]", "_", name).strip(" .") or "drawing"


def multipart_file(content_type, body):
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;\s]+))", content_type)
    if not match:
        raise ValueError("未收到 DWG 文件。")
    boundary = (match.group(1) or match.group(2)).encode()
    for section in body.split(b"--" + boundary):
        if b"Content-Disposition:" not in section:
            continue
        header, separator, payload = section.partition(b"\r\n\r\n")
        filename = re.search(br'filename="([^\"]*)"', header)
        if separator and filename:
            value = payload[:-2] if payload.endswith(b"\r\n") else payload
            return Path(filename.group(1).decode("utf-8", "replace")).name, value
    raise ValueError("未收到 DWG 文件。")


def convert_dwg(filename, data):
    if Path(filename).suffix.lower() != ".dwg":
        raise ValueError("请选择 .dwg 文件。")
    if not ODA.is_file():
        raise RuntimeError(f"找不到 ODA File Converter：{ODA}")
    if not CONVERTER.is_file():
        raise RuntimeError("找不到 DXF 转换脚本。")
    stem = safe_name(Path(filename).stem)
    output_dir = OUTPUT_ROOT / f"{stem}-{time.strftime('%Y%m%d-%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="space-editor-dwg-") as temp:
        input_dir, dxf_dir = Path(temp) / "input", Path(temp) / "dxf"
        input_dir.mkdir()
        dxf_dir.mkdir()
        source = input_dir / f"{stem}.dwg"
        source.write_bytes(data)
        oda = subprocess.run([str(ODA), str(input_dir), str(dxf_dir), "ACAD2018", "DXF", "0", "1", source.name], capture_output=True, text=True, errors="replace", timeout=180)
        if oda.returncode != 0:
            raise RuntimeError(f"ODA 转换失败（{oda.returncode}）：{oda.stderr or oda.stdout}")
        dxf_files = list(dxf_dir.rglob("*.dxf"))
        if not dxf_files:
            raise RuntimeError("ODA 没有生成 DXF 文件。")
        dxf = dxf_files[0]
        shutil.copy2(dxf, output_dir / f"{stem}.dxf")
        result = subprocess.run([sys.executable, str(CONVERTER), str(dxf), str(output_dir)], capture_output=True, text=True, errors="replace", timeout=180)
        if result.returncode != 0:
            raise RuntimeError(f"DXF 解析失败：{result.stderr or result.stdout}")
    svg_path, json_path = output_dir / f"{stem}.svg", output_dir / f"{stem}.json"
    return {"outputDir": str(output_dir), "svgFileName": svg_path.name, "svg": svg_path.read_text(encoding="utf-8"), "structure": json.loads(json_path.read_text(encoding="utf-8")), "manifestPath": str(output_dir / f"{stem}.manifest.json")}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print("[space-editor] " + fmt % args)

    def send_json(self, code, value):
        encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        if self.path != "/api/dwg/import":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 200 * 1024 * 1024:
                raise ValueError("DWG 文件为空或超过 200 MB。")
            filename, data = multipart_file(self.headers.get("Content-Type", ""), self.rfile.read(size))
            self.send_json(200, convert_dwg(filename, data))
        except Exception as error:
            self.send_json(400, {"error": str(error)})


def main():
    print(f"空间编辑器已启动：http://{HOST}:{PORT}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Timer(0.4, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
