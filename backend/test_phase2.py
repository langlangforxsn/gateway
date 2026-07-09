"""
Phase 2 测试 — 邮箱验证码登录
覆盖：验证码生成、频率限制、用户创建、登录流程
"""
import sys
sys.path.insert(0, ".")

from unittest.mock import patch
from app import create_app
from database import db
from auth.models import User, EmailCode
from user.models import UsageLog, LimitConfig
from utils import usage_tracker
from datetime import datetime, timedelta
import json


def run_tests():
    app = create_app()
    client = app.test_client()

    with app.app_context():
        # 清理
        UsageLog.query.delete()
        EmailCode.query.delete()
        User.query.delete()
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
        print("=== 1. 验证码生成 ===")
        # ==========================================
        from auth.email_login import generate_code
        code1 = generate_code()
        code2 = generate_code()
        assert_eq("长度为 6", len(code1), 6)
        assert_eq("纯数字", code1.isdigit(), True)
        assert_eq("随机性", code1 == code2, False)  # 极小概率相等

        # ==========================================
        print("\n=== 2. 邮箱格式验证 ===")
        # ==========================================
        resp = client.post("/api/auth/email/send", json={"email": ""})
        assert_eq("空邮箱 → 400", resp.status_code, 400)

        resp = client.post("/api/auth/email/send", json={"email": "invalid"})
        assert_eq("无效邮箱 → 400", resp.status_code, 400)

        resp = client.post("/api/auth/email/send", json={"email": "a@b"})
        assert_eq("不完整邮箱 → 400", resp.status_code, 400)

        resp = client.post("/api/auth/email/send", json={})
        assert_eq("缺少 email → 400", resp.status_code, 400)

        # ==========================================
        print("\n=== 3. 发送验证码（mock SMTP）===")
        # ==========================================
        with patch("auth.email_login.send_verification_email", return_value=(True, "")) as mock_send:
            resp = client.post("/api/auth/email/send", json={"email": "test@example.com"})
            data = resp.get_json()
            assert_eq("发送成功 → 200", resp.status_code, 200)
            assert_eq("返回消息", data["message"], "验证码已发送，请查收邮件")
            assert_eq("SMTP 被调用", mock_send.called, True)
            sent_email = mock_send.call_args[0][0]
            assert_eq("发送到正确邮箱", sent_email, "test@example.com")

        # 验证码已存入数据库
        code_record = EmailCode.query.filter_by(email="test@example.com").order_by(EmailCode.created_at.desc()).first()
        assert_eq("验证码已存入 DB", code_record is not None, True)
        assert_eq("验证码长度", len(code_record.code), 6)
        assert_eq("未使用", code_record.used, False)

        # ==========================================
        print("\n=== 4. 频率限制 ===")
        # ==========================================
        with patch("auth.email_login.send_verification_email", return_value=(True, "")):
            # 1 分钟内第 2 次发送 → 应被限制
            resp = client.post("/api/auth/email/send", json={"email": "test@example.com"})
            assert_eq("1 分钟内重发 → 429", resp.status_code, 429)
            assert_eq("提示等待", "1 分钟" in resp.get_json()["error"], True)

            # 不同邮箱不受影响
            resp = client.post("/api/auth/email/send", json={"email": "other@example.com"})
            assert_eq("不同邮箱 → 200", resp.status_code, 200)

        # ==========================================
        print("\n=== 5. 验证码登录 ===")
        # ==========================================
        # 错误验证码
        resp = client.post("/api/auth/email/verify", json={"email": "test@example.com", "code": "000000"})
        assert_eq("错误验证码 → 400", resp.status_code, 400)

        # 正确验证码
        code_value = code_record.code
        resp = client.post("/api/auth/email/verify", json={"email": "test@example.com", "code": code_value})
        data = resp.get_json()
        assert_eq("正确验证码 → 200", resp.status_code, 200)
        assert_eq("登录成功消息", data["message"], "登录成功")
        assert_eq("返回用户信息", "user" in data, True)
        assert_eq("user_no=1", data["user"]["user_no"], 1)
        assert_eq("nickname 是邮箱前缀", data["user"]["nickname"], "test")
        assert_eq("auth_type=email", data["user"]["auth_type"], "email")
        assert_eq("is_admin=False", data["user"]["is_admin"], False)

        # 用户已创建
        user = User.query.filter_by(auth_id="test@example.com").first()
        assert_eq("用户已创建", user is not None, True)
        assert_eq("user_no=1", user.user_no, 1)

        # 验证码已标记为 used
        db.session.refresh(code_record)
        assert_eq("验证码已标记 used", code_record.used, True)

        # ==========================================
        print("\n=== 6. 登录状态 ===")
        # ==========================================
        resp = client.get("/api/auth/status")
        data = resp.get_json()
        assert_eq("已登录", data["logged_in"], True)
        assert_eq("用户邮箱", data["user"]["email"], "test@example.com")
        assert_eq("用户序号", data["user"]["user_no"], 1)

        # ==========================================
        print("\n=== 7. 退出登录 ===")
        # ==========================================
        resp = client.post("/api/auth/logout")
        assert_eq("退出成功", resp.status_code, 200)

        resp = client.get("/api/auth/status")
        assert_eq("退出后未登录", resp.get_json()["logged_in"], False)

        # ==========================================
        print("\n=== 8. 验证码过期 ===")
        # ==========================================
        # 创建一个过期的验证码
        expired = EmailCode(
            email="expired@test.com", code="999999",
            expires_at=datetime.utcnow() - timedelta(minutes=1), used=False,
        )
        db.session.add(expired)
        db.session.commit()

        resp = client.post("/api/auth/email/verify", json={"email": "expired@test.com", "code": "999999"})
        assert_eq("过期验证码 → 400", resp.status_code, 400)
        assert_eq("过期提示", "过期" in resp.get_json()["error"], True)

        # ==========================================
        print("\n=== 9. 重复使用验证码 ===")
        # ==========================================
        with patch("auth.email_login.send_verification_email", return_value=(True, "")):
            resp = client.post("/api/auth/email/send", json={"email": "reuse@test.com"})
            assert_eq("发送成功", resp.status_code, 200)

        reuse_code = EmailCode.query.filter_by(email="reuse@test.com").order_by(EmailCode.created_at.desc()).first()
        resp = client.post("/api/auth/email/verify", json={"email": "reuse@test.com", "code": reuse_code.code})
        assert_eq("首次使用成功", resp.status_code, 200)
        client.post("/api/auth/logout")

        # 再次使用同一验证码
        resp = client.post("/api/auth/email/verify", json={"email": "reuse@test.com", "code": reuse_code.code})
        assert_eq("重复使用 → 400", resp.status_code, 400)

        # ==========================================
        print("\n=== 10. 管理员邮箱自动提升 ===")
        # ==========================================
        app.config["ADMIN_EMAIL"] = "admin@test.com"
        with patch("auth.email_login.send_verification_email", return_value=(True, "")):
            resp = client.post("/api/auth/email/send", json={"email": "admin@test.com"})
            assert_eq("管理员发送成功", resp.status_code, 200)

        admin_code = EmailCode.query.filter_by(email="admin@test.com").order_by(EmailCode.created_at.desc()).first()
        resp = client.post("/api/auth/email/verify", json={"email": "admin@test.com", "code": admin_code.code})
        assert_eq("管理员登录成功", resp.status_code, 200)
        assert_eq("is_admin=True", resp.get_json()["user"]["is_admin"], True)
        admin_user_no = resp.get_json()["user"]["user_no"]

        # 验证管理员后台可访问
        resp = client.get("/api/admin/users")
        assert_eq("管理员访问后台", resp.status_code, 501)  # 501 因为还没实现

        client.post("/api/auth/logout")
        app.config["ADMIN_EMAIL"] = ""

        # ==========================================
        print("\n=== 11. 第二位用户 user_no ===")
        # ==========================================
        with patch("auth.email_login.send_verification_email", return_value=(True, "")):
            resp = client.post("/api/auth/email/send", json={"email": "user2@test.com"})

        user2_code = EmailCode.query.filter_by(email="user2@test.com").order_by(EmailCode.created_at.desc()).first()
        resp = client.post("/api/auth/email/verify", json={"email": "user2@test.com", "code": user2_code.code})
        assert_eq("第二位用户登录", resp.status_code, 200)
        user2_no = resp.get_json()["user"]["user_no"]
        assert_eq("user_no 递增", user2_no > admin_user_no, True)

        # ==========================================
        print("\n=== 12. 参数校验 ===")
        # ==========================================
        resp = client.post("/api/auth/email/verify", json={"email": "", "code": "123456"})
        assert_eq("空邮箱 → 400", resp.status_code, 400)

        resp = client.post("/api/auth/email/verify", json={"email": "a@b.com", "code": ""})
        assert_eq("空验证码 → 400", resp.status_code, 400)

        resp = client.post("/api/auth/email/verify", json={"email": "a@b.com", "code": "12345"})
        assert_eq("验证码不足 6 位 → 400", resp.status_code, 400)

        resp = client.post("/api/auth/email/verify", json={"email": "a@b.com", "code": "abcdef"})
        assert_eq("验证码非数字 → 400", resp.status_code, 400)

        # ==========================================
        print("\n=== 13. SMTP 失败处理 ===")
        # ==========================================
        with patch("auth.email_login.send_verification_email", return_value=(False, "邮件服务认证失败")):
            # 手动绕过频率限制
            EmailCode.query.filter_by(email="smtp_fail@test.com").delete()
            db.session.commit()
            resp = client.post("/api/auth/email/send", json={"email": "smtp_fail@test.com"})
            assert_eq("SMTP 失败 → 429", resp.status_code, 429)

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
