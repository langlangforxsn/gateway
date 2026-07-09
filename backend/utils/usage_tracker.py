"""
使用记录追踪工具函数
- log_usage()        : 记录一次使用
- get_today_count()  : 查询今日使用次数
- check_limit()      : 检查是否超限
- get_remaining()    : 返回剩余次数
"""
from datetime import datetime, date
from database import db


def log_usage(tool_name, user_id=None, ip="unknown", action="use"):
    """记录一次工具使用。"""
    from user.models import UsageLog
    log = UsageLog(
        user_id=user_id,
        tool_name=tool_name,
        action=action,
        ip_address=ip,
    )
    db.session.add(log)

    # 更新用户累计使用次数
    if user_id:
        from auth.models import User
        user = db.session.get(User, user_id)
        if user:
            user.usage_count = (user.usage_count or 0) + 1

    db.session.commit()


def get_today_count(tool_name, user_id=None, ip=None):
    """查询今日某个工具的使用次数。"""
    from user.models import UsageLog
    today_start = datetime.combine(date.today(), datetime.min.time())

    query = UsageLog.query.filter(
        UsageLog.tool_name == tool_name,
        UsageLog.created_at >= today_start,
    )

    if user_id:
        query = query.filter(UsageLog.user_id == user_id)
    elif ip:
        query = query.filter(UsageLog.ip_address == ip, UsageLog.user_id.is_(None))
    else:
        return 0

    return query.count()


def check_limit(tool_name, user_id=None, ip=None):
    """
    检查是否超限。
    返回 (allowed: bool, remaining: int, message: str)
    """
    from user.models import LimitConfig

    config = LimitConfig.query.filter_by(tool_name=tool_name).first()
    if not config:
        return True, -1, ""  # 无配置，放行

    if not config.enabled:
        return False, 0, "该功能暂时不可用"  # 功能已禁用

    if user_id:
        # 登录用户
        if config.login_daily <= 0:
            return True, -1, ""  # 无限制
        count = get_today_count(tool_name, user_id=user_id)
        remaining = config.login_daily - count
        if remaining <= 0:
            return False, 0, f"今日使用次数已达上限（{config.login_daily} 次）"
        return True, remaining, ""
    else:
        # 未登录用户
        if config.require_login:
            return False, 0, "此功能需要登录后使用"
        if config.guest_daily <= 0:
            return False, 0, "此功能需要登录后使用"
        count = get_today_count(tool_name, ip=ip)
        remaining = config.guest_daily - count
        if remaining <= 0:
            return False, 0, f"今日免费次数已用完（{config.guest_daily} 次），登录解锁无限使用 ✨"
        return True, remaining, ""


def get_remaining(tool_name, user_id=None, ip=None):
    """返回今日剩余使用次数。-1 表示无限制。"""
    allowed, remaining, _ = check_limit(tool_name, user_id, ip)
    return remaining
