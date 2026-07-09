"""
反向代理路由
转发请求到各工具后端，同时检查使用限制并记录日志。
"""
import requests as http_requests
from flask import request, Response, g
from proxy import bp

# ---- API 路径 → 工具名映射 ----
TOOL_MAP = {
    "merge": "pdf_merge",
    "split": "pdf_split",
    "compress": "pdf_compress",
    "encrypt": "pdf_encrypt",
    "decrypt": "pdf_encrypt",
    "rotate": "pdf_rotate",
    "delete-pages": "pdf_delete_pages",
    "add-page-numbers": "pdf_page_numbers",
    "convert/pdf-to-image": "pdf_to_image",
    "convert/image-to-pdf": "image_to_pdf",
    "convert/pdf-to-word": "pdf_to_word",
    "convert/office-to-pdf": "office_to_pdf",
    "watermark/text": "pdf_merge",      # 水印功能归入 pdf 工具
    "watermark/image": "pdf_merge",
}


def _get_client_ip():
    """获取客户端真实 IP。"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _resolve_tool_name(path):
    """从 URL 路径解析工具名（去掉 api/ 前缀）。"""
    # /api/merge → merge, /api/convert/pdf-to-word → convert/pdf-to-word
    clean = path
    if clean.startswith("api/"):
        clean = clean[4:]
    for prefix, tool_name in TOOL_MAP.items():
        if clean.startswith(prefix):
            return tool_name
    return None


def _check_and_log(tool_name):
    """
    检查使用限制，通过则记录日志。
    返回 (allowed, error_response) 或 (True, None)
    """
    from flask_login import current_user
    from user.models import LimitConfig
    from utils.usage_tracker import log_usage, get_today_count

    config = LimitConfig.query.filter_by(tool_name=tool_name).first()
    if not config or not config.enabled:
        return True, None  # 无配置或已禁用，不拦截

    ip = _get_client_ip()

    # 已登录用户
    if current_user.is_authenticated:
        if config.login_daily > 0:
            count = get_today_count(tool_name, user_id=current_user.id)
            if count >= config.login_daily:
                return False, ({"error": f"今日使用次数已达上限（{config.login_daily} 次）", "code": "DAILY_LIMIT"}, 429)
        log_usage(tool_name, user_id=current_user.id, ip=ip)
        g.remaining = -1
        return True, None

    # 未登录：必须登录的功能
    if config.require_login:
        return False, ({"error": "此功能需要登录后使用", "code": "LOGIN_REQUIRED", "tool_label": config.tool_label}, 403)

    # 未登录：检查每日限制
    if config.guest_daily <= 0:
        return False, ({"error": "此功能需要登录后使用", "code": "LOGIN_REQUIRED"}, 403)

    count = get_today_count(tool_name, ip=ip)
    if count >= config.guest_daily:
        return False, ({
            "error": f"今日免费次数已用完（{config.guest_daily}/{config.guest_daily}），登录解锁无限使用",
            "code": "DAILY_LIMIT",
            "remaining": 0,
            "limit": config.guest_daily,
        }, 429)

    # 放行，记录使用
    log_usage(tool_name, ip=ip)
    g.remaining = config.guest_daily - count - 1
    return True, None


def _build_headers(backend_resp):
    """从后端响应构建前端响应头，附加使用次数信息。"""
    headers = {}
    for key, value in backend_resp.headers.items():
        key_lower = key.lower()
        # 跳过 hop-by-hop 头和可能冲突的头
        if key_lower in ("transfer-encoding", "connection", "content-encoding", "content-length"):
            continue
        headers[key] = value

    # 附加剩余使用次数
    remaining = getattr(g, "remaining", None)
    if remaining is not None:
        headers["X-Remaining"] = str(remaining)

    return headers


# ============================================
#  PDF 工具代理
# ============================================
@bp.route("/pdf/", defaults={"subpath": ""})
@bp.route("/pdf/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
def proxy_pdf(subpath):
    """代理转发到 PDF 工具后端。"""
    from flask import current_app
    backend_base = current_app.config.get("PDF_TOOL_API", "")

    if not backend_base:
        return {"error": "PDF 工具后端未配置"}, 503

    # 构建目标 URL
    target_url = f"{backend_base}/{subpath}"
    if request.query_string:
        target_url += f"?{request.query_string.decode('utf-8')}"

    # POST 请求：检查使用限制
    tool_name = _resolve_tool_name(subpath)
    if request.method == "POST" and tool_name:
        allowed, error_resp = _check_and_log(tool_name)
        if not allowed:
            return error_resp

    # 转发请求
    try:
        # 构建请求头（过滤掉 host 等）
        fwd_headers = {
            key: value for key, value in request.headers
            if key.lower() not in ("host", "content-length", "transfer-encoding")
        }
        fwd_headers["X-Forwarded-For"] = _get_client_ip()
        fwd_headers["X-Real-IP"] = _get_client_ip()

        # 发起请求
        if request.content_type and "multipart/form-data" in request.content_type:
            # 文件上传：转发 form data
            resp = http_requests.request(
                method=request.method,
                url=target_url,
                headers=fwd_headers,
                files={k: (v.filename, v.stream, v.content_type) for k, v in request.files.items()},
                data=request.form,
                timeout=120,
                allow_redirects=False,
            )
        else:
            # 普通请求
            resp = http_requests.request(
                method=request.method,
                url=target_url,
                headers=fwd_headers,
                data=request.get_data(),
                timeout=120,
                allow_redirects=False,
            )

        # 构建响应
        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        response_headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]

        # 附加剩余使用次数
        remaining = getattr(g, "remaining", None)
        if remaining is not None:
            response_headers.append(("X-Remaining", str(remaining)))

        return Response(resp.content, resp.status_code, response_headers)

    except http_requests.Timeout:
        return {"error": "请求超时，请稍后重试"}, 504
    except http_requests.ConnectionError:
        return {"error": "PDF 工具服务暂时不可用"}, 503
    except Exception as e:
        return {"error": f"代理请求失败: {str(e)}"}, 502


# ============================================
#  图片转换工具代理
# ============================================
@bp.route("/img/", defaults={"subpath": ""})
@bp.route("/img/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
def proxy_img(subpath):
    """代理转发到图片转换后端。"""
    from flask import current_app
    backend_base = current_app.config.get("IMAGE_CONVERTER_API", "")

    if not backend_base:
        return {"error": "图片转换服务未配置"}, 503

    target_url = f"{backend_base}/{subpath}"
    if request.query_string:
        target_url += f"?{request.query_string.decode('utf-8')}"

    try:
        fwd_headers = {
            key: value for key, value in request.headers
            if key.lower() not in ("host", "content-length", "transfer-encoding")
        }
        fwd_headers["X-Forwarded-For"] = _get_client_ip()

        resp = http_requests.request(
            method=request.method,
            url=target_url,
            headers=fwd_headers,
            data=request.get_data(),
            timeout=120,
            allow_redirects=False,
        )

        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        response_headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]
        return Response(resp.content, resp.status_code, response_headers)

    except http_requests.Timeout:
        return {"error": "请求超时"}, 504
    except http_requests.ConnectionError:
        return {"error": "图片转换服务暂时不可用"}, 503
    except Exception as e:
        return {"error": f"代理请求失败: {str(e)}"}, 502
