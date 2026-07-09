"""认证相关数据模型：User、EmailCode"""
from datetime import datetime, timedelta
from flask_login import UserMixin
from database import db


class User(UserMixin, db.Model):
    """用户表"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    user_no = db.Column(db.Integer, unique=True, nullable=False, comment="用户序号")
    auth_type = db.Column(db.String(20), nullable=False, comment="email | gitee")
    auth_id = db.Column(db.String(128), unique=True, nullable=False, comment="邮箱地址 或 gitee_id")
    nickname = db.Column(db.String(128), nullable=False, comment="显示名称")
    avatar_url = db.Column(db.String(512), nullable=True, comment="头像 URL")
    email = db.Column(db.String(256), nullable=True, comment="邮箱地址")
    is_admin = db.Column(db.Boolean, default=False, comment="是否管理员")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment="注册时间")
    last_login = db.Column(db.DateTime, nullable=True, comment="最后登录时间")
    usage_count = db.Column(db.Integer, default=0, comment="累计使用次数")

    def __repr__(self):
        return f"<User #{self.user_no} {self.nickname}>"


class EmailCode(db.Model):
    """邮箱验证码表"""
    __tablename__ = "email_codes"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(256), nullable=False, index=True)
    code = db.Column(db.String(10), nullable=False, comment="6 位数字验证码")
    expires_at = db.Column(db.DateTime, nullable=False, comment="过期时间")
    used = db.Column(db.Boolean, default=False, comment="是否已使用")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    @classmethod
    def create(cls, email, code, expire_minutes=10):
        """创建一条新的验证码记录。"""
        return cls(
            email=email.lower().strip(),
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=expire_minutes),
        )

    def __repr__(self):
        return f"<EmailCode {self.email} code={self.code} used={self.used}>"
