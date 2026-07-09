"""
用户路由
- GET /api/user/profile   个人信息
- GET /api/user/usage     使用记录（分页）
- GET /api/user/stats     使用统计（ECharts 数据）
"""
from datetime import datetime, timedelta, date
from flask import jsonify, request
from flask_login import current_user
from database import db
from user import bp
from auth.decorators import login_required


@bp.route("/profile", methods=["GET"])
@login_required
def profile():
    """个人信息。"""
    return jsonify({
        "id": current_user.id,
        "user_no": current_user.user_no,
        "nickname": current_user.nickname,
        "avatar_url": current_user.avatar_url,
        "email": current_user.email,
        "is_admin": current_user.is_admin,
        "auth_type": current_user.auth_type,
        "created_at": current_user.created_at.strftime("%Y-%m-%d %H:%M") if current_user.created_at else None,
        "last_login": current_user.last_login.strftime("%Y-%m-%d %H:%M") if current_user.last_login else None,
        "usage_count": current_user.usage_count or 0,
    })


@bp.route("/usage", methods=["GET"])
@login_required
def usage():
    """使用记录（分页）。"""
    from user.models import UsageLog

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    query = UsageLog.query.filter_by(user_id=current_user.id).order_by(UsageLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    records = []
    for log in pagination.items:
        records.append({
            "id": log.id,
            "tool_name": log.tool_name,
            "action": log.action,
            "created_at": log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else None,
        })

    return jsonify({
        "records": records,
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    })


@bp.route("/stats", methods=["GET"])
@login_required
def stats():
    """
    使用统计（ECharts 数据）。
    返回：
    - tool_stats: 各工具使用次数（饼图数据）
    - daily_stats: 近 N 天每日使用次数（柱状图数据）
    - total: 总使用次数
    """
    from user.models import UsageLog

    days = request.args.get("days", 7, type=int)
    days = min(days, 90)

    # ---- 各工具使用次数（饼图） ----
    tool_rows = (
        db.session.query(UsageLog.tool_name, db.func.count(UsageLog.id))
        .filter(UsageLog.user_id == current_user.id)
        .group_by(UsageLog.tool_name)
        .order_by(db.func.count(UsageLog.id).desc())
        .all()
    )

    # 工具名 → 显示名映射
    TOOL_LABELS = {
        "pdf_merge": "PDF 合并",
        "pdf_split": "PDF 分割",
        "pdf_compress": "PDF 压缩",
        "pdf_encrypt": "PDF 加密",
        "pdf_rotate": "PDF 旋转",
        "pdf_delete_pages": "PDF 删除页",
        "pdf_page_numbers": "PDF 加页码",
        "pdf_to_image": "PDF 转图片",
        "image_to_pdf": "图片转 PDF",
        "pdf_to_word": "PDF 转 Word",
        "office_to_pdf": "Office 转 PDF",
    }

    tool_stats = [
        {"name": TOOL_LABELS.get(name, name), "value": count}
        for name, count in tool_rows
    ]

    # ---- 近 N 天每日使用次数（柱状图） ----
    today = date.today()
    start_date = today - timedelta(days=days - 1)

    daily_rows = (
        db.session.query(
            db.func.date(UsageLog.created_at).label("day"),
            db.func.count(UsageLog.id),
        )
        .filter(
            UsageLog.user_id == current_user.id,
            UsageLog.created_at >= datetime.combine(start_date, datetime.min.time()),
        )
        .group_by("day")
        .order_by("day")
        .all()
    )

    # 构建完整日期序列（补零）
    daily_map = {str(row[0]): row[1] for row in daily_rows}
    daily_stats = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        d_str = d.strftime("%m-%d")
        d_key = d.strftime("%Y-%m-%d")
        daily_stats.append({"date": d_str, "count": daily_map.get(d_key, 0)})

    return jsonify({
        "tool_stats": tool_stats,
        "daily_stats": daily_stats,
        "total": current_user.usage_count or 0,
    })
