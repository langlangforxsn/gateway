"""
叮当猫的口袋 — Gateway 主应用
统一入口：用户认证 + 门户页面 + 反向代理
"""
import os
import sys
import logging

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager

from config import Config
from database import db, init_db


def create_app():
    # 前端目录：Docker 中是 /app/frontend，本地是 ../frontend
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(base_dir, "..", "frontend")
    if not os.path.isdir(frontend_dir):
        # Docker 环境：frontend 在同级
        frontend_dir = os.path.join(base_dir, "frontend")

    logger.info(f"base_dir: {base_dir}")
    logger.info(f"frontend_dir: {frontend_dir}")
    logger.info(f"frontend exists: {os.path.isdir(frontend_dir)}")
    logger.info(f"sys.path: {sys.path[:3]}")

    app = Flask(
        __name__,
        static_folder=frontend_dir,
        static_url_path="",
    )
    app.config.from_object(Config)
    CORS(app, supports_credentials=True)

    # ---- 初始化数据库 ----
    init_db(app)

    # ---- Flask-Login ----
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        from auth.models import User
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import jsonify
        return jsonify({"error": "请先登录", "code": "LOGIN_REQUIRED"}), 401

    # ---- 注册蓝图 ----
    try:
        from auth import bp as auth_bp
        from user import bp as user_bp
        from admin import bp as admin_bp
        from proxy import bp as proxy_bp

        app.register_blueprint(auth_bp)
        app.register_blueprint(user_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(proxy_bp)
        logger.info("所有蓝图注册成功")
    except Exception as e:
        logger.error(f"蓝图注册失败: {e}")
        raise

    # ---- 前端页面路由 ----
    @app.route("/")
    def serve_portal():
        return send_from_directory(app.static_folder, "portal.html")

    @app.route("/personal.html")
    def serve_personal():
        return send_from_directory(app.static_folder, "personal.html")

    @app.route("/admin.html")
    def serve_admin():
        return send_from_directory(app.static_folder, "admin.html")

    # ---- 健康检查 ----
    @app.route("/health")
    def health():
        from flask import jsonify
        return jsonify({"status": "ok", "service": "gateway"})

    return app


# Gunicorn 入口: gunicorn app:app
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
