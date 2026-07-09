"""
认证 & 使用限制装饰器
- @login_required      : 要求登录
- @admin_required       : 要求管理员
- @usage_limit(tool)    : 检查未登录用户使用限制
"""
from functools import wraps
from flask import jsonify, request, g
from flask_login import current_user


def _get_client_ip():
    """获取客户端真实 IP（兼容反向代理）。"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2 → 取第一个
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def login_required(f):
    """要求用户已登录，否则返回 401。"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "请先登录", "code": "LOGIN_REQUIRED"}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """要求当前用户是管理员，否则返回 403。"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "请先登录", "code": "LOGIN_REQUIRED"}), 401
        if not current_user.is_admin:
            return jsonify({"error": "需要管理员权限", "code": "ADMIN_REQUIRED"}), 403
        return f(*args, **kwargs)
    return decorated


def usage_limit(tool_name):
    """
    未登录用户使用限制装饰器。
    读取 limit_configs 中该工具的配置，检查：
    1. 功能是否启用
    2. 是否必须登录
    3. 未登录时今日使用次数是否超限
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from user.models import LimitConfig

            config = LimitConfig.query.filter_by(tool_name=tool_name).first()

            # 如果没有配置，使用默认值放行
            if not config:
                return f(*args, **kwargs)

            # 功能未启用
            if not config.enabled:
                return jsonify({"error": "该功能暂时不可用", "code": "DISABLED"}), 503

            # 已登录用户：检查 login_daily 限制（0 = 无限制）
            if current_user.is_authenticated:
                if config.login_daily > 0:
                    from utils.usage_tracker import get_today_count
                    count = get_today_count(tool_name, user_id=current_user.id)
                    if count >= config.login_daily:
                        return jsonify({
                            "error": f"今日使用次数已达上限（{config.login_daily} 次）",
                            "code": "DAILY_LIMIT",
                            "remaining": 0,
                        }), 429
                g.remaining = -1  # -1 表示无限制
                return f(*args, **kwargs)

            # 未登录用户：必须登录的功能
            if config.require_login:
                return jsonify({
                    "error": "此功能需要登录后使用",
                    "code": "LOGIN_REQUIRED",
                    "tool_label": config.tool_label,
                }), 403

            # 未登录用户：检查每日限制
            if config.guest_daily <= 0:
                return jsonify({
                    "error": "此功能需要登录后使用",
                    "code": "LOGIN_REQUIRED",
                }), 403

            from utils.usage_tracker import get_today_count
            ip = _get_client_ip()
            count = get_today_count(tool_name, ip=ip)
            if count >= config.guest_daily:
                return jsonify({
                    "error": f"今日免费次数已用完（{config.guest_daily}/{config.guest_daily}），登录解锁无限使用 ✨",
                    "code": "DAILY_LIMIT",
                    "remaining": 0,
                    "limit": config.guest_daily,
                }), 429

            # 还有剩余次数
            g.remaining = config.guest_daily - count - 1  # 本次使用后的剩余
            return f(*args, **kwargs)
        return decorated
    return decorator
