"""
SQLAlchemy 全局初始化
在 app.py 中调用 init_db(app) 完成绑定。
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """绑定 Flask 应用并创建所有表 + 初始化默认数据。"""
    db.init_app(app)

    with app.app_context():
        # 导入所有模型，确保表被注册
        from auth.models import User, EmailCode
        from user.models import UsageLog, LimitConfig

        db.create_all()

        # 初始化 limit_configs 默认数据（仅在表为空时写入）
        if LimitConfig.query.count() == 0:
            from config import Config
            for cfg in Config.DEFAULT_LIMITS:
                db.session.add(LimitConfig(**cfg))
            db.session.commit()
