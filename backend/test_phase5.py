"""
Phase 5 测试 — 管理员后台 API
"""
import sys
sys.path.insert(0, ".")

from unittest.mock import patch
from datetime import datetime, timedelta
from app import create_app
from database import db
from auth.models import User, EmailCode
from user.models import UsageLog, LimitConfig
from utils.usage_tracker import log_usage


def login_as_admin(client, email="admin@test.com"):
    """辅助：以管理员身份登录。"""
    app_config = client.application.config
    app_config["ADMIN_EMAIL"] = email
    with patch("auth.email_login.send_verification_email", return_value=(True, "")):
        client.post("/api/auth/email/send", json={"email": email})
    code = EmailCode.query.filter_by(email=email).order_by(EmailCode.created_at.desc()).first()
    client.post("/api/auth/email/verify", json={"email": email, "code": code.code})


def run_tests():
    app = create_app()
    client = app.test_client()

    with app.app_context():
        UsageLog.query.delete()
        EmailCode.query.delete()
        User.query.delete()
        # 重置 limit_configs
        LimitConfig.query.delete()
        from config import Config
        for cfg in Config.DEFAULT_LIMITS:
            db.session.add(LimitConfig(**cfg))
        db.session.commit()

        # 创建普通用户
        u1 = User(user_no=301, auth_type="email", auth_id="u1@test.com", nickname="User1")
        u2 = User(user_no=302, auth_type="email", auth_id="u2@test.com", nickname="User2")
        db.session.add_all([u1, u2])
        db.session.commit()

        # 记录使用
        log_usage("pdf_merge", user_id=u1.id, ip="1.1.1.1")
        log_usage("pdf_merge", user_id=u1.id, ip="1.1.1.1")
        log_usage("pdf_compress", user_id=u2.id, ip="2.2.2.2")
        log_usage("pdf_split", ip="3.3.3.3")  # 未登录

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
        print("=== 1. 未登录访问管理员 API ===")
        # ==========================================
        for path in ["/api/admin/users", "/api/admin/stats", "/api/admin/stats/trend",
                      "/api/admin/limits", "/api/admin/usage"]:
            resp = client.get(path)
            assert_eq(f"GET {path} 未登录 → 401", resp.status_code, 401)

        # ==========================================
        print("\n=== 2. 普通用户访问管理员 API ===")
        # ==========================================
        with patch("auth.email_login.send_verification_email", return_value=(True, "")):
            client.post("/api/auth/email/send", json={"email": "u1@test.com"})
        code = EmailCode.query.filter_by(email="u1@test.com").order_by(EmailCode.created_at.desc()).first()
        client.post("/api/auth/email/verify", json={"email": "u1@test.com", "code": code.code})

        resp = client.get("/api/admin/users")
        assert_eq("普通用户 → 403", resp.status_code, 403)
        client.post("/api/auth/logout")

        # ==========================================
        print("\n=== 3. 管理员登录 ===")
        # ==========================================
        login_as_admin(client)
        assert_eq("管理员已登录", AuthState_check(client), True)

        # ==========================================
        print("\n=== 4. 数据概览 ===")
        # ==========================================
        resp = client.get("/api/admin/stats")
        assert_eq("stats → 200", resp.status_code, 200)
        data = resp.get_json()
        assert_eq("total_users", data["total_users"], 3)  # u1, u2, admin
        assert_eq("today_usage", data["today_usage"], 4)

        # ==========================================
        print("\n=== 5. 用户列表 ===")
        # ==========================================
        resp = client.get("/api/admin/users")
        assert_eq("users → 200", resp.status_code, 200)
        data = resp.get_json()
        assert_eq("total=3", data["total"], 3)
        assert_eq("page=1", data["page"], 1)

        # 搜索
        resp = client.get("/api/admin/users?search=User1")
        data = resp.get_json()
        assert_eq("搜索 User1 结果数", data["total"], 1)
        assert_eq("搜索结果昵称", data["users"][0]["nickname"], "User1")

        # 分页
        resp = client.get("/api/admin/users?page=1&per_page=2")
        data = resp.get_json()
        assert_eq("分页 per_page=2", len(data["users"]), 2)
        assert_eq("总页数", data["pages"], 2)

        # ==========================================
        print("\n=== 6. 趋势数据 ===")
        # ==========================================
        resp = client.get("/api/admin/stats/trend?days=7")
        assert_eq("trend → 200", resp.status_code, 200)
        data = resp.get_json()
        assert_eq("dates 长度=7", len(data["dates"]), 7)
        assert_eq("register_data 长度=7", len(data["register_data"]), 7)
        assert_eq("usage_data 长度=7", len(data["usage_data"]), 7)
        # 今日有数据
        assert_eq("今日注册>0", data["register_data"][-1] > 0, True)
        assert_eq("今日使用=4", data["usage_data"][-1], 4)

        # ==========================================
        print("\n=== 7. 限制配置列表 ===")
        # ==========================================
        resp = client.get("/api/admin/limits")
        assert_eq("limits → 200", resp.status_code, 200)
        data = resp.get_json()
        assert_eq("配置数量=11", len(data["limits"]), 11)

        merge_cfg = [c for c in data["limits"] if c["tool_name"] == "pdf_merge"][0]
        assert_eq("pdf_merge.guest_daily=3", merge_cfg["guest_daily"], 3)

        # ==========================================
        print("\n=== 8. 修改限制配置 ===")
        # ==========================================
        resp = client.put("/api/admin/limits/pdf_merge", json={"guest_daily": 10, "guest_file_mb": 50})
        assert_eq("修改成功 → 200", resp.status_code, 200)
        data = resp.get_json()
        assert_eq("新 guest_daily=10", data["config"]["guest_daily"], 10)
        assert_eq("新 guest_file_mb=50", data["config"]["guest_file_mb"], 50)

        # 验证修改生效
        resp = client.get("/api/admin/limits")
        merge_cfg = [c for c in resp.get_json()["limits"] if c["tool_name"] == "pdf_merge"][0]
        assert_eq("持久化 guest_daily=10", merge_cfg["guest_daily"], 10)

        # 不存在的工具
        resp = client.put("/api/admin/limits/nonexistent", json={"guest_daily": 1})
        assert_eq("不存在 → 404", resp.status_code, 404)

        # ==========================================
        print("\n=== 9. 全局使用记录 ===")
        # ==========================================
        resp = client.get("/api/admin/usage")
        assert_eq("usage → 200", resp.status_code, 200)
        data = resp.get_json()
        assert_eq("total=4", data["total"], 4)
        assert_eq("records 数量", len(data["records"]), 4)

        # 筛选工具
        resp = client.get("/api/admin/usage?tool_name=pdf_merge")
        data = resp.get_json()
        assert_eq("筛选 pdf_merge=2", data["total"], 2)

        # 筛选用户
        resp = client.get(f"/api/admin/usage?user_id={u1.id}")
        data = resp.get_json()
        assert_eq(f"筛选 user_id={u1.id}=2", data["total"], 2)

        # ==========================================
        print("\n=== 10. 管理员页面 ===")
        # ==========================================
        resp = client.get("/admin.html")
        assert_eq("admin.html → 200", resp.status_code, 200)
        assert_eq("包含 ECharts", b"echarts" in resp.data, True)
        assert_eq("包含管理后台", "管理后台".encode() in resp.data, True)

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


def AuthState_check(client):
    """检查当前是否已登录且是管理员。"""
    resp = client.get("/api/auth/status")
    data = resp.get_json()
    return data.get("logged_in", False) and data.get("user", {}).get("is_admin", False)


if __name__ == "__main__":
    run_tests()
