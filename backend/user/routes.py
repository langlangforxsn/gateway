"""
用户路由 — Phase 4 将完整实现
当前提供占位端点。
"""
from flask import jsonify
from user import bp


@bp.route("/profile", methods=["GET"])
def profile():
    """个人信息 — Phase 4 实现。"""
    return jsonify({"error": "功能开发中"}), 501


@bp.route("/usage", methods=["GET"])
def usage():
    """使用记录 — Phase 4 实现。"""
    return jsonify({"error": "功能开发中"}), 501


@bp.route("/stats", methods=["GET"])
def stats():
    """使用统计 — Phase 4 实现。"""
    return jsonify({"error": "功能开发中"}), 501
