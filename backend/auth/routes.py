"""
认证路由 — Phase 2 将完整实现
当前提供占位端点，确保蓝图注册不报错。
"""
from flask import jsonify
from auth import bp


@bp.route("/status", methods=["GET"])
def status():
    """检查当前登录状态。"""
    from flask_login import current_user
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


@bp.route("/email/send", methods=["POST"])
def email_send():
    """发送邮箱验证码 — Phase 2 实现。"""
    return jsonify({"error": "功能开发中"}), 501


@bp.route("/email/verify", methods=["POST"])
def email_verify():
    """邮箱验证码登录 — Phase 2 实现。"""
    return jsonify({"error": "功能开发中"}), 501


@bp.route("/gitee", methods=["GET"])
def gitee_login():
    """Gitee OAuth 登录 — Phase 8 实现。"""
    return jsonify({"error": "Gitee 登录即将上线，敬请期待 🚀"}), 501


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
