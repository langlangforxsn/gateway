"""
Phase 3 测试 — 反向代理 + 使用限制集成
"""
import sys, json, threading
sys.path.insert(0, ".")

from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import patch
from app import create_app
from database import db
from auth.models import User, EmailCode
from user.models import UsageLog, LimitConfig


# ---- Mock PDF 工具后端 ----
class MockPDFHandler(BaseHTTPRequestHandler):
    """模拟 PDF 工具后端。"""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "path": self.path}).encode())

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"result": "success", "path": self.path, "size": len(body)}).encode())

    def log_message(self, *args):
        pass  # 静默日志


MOCK_PORT = 18765
mock_server = None


def start_mock_server():
    global mock_server
    mock_server = HTTPServer(("127.0.0.1", MOCK_PORT), MockPDFHandler)
    thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{MOCK_PORT}"


def stop_mock_server():
    global mock_server
    if mock_server:
        mock_server.shutdown()
        mock_server = None


def run_tests():
    mock_url = start_mock_server()

    app = create_app()
    app.config["PDF_TOOL_API"] = mock_url
    client = app.test_client()

    with app.app_context():
        # 清理
        UsageLog.query.delete()
        EmailCode.query.delete()
        User.query.delete()
        db.session.commit()

        # 创建测试用户
        user = User(user_no=100, auth_type="email", auth_id="proxy@test.com", nickname="ProxyUser")
        db.session.add(user)
        # 重置 limit_configs 为默认值（防止前一个测试污染）
        LimitConfig.query.delete()
        from config import Config
        for cfg in Config.DEFAULT_LIMITS:
            db.session.add(LimitConfig(**cfg))
        db.session.commit()

        passed = 0
        failed = 0

        def assert_eq(name, actual, expected):
            nonlocal passed, failed
            if actual == expected:
                print(f"  PASS: {name}")
                passed += 1
            else:
                print(f"  FAIL: {name} — expected {expected!r}, got {actual!r}")
                failed += 1

        # ==========================================
        print("=== 1. 基本代理转发 ===")
        # ==========================================
        resp = client.get("/proxy/pdf/api/health")
        assert_eq("GET 代理 → 200", resp.status_code, 200)
        data = resp.get_json()
        assert_eq("路径正确", data["path"], "/api/health")

        # ==========================================
        print("\n=== 2. POST 代理转发（未登录）===")
        # ==========================================
        resp = client.post("/proxy/pdf/api/merge", data={"test": "data"})
        assert_eq("POST merge → 200 (3次内)", resp.status_code, 200)
        assert_eq("X-Remaining header", resp.headers.get("X-Remaining"), "2")

        # 第 2 次
        resp = client.post("/proxy/pdf/api/merge", data={"test": "data"})
        assert_eq("第2次 remaining", resp.headers.get("X-Remaining"), "1")

        # 第 3 次
        resp = client.post("/proxy/pdf/api/merge", data={"test": "data"})
        assert_eq("第3次 remaining", resp.headers.get("X-Remaining"), "0")

        # 第 4 次 → 超限
        resp = client.post("/proxy/pdf/api/merge", data={"test": "data"})
        assert_eq("第4次 → 429", resp.status_code, 429)
        data = resp.get_json()
        assert_eq("DAILY_LIMIT code", data["code"], "DAILY_LIMIT")
        assert_eq("remaining=0", data["remaining"], 0)

        # ==========================================
        print("\n=== 3. 不同工具独立计数 ===")
        # ==========================================
        resp = client.post("/proxy/pdf/api/compress", data={"test": "data"})
        assert_eq("compress 不受 merge 影响 → 200", resp.status_code, 200)
        assert_eq("compress remaining=2", resp.headers.get("X-Remaining"), "2")

        # ==========================================
        print("\n=== 4. 登录用户无限制 ===")
        # ==========================================
        # 登录
        with patch("auth.email_login.send_verification_email", return_value=(True, "")):
            client.post("/api/auth/email/send", json={"email": "proxy@test.com"})
        code = EmailCode.query.filter_by(email="proxy@test.com").order_by(EmailCode.created_at.desc()).first()
        client.post("/api/auth/email/verify", json={"email": "proxy@test.com", "code": code.code})

        # 已登录用户不受 merge 3次限制影响
        resp = client.post("/proxy/pdf/api/merge", data={"test": "data"})
        assert_eq("登录后 merge → 200", resp.status_code, 200)
        assert_eq("remaining=-1 (无限制)", resp.headers.get("X-Remaining"), "-1")

        client.post("/api/auth/logout")

        # ==========================================
        print("\n=== 5. require_login 功能 ===")
        # ==========================================
        resp = client.post("/proxy/pdf/api/convert/pdf-to-word", data={"test": "data"})
        assert_eq("pdf-to-word 未登录 → 403", resp.status_code, 403)
        data = resp.get_json()
        assert_eq("LOGIN_REQUIRED code", data["code"], "LOGIN_REQUIRED")
        assert_eq("tool_label", data["tool_label"], "PDF 转 Word")

        # ==========================================
        print("\n=== 6. 使用日志记录 ===")
        # ==========================================
        merge_logs = UsageLog.query.filter_by(tool_name="pdf_merge").all()
        assert_eq("merge 使用日志 > 0", len(merge_logs) > 0, True)

        compress_logs = UsageLog.query.filter_by(tool_name="pdf_compress").all()
        assert_eq("compress 使用日志", len(compress_logs), 1)

        # ==========================================
        print("\n=== 7. 非 API 路径不限制 ===")
        # ==========================================
        resp = client.get("/proxy/pdf/index.html")
        assert_eq("静态页面不限制 → 200", resp.status_code, 200)

        # ==========================================
        print("\n=== 8. 未映射的 API 路径 ===")
        # ==========================================
        resp = client.post("/proxy/pdf/api/info", data={"test": "data"})
        assert_eq("info 无限制 → 200", resp.status_code, 200)

        # ==========================================
        print("\n=== 9. 图片转换代理 ===")
        # ==========================================
        resp = client.get("/proxy/img/test")
        assert_eq("img 代理 (未配置) → 503", resp.status_code, 503)

        # ==========================================
        print("\n=== 10. PDF 后端未配置 ===")
        # ==========================================
        app.config["PDF_TOOL_API"] = ""
        resp = client.get("/proxy/pdf/test")
        assert_eq("未配置 → 503", resp.status_code, 503)
        app.config["PDF_TOOL_API"] = mock_url

        # ==========================================
        # 清理
        # ==========================================
        UsageLog.query.delete()
        EmailCode.query.delete()
        User.query.delete()
        db.session.commit()

        print(f"\n{'='*40}")
        print(f"结果: {passed} passed, {failed} failed")
        if failed == 0:
            print("ALL TESTS PASSED")
        else:
            print("SOME TESTS FAILED")
            sys.exit(1)

    stop_mock_server()


if __name__ == "__main__":
    run_tests()
