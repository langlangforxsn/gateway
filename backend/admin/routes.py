"""
管理员路由
- GET  /api/admin/users           用户列表（分页、搜索）
- GET  /api/admin/stats           数据概览
- GET  /api/admin/stats/trend     近 N 天趋势（ECharts）
- GET  /api/admin/limits          限制配置列表
- PUT  /api/admin/limits/<tool>   修改限制配置
- GET  /api/admin/usage           全局使用记录（分页、筛选）
"""
from datetime import datetime, timedelta, date
from flask import jsonify, request
from database import db
from admin import bp
from auth.decorators import admin_required


@bp.route("/users", methods=["GET"])
@admin_required
def users_list():
    """用户列表（分页、搜索、排序）。"""
    from auth.models import User

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    search = request.args.get("search", "").strip()
    sort = request.args.get("sort", "created_at")  # created_at | user_no | usage_count
    order = request.args.get("order", "desc")  # asc | desc

    query = User.query

    # 搜索
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                User.nickname.ilike(like),
                User.email.ilike(like),
                User.auth_id.ilike(like),
            )
        )

    # 排序
    sort_col = {
        "created_at": User.created_at,
        "user_no": User.user_no,
        "usage_count": User.usage_count,
        "last_login": User.last_login,
    }.get(sort, User.created_at)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    users = []
    for u in pagination.items:
        users.append({
            "id": u.id,
            "user_no": u.user_no,
            "nickname": u.nickname,
            "email": u.email,
            "auth_type": u.auth_type,
            "is_admin": u.is_admin,
            "usage_count": u.usage_count or 0,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else None,
            "last_login": u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else None,
        })

    return jsonify({
        "users": users,
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    })


@bp.route("/stats", methods=["GET"])
@admin_required
def stats():
    """数据概览。"""
    from auth.models import User
    from user.models import UsageLog

    today_start = datetime.combine(date.today(), datetime.min.time())

    total_users = User.query.count()
    today_new = User.query.filter(User.created_at >= today_start).count()
    today_login = User.query.filter(User.last_login >= today_start).count()
    today_usage = UsageLog.query.filter(UsageLog.created_at >= today_start).count()

    return jsonify({
        "total_users": total_users,
        "today_new": today_new,
        "today_login": today_login,
        "today_usage": today_usage,
    })


@bp.route("/stats/trend", methods=["GET"])
@admin_required
def stats_trend():
    """近 N 天注册趋势 + 使用量趋势。"""
    from auth.models import User
    from user.models import UsageLog

    days = request.args.get("days", 30, type=int)
    days = min(days, 90)
    today = date.today()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())

    # 注册趋势
    reg_rows = (
        db.session.query(db.func.date(User.created_at), db.func.count(User.id))
        .filter(User.created_at >= start_dt)
        .group_by(db.func.date(User.created_at))
        .order_by(db.func.date(User.created_at))
        .all()
    )
    reg_map = {str(r[0]): r[1] for r in reg_rows}

    # 使用趋势
    usage_rows = (
        db.session.query(db.func.date(UsageLog.created_at), db.func.count(UsageLog.id))
        .filter(UsageLog.created_at >= start_dt)
        .group_by(db.func.date(UsageLog.created_at))
        .order_by(db.func.date(UsageLog.created_at))
        .all()
    )
    usage_map = {str(r[0]): r[1] for r in usage_rows}

    # 构建完整日期序列
    dates = []
    register_data = []
    usage_data = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        d_key = d.strftime("%Y-%m-%d")
        d_label = d.strftime("%m-%d")
        dates.append(d_label)
        register_data.append(reg_map.get(d_key, 0))
        usage_data.append(usage_map.get(d_key, 0))

    return jsonify({
        "dates": dates,
        "register_data": register_data,
        "usage_data": usage_data,
    })


@bp.route("/limits", methods=["GET"])
@admin_required
def limits_list():
    """所有工具的限制配置列表。"""
    from user.models import LimitConfig

    configs = LimitConfig.query.order_by(LimitConfig.id).all()
    return jsonify({"limits": [c.to_dict() for c in configs]})


@bp.route("/limits/<tool_name>", methods=["PUT"])
@admin_required
def limits_update(tool_name):
    """修改某个工具的限制配置。"""
    from user.models import LimitConfig

    config = LimitConfig.query.filter_by(tool_name=tool_name).first()
    if not config:
        return jsonify({"error": f"工具 {tool_name} 不存在"}), 404

    data = request.get_json(silent=True) or {}

    # 只允许修改以下字段
    allowed_fields = {"guest_daily", "guest_file_mb", "login_daily", "login_file_mb", "enabled", "require_login"}
    for field in allowed_fields:
        if field in data:
            setattr(config, field, data[field])

    config.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"message": "配置已更新", "config": config.to_dict()})


@bp.route("/usage", methods=["GET"])
@admin_required
def usage_list():
    """全局使用记录（分页、筛选）。"""
    from user.models import UsageLog
    from auth.models import User

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    tool_name = request.args.get("tool_name", "").strip()
    user_id = request.args.get("user_id", type=int)
    date_from = request.args.get("date_from", "")

    query = UsageLog.query

    if tool_name:
        query = query.filter(UsageLog.tool_name == tool_name)
    if user_id:
        query = query.filter(UsageLog.user_id == user_id)
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(UsageLog.created_at >= dt)
        except ValueError:
            pass

    query = query.order_by(UsageLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 预加载用户名
    user_ids = {log.user_id for log in pagination.items if log.user_id}
    users_map = {}
    if user_ids:
        users = User.query.filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u.nickname for u in users}

    records = []
    for log in pagination.items:
        records.append({
            "id": log.id,
            "user_id": log.user_id,
            "user_nickname": users_map.get(log.user_id, "匿名"),
            "tool_name": log.tool_name,
            "action": log.action,
            "ip_address": log.ip_address,
            "created_at": log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else None,
        })

    return jsonify({
        "records": records,
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    })
