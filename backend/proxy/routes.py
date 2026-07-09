"""
反向代理路由 — Phase 3 将完整实现
当前提供占位端点。
"""
from flask import jsonify
from proxy import bp


@bp.route("/pdf/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_pdf(subpath):
    """代理转发到 PDF 工具后端 — Phase 3 实现。"""
    return jsonify({"error": "代理功能开发中"}), 501


@bp.route("/img/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_img(subpath):
    """代理转发到图片转换后端 — Phase 3 实现。"""
    return jsonify({"error": "代理功能开发中"}), 501
