"""user 蓝图"""
from flask import Blueprint

bp = Blueprint("user", __name__, url_prefix="/api/user")

from user import routes  # noqa: F401, E402
