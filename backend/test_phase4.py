"""
Phase 4 测试 — 个人中心 API
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


def run_tests():
    app = create_app()
    client = app.test_client()

    with app.app_context():
        # 清理
        UsageLog.query.delete()
        EmailCode.query.delete()
        User.query.delete()
        db.session.commit()

        # 创建测试用户并登录
        user = User(user_no=200, auth_type="email", auth_id="personal@test.com", nickname="PersonalUser", email="personal@test.com")
        db.session.add(user)
        db.session.commit()

        # 记录一些使用数据
        log_usage("pdf_merge", user_id=user.id, ip="127.0.0.1")
        log_usage("pdf_merge", user_id=user.id, ip="127.0.0.1")
        log_usage("pdf_merge", user_id=user.id, ip="127.0.0.1")
        log_usage("pdf_compress", user_id=user.id, ip="127.0.0.1")
        log_usage("pdf_compress", user_id=user.id, ip="127.0.0.1")
        log_usage("pdf_split", user_id=user.id, ip="127.0.0.1")
        log_usage("pdf_to_image", user_id=user.id, ip="127.0.0.1")

        # 登录
        with patch("auth.email_login.send_verification_email", return_value=(True, "")):
            client.post("/api/auth/email/send", json={"email": "personal@test.com"})
        code = EmailCode.query.filter_by(email="personal@test.com").order_by(EmailCode.created_at.desc()).first()
        client.post("/api/auth/email/verify", json={"email": "personal@test.com", "code": code.code})

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
        print("=== 1. 个人信息 API ===")
        # ==========================================
        resp = client.get("/api/user/profile")
        assert_eq("profile → 200", resp.status_code, 200)
        data = resp.get_json()
        assert_eq("nickname", data["nickname"], "PersonalUser")
        assert_eq("user_no", data["user_no"], 200)
        assert_eq("email", data["email"], "personal@test.com")
        assert_eq("auth_type", data["auth_type"], "email")
        assert_eq("usage_count", data["usage_count"], 7)
        assert_eq("created_at 不为空", data["created_at"] is not None, True)

        # ==========================================
        print("\n=== 2. 使用记录 API ===")
        # ==========================================
        resp = client.get("/api/user/usage")
        assert_eq("usage → 200", resp.status_code, 200)
        data = resp.get_json()
        assert_eq("total=7", data["total"], 7)
        assert_eq("page=1", data["page"], 1)
        assert_eq("per_page=20", data["per_page"], 20)
        assert_eq("records 数量", len(data["records"]), 7)
        assert_eq("最新记录在前", data["records"][0]["tool_name"], "pdf_to_image")

        # 分页
        resp = client.get("/api/user/usage?page=1&per_page=3")
        data = resp.get_json()
        assert_eq("分页 per_page=3", len(data["records"]), 3)
        assert_eq("总页数", data["pages"], 3)

        # ==========================================
        print("\n=== 3. 使用统计 API ===")
        # ==========================================
        resp = client.get("/api/user/stats")
        assert_eq("stats → 200", resp.status_code, 200)
        data = resp.get_json()
        assert_eq("total=7", data["total"], 7)
        assert_eq("tool_stats 数量", len(data["tool_stats"]), 4)
        assert_eq("daily_stats 数量", len(data["daily_stats"]), 7)  # 默认 7 天

        # 饼图数据验证
        tool_names = [t["name"] for t in data["tool_stats"]]
        assert_eq("饼图包含 PDF 合并", "PDF 合并" in tool_names, True)
        merge_stat = [t for t in data["tool_stats"] if t["name"] == "PDF 合并"][0]
        assert_eq("PDF 合并次数=3", merge_stat["value"], 3)

        # 柱状图数据验证
        today_str = datetime.utcnow().strftime("%m-%d")
        today_stat = [d for d in data["daily_stats"] if d["date"] == today_str]
        assert_eq("今日有数据", len(today_stat), 1)
        assert_eq("今日使用次数=7", today_stat[0]["count"], 7)

        # 自定义天数
        resp = client.get("/api/user/stats?days=3")
        data = resp.get_json()
        assert_eq("3天统计", len(data["daily_stats"]), 3)

        # ==========================================
        print("\n=== 4. 未登录访问 ===")
        # ==========================================
        client.post("/api/auth/logout")

        resp = client.get("/api/user/profile")
        assert_eq("未登录 profile → 401", resp.status_code, 401)

        resp = client.get("/api/user/usage")
        assert_eq("未登录 usage → 401", resp.status_code, 401)

        resp = client.get("/api/user/stats")
        assert_eq("未登录 stats → 401", resp.status_code, 401)

        # ==========================================
        print("\n=== 5. 个人中心页面 ===")
        # ==========================================
        resp = client.get("/personal.html")
        assert_eq("personal.html → 200", resp.status_code, 200)
        assert_eq("包含 ECharts", b"echarts" in resp.data, True)
        assert_eq("包含 auth.js", b"auth.js" in resp.data, True)

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


if __name__ == "__main__":
    run_tests()
