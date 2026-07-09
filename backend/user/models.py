"""用户相关数据模型：UsageLog、LimitConfig"""
from datetime import datetime
from database import db


class UsageLog(db.Model):
    """使用记录表"""
    __tablename__ = "usage_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, comment="已登录用户 ID，未登录为 NULL")
    tool_name = db.Column(db.String(64), nullable=False, comment="工具标识")
    action = db.Column(db.String(32), nullable=False, comment="操作类型")
    ip_address = db.Column(db.String(45), nullable=False, comment="客户端 IP")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联用户
    user = db.relationship("User", backref=db.backref("usage_logs", lazy="dynamic"))

    def __repr__(self):
        return f"<UsageLog tool={self.tool_name} user={self.user_id}>"


class LimitConfig(db.Model):
    """各工具的使用限制配置（管理员可在后台调整）"""
    __tablename__ = "limit_configs"

    id = db.Column(db.Integer, primary_key=True)
    tool_name = db.Column(db.String(64), unique=True, nullable=False, comment="工具标识")
    tool_label = db.Column(db.String(64), nullable=False, comment="显示名")
    guest_daily = db.Column(db.Integer, default=3, comment="未登录用户每日限制次数，0=禁止")
    guest_file_mb = db.Column(db.Integer, default=20, comment="未登录文件大小限制(MB)")
    login_daily = db.Column(db.Integer, default=0, comment="登录用户每日限制，0=无限制")
    login_file_mb = db.Column(db.Integer, default=100, comment="登录文件大小限制(MB)")
    enabled = db.Column(db.Boolean, default=True, comment="功能是否启用")
    require_login = db.Column(db.Boolean, default=False, comment="是否必须登录才能使用")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "tool_name": self.tool_name,
            "tool_label": self.tool_label,
            "guest_daily": self.guest_daily,
            "guest_file_mb": self.guest_file_mb,
            "login_daily": self.login_daily,
            "login_file_mb": self.login_file_mb,
            "enabled": self.enabled,
            "require_login": self.require_login,
        }

    def __repr__(self):
        return f"<LimitConfig {self.tool_name} guest={self.guest_daily}/day>"
