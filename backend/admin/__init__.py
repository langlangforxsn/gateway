"""admin 蓝图"""
from flask import Blueprint

bp = Blueprint("admin", __name__, url_prefix="/api/admin")

from admin import routes  # noqa: F401, E402
