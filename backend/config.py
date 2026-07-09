"""
Gateway 配置管理
所有配置项优先读取环境变量，未设置时使用默认值。
"""
import os
import secrets


class Config:
    # ---- Flask ----
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # ---- 数据库 ----
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///dingdangcat.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- 管理员 ----
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")

    # ---- 邮箱 SMTP ----
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.qq.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "叮当猫的口袋")

    # ---- 邮箱验证码 ----
    EMAIL_CODE_EXPIRE_MINUTES = int(os.environ.get("EMAIL_CODE_EXPIRE_MINUTES", "10"))
    EMAIL_CODE_LENGTH = 6
    # IP 频率限制
    EMAIL_RATE_LIMIT_PER_MINUTE = 1
    EMAIL_RATE_LIMIT_PER_HOUR = 5
    EMAIL_RATE_LIMIT_PER_DAY = 10

    # ---- 未登录用户限制 ----
    GUEST_DAILY_LIMIT = int(os.environ.get("GUEST_DAILY_LIMIT", "3"))
    GUEST_FILE_SIZE_MB = int(os.environ.get("GUEST_FILE_SIZE_MB", "20"))
    LOGIN_FILE_SIZE_MB = int(os.environ.get("LOGIN_FILE_SIZE_MB", "100"))

    # ---- 反向代理目标地址 ----
    PDF_TOOL_API = os.environ.get("PDF_TOOL_API", "http://localhost:5001")
    IMAGE_CONVERTER_API = os.environ.get("IMAGE_CONVERTER_API", "http://localhost:8000")

    # ---- Session ----
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("RENDER", "") != ""  # Render 部署时自动启用 HTTPS
    PERMANENT_SESSION_LIFETIME = 86400 * 7  # 7 天

    # ---- 各工具默认限制配置（首次启动时写入 limit_configs 表） ----
    DEFAULT_LIMITS = [
        {"tool_name": "pdf_merge",        "tool_label": "PDF 合并",     "guest_daily": 3, "guest_file_mb": 20, "login_daily": 0, "login_file_mb": 100, "require_login": False},
        {"tool_name": "pdf_split",        "tool_label": "PDF 分割",     "guest_daily": 3, "guest_file_mb": 20, "login_daily": 0, "login_file_mb": 100, "require_login": False},
        {"tool_name": "pdf_compress",     "tool_label": "PDF 压缩",     "guest_daily": 3, "guest_file_mb": 20, "login_daily": 0, "login_file_mb": 100, "require_login": False},
        {"tool_name": "pdf_encrypt",      "tool_label": "PDF 加密",     "guest_daily": 3, "guest_file_mb": 20, "login_daily": 0, "login_file_mb": 100, "require_login": False},
        {"tool_name": "pdf_rotate",       "tool_label": "PDF 旋转",     "guest_daily": 3, "guest_file_mb": 20, "login_daily": 0, "login_file_mb": 100, "require_login": False},
        {"tool_name": "pdf_delete_pages", "tool_label": "PDF 删除页",   "guest_daily": 3, "guest_file_mb": 20, "login_daily": 0, "login_file_mb": 100, "require_login": False},
        {"tool_name": "pdf_page_numbers", "tool_label": "PDF 加页码",   "guest_daily": 3, "guest_file_mb": 20, "login_daily": 0, "login_file_mb": 100, "require_login": False},
        {"tool_name": "pdf_to_image",     "tool_label": "PDF 转图片",   "guest_daily": 3, "guest_file_mb": 20, "login_daily": 0, "login_file_mb": 100, "require_login": False},
        {"tool_name": "image_to_pdf",     "tool_label": "图片转 PDF",   "guest_daily": 3, "guest_file_mb": 20, "login_daily": 0, "login_file_mb": 100, "require_login": False},
        {"tool_name": "pdf_to_word",      "tool_label": "PDF 转 Word",  "guest_daily": 0, "guest_file_mb": 0,  "login_daily": 0, "login_file_mb": 100, "require_login": True},
        {"tool_name": "office_to_pdf",    "tool_label": "Office 转 PDF","guest_daily": 0, "guest_file_mb": 0,  "login_daily": 0, "login_file_mb": 100, "require_login": True},
    ]
