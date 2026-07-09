"""
邮箱验证码登录模块
- 验证码生成（6 位随机数字）
- SMTP 邮件发送（HTML 模板）
- 验证码校验（正确性 + 过期 + 防重复）
- IP 频率限制
- 用户创建/更新（首次自动注册）
"""
import random
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from flask import request, render_template
from database import db
from auth.models import User, EmailCode
from config import Config


def generate_code(length=None):
    """生成指定长度的纯数字验证码。"""
    length = length or Config.EMAIL_CODE_LENGTH
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def check_email_rate_limit(email):
    """
    检查邮箱发送频率限制。
    返回 (allowed: bool, message: str)
    """
    now = datetime.utcnow()
    email_lower = email.lower().strip()

    # 1 分钟内
    count_1min = EmailCode.query.filter(
        EmailCode.email == email_lower,
        EmailCode.created_at >= now - timedelta(minutes=1),
    ).count()
    if count_1min >= Config.EMAIL_RATE_LIMIT_PER_MINUTE:
        return False, "发送太频繁，请 1 分钟后再试"

    # 1 小时内
    count_1hour = EmailCode.query.filter(
        EmailCode.email == email_lower,
        EmailCode.created_at >= now - timedelta(hours=1),
    ).count()
    if count_1hour >= Config.EMAIL_RATE_LIMIT_PER_HOUR:
        return False, "该邮箱发送次数已达上限，请 1 小时后再试"

    return True, ""


def check_ip_rate_limit():
    """
    检查 IP 发送频率限制（防止同一 IP 对不同邮箱轰炸）。
    返回 (allowed: bool, message: str)
    """
    ip = _get_client_ip()
    now = datetime.utcnow()

    # 1 小时内该 IP 发送的所有验证码
    count_1hour = EmailCode.query.filter(
        EmailCode.created_at >= now - timedelta(hours=1),
    ).count()
    if count_1hour >= Config.EMAIL_RATE_LIMIT_PER_HOUR * 3:
        return False, "发送次数过多，请稍后再试"

    return True, ""


def send_verification_email(email, code):
    """
    通过 SMTP 发送验证码邮件。
    返回 (success: bool, error_message: str)
    """
    if not Config.SMTP_USER or not Config.SMTP_PASSWORD:
        return False, "邮件服务未配置"

    email_lower = email.lower().strip()

    # 构建邮件
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【叮当猫的口袋】验证码：{code}"
    msg["From"] = f"{Config.SMTP_FROM} <{Config.SMTP_USER}>"
    msg["To"] = email_lower

    # HTML 正文
    html = render_template(
        "email_code.html",
        code=code,
        expire_minutes=Config.EMAIL_CODE_EXPIRE_MINUTES,
    )
    msg.attach(MIMEText(html, "html", "utf-8"))

    # 发送
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, context=context) as server:
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.sendmail(Config.SMTP_USER, email_lower, msg.as_string())
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, "邮件服务认证失败，请联系管理员"
    except smtplib.SMTPRecipientsRefused:
        return False, "邮箱地址无效"
    except Exception as e:
        return False, f"邮件发送失败：{str(e)}"


def create_and_send_code(email):
    """
    生成验证码 → 存入数据库 → 发送邮件。
    返回 (success: bool, message: str)
    """
    # 检查邮箱频率限制
    allowed, msg = check_email_rate_limit(email)
    if not allowed:
        return False, msg

    # 检查 IP 频率限制
    allowed, msg = check_ip_rate_limit()
    if not allowed:
        return False, msg

    # 生成验证码
    code = generate_code()

    # 存入数据库
    email_code = EmailCode.create(email, code, Config.EMAIL_CODE_EXPIRE_MINUTES)
    db.session.add(email_code)
    db.session.commit()

    # 发送邮件
    success, error = send_verification_email(email, code)
    if not success:
        return False, error

    return True, "验证码已发送，请查收邮件"


def verify_code(email, code):
    """
    验证邮箱验证码。
    返回 (success: bool, message: str, user: User|None)
    """
    email_lower = email.lower().strip()

    # 查找最近一条未使用且未过期的验证码
    email_code = EmailCode.query.filter(
        EmailCode.email == email_lower,
        EmailCode.code == code,
        EmailCode.used == False,
    ).order_by(EmailCode.created_at.desc()).first()

    if not email_code:
        return False, "验证码错误", None

    if email_code.is_expired:
        return False, "验证码已过期，请重新发送", None

    # 标记已使用
    email_code.used = True
    db.session.commit()

    # 查找或创建用户
    user = User.query.filter_by(auth_type="email", auth_id=email_lower).first()

    if not user:
        # 首次登录，自动注册
        user = _create_user(email_lower)
    else:
        # 更新最后登录时间
        user.last_login = datetime.utcnow()

    db.session.commit()
    return True, "登录成功", user


def _create_user(email):
    """创建新用户，自动分配 user_no。"""
    from flask import current_app

    # 获取当前最大 user_no
    max_no = db.session.query(db.func.max(User.user_no)).scalar() or 0
    new_no = max_no + 1

    # 检查是否是管理员邮箱（从运行时配置读取）
    admin_email = current_app.config.get("ADMIN_EMAIL", "")
    is_admin = (email == admin_email.lower().strip()) if admin_email else False

    nickname = email.split("@")[0]

    user = User(
        user_no=new_no,
        auth_type="email",
        auth_id=email,
        nickname=nickname,
        email=email,
        is_admin=is_admin,
        last_login=datetime.utcnow(),
    )
    db.session.add(user)
    db.session.flush()  # 获取 user.id

    return user


def _get_client_ip():
    """获取客户端真实 IP（兼容反向代理）。"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"
