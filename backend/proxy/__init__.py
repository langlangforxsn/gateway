"""proxy 蓝图"""
from flask import Blueprint

bp = Blueprint("proxy", __name__, url_prefix="/proxy")

from proxy import routes  # noqa: F401, E402
