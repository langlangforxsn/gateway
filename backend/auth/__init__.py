"""auth 蓝图"""
from flask import Blueprint

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# 路由注册延迟到 app.py 中通过 register_blueprint 触发
from auth import routes  # noqa: F401, E402
