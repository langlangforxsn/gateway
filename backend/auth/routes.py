"""
认证路由
- POST /api/auth/email/send    发送邮箱验证码
- POST /api/auth/email/verify  验证码登录
- GET  /api/auth/status         登录状态
- POST /api/auth/logout         退出登录
- GET  /api/auth/gitee          Gitee OAuth（占位）
- GET  /api/auth/gitee/callback Gitee 回调（占位）
"""
import re
from flask import jsonify, request, session
from flask_login import login_user, current_user
from auth import bp

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


@bp.route("/email/send", methods=["POST"])
def email_send():
    """发送邮箱验证码。"""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    # 验证邮箱格式
    if not email:
        return jsonify({"error": "请输入邮箱地址"}), 400
    if not EMAIL_REGEX.match(email):
        return jsonify({"error": "邮箱格式不正确"}), 400

    from auth.email_login import create_and_send_code
    success, message = create_and_send_code(email)

    if success:
        return jsonify({"message": message})
    else:
        return jsonify({"error": message}), 429


@bp.route("/email/verify", methods=["POST"])
def email_verify():
    """邮箱验证码登录。"""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()

    # 参数校验
    if not email:
        return jsonify({"error": "请输入邮箱地址"}), 400
    if not EMAIL_REGEX.match(email):
        return jsonify({"error": "邮箱格式不正确"}), 400
    if not code or len(code) != 6 or not code.isdigit():
        return jsonify({"error": "请输入 6 位数字验证码"}), 400

    from auth.email_login import verify_code
    success, message, user = verify_code(email, code)

    if not success:
        return jsonify({"error": message}), 400

    # 登录用户（设置 session）
    login_user(user, remember=True)

    return jsonify({
        "message": message,
        "user": {
            "id": user.id,
            "user_no": user.user_no,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "email": user.email,
            "is_admin": user.is_admin,
            "auth_type": user.auth_type,
        },
    })


@bp.route("/status", methods=["GET"])
def status():
    """检查当前登录状态。"""
    if current_user.is_authenticated:
        return jsonify({
            "logged_in": True,
            "user": {
                "id": current_user.id,
                "user_no": current_user.user_no,
                "nickname": current_user.nickname,
                "avatar_url": current_user.avatar_url,
                "email": current_user.email,
                "is_admin": current_user.is_admin,
                "auth_type": current_user.auth_type,
            }
        })
    return jsonify({"logged_in": False})


@bp.route("/gitee", methods=["GET"])
def gitee_login():
    """Gitee OAuth 登录 — Phase 8 实现。"""
    return jsonify({"error": "Gitee 登录即将上线，敬请期待"}), 501


@bp.route("/gitee/callback", methods=["GET"])
def gitee_callback():
    """Gitee OAuth 回调 — Phase 8 实现。"""
    return jsonify({"error": "功能开发中"}), 501


@bp.route("/logout", methods=["POST"])
def logout():
    """退出登录。"""
    from flask_login import logout_user
    logout_user()
    return jsonify({"message": "已退出登录"})
