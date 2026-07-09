"""
管理员路由 — Phase 5 将完整实现
当前提供占位端点。
"""
from flask import jsonify
from admin import bp


@bp.route("/users", methods=["GET"])
def users_list():
    """用户列表 — Phase 5 实现。"""
    return jsonify({"error": "功能开发中"}), 501


@bp.route("/stats", methods=["GET"])
def stats():
    """总体统计 — Phase 5 实现。"""
    return jsonify({"error": "功能开发中"}), 501


@bp.route("/stats/trend", methods=["GET"])
def stats_trend():
    """趋势数据 — Phase 5 实现。"""
    return jsonify({"error": "功能开发中"}), 501


@bp.route("/limits", methods=["GET"])
def limits_list():
    """限制配置列表 — Phase 5 实现。"""
    return jsonify({"error": "功能开发中"}), 501


@bp.route("/limits/<tool_name>", methods=["PUT"])
def limits_update(tool_name):
    """修改限制配置 — Phase 5 实现。"""
    return jsonify({"error": "功能开发中"}), 501


@bp.route("/usage", methods=["GET"])
def usage_list():
    """全局使用记录 — Phase 5 实现。"""
    return jsonify({"error": "功能开发中"}), 501
