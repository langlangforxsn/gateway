"""
QR 码生成工具
POST /api/tools/qr → 生成二维码，返回 base64 PNG
"""
import io
import base64
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from flask import Blueprint, request, jsonify

bp = Blueprint("tools", __name__, url_prefix="/api/tools")


@bp.route("/qr", methods=["POST"])
def generate_qr():
    """生成二维码，返回 base64 图片。"""
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    fill_color = data.get("fill_color", "#000000")
    back_color = data.get("back_color", "#FFFFFF")
    box_size = min(max(data.get("box_size", 10), 4), 20)

    if not content:
        return jsonify({"error": "请输入内容"}), 400

    if len(content) > 2000:
        return jsonify({"error": "内容过长，最多 2000 字符"}), 400

    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=2,
        )
        qr.add_data(content)
        qr.make(fit=True)

        img = qr.make_image(
            fill_color=fill_color,
            back_color=back_color,
        )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return jsonify({
            "image": f"data:image/png;base64,{img_base64}",
            "version": qr.version,
        })
    except Exception as e:
        return jsonify({"error": f"生成失败：{str(e)}"}), 500
