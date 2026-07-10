/**
 * gateway-guard.js — 工具页面登录拦截脚本
 * 引入此脚本的页面会自动检查 Gateway 登录状态，
 * 未登录时在页面顶部显示提醒条，引导用户登录。
 *
 * 使用方式：在工具页面 <head> 中加一行：
 *   <script src="https://gateway-w7tf.onrender.com/js/guard.js" defer></script>
 */
(function () {
  const GATEWAY = "https://gateway-w7tf.onrender.com";

  // 避免重复注入
  if (document.getElementById("gateway-guard-bar")) return;

  fetch(GATEWAY + "/api/auth/status", { credentials: "include" })
    .then((res) => res.json())
    .then((data) => {
      if (data.logged_in) return; // 已登录，什么也不做

      // 创建提醒条
      const bar = document.createElement("div");
      bar.id = "gateway-guard-bar";
      bar.style.cssText =
        "position:fixed;top:0;left:0;right:0;z-index:9999;" +
        "background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;" +
        "padding:10px 16px;text-align:center;font-size:14px;" +
        "display:flex;align-items:center;justify-content:center;gap:12px;" +
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;";

      bar.innerHTML = `
        <span>🔒 你尚未登录，每日有使用次数限制</span>
        <a href="${GATEWAY}" target="_blank"
           style="display:inline-block;padding:4px 16px;background:#fff;color:#6366f1;
                  border-radius:6px;font-weight:600;text-decoration:none;font-size:13px;">
          立即登录
        </a>
        <button onclick="this.parentElement.remove()"
                style="background:none;border:none;color:#fff;cursor:pointer;font-size:18px;padding:0 4px;">
          ×
        </button>
      `;

      document.body.prepend(bar);

      // 如果页面有固定导航栏，给 body 加一点间距
      const existingNav = document.querySelector("nav.fixed, nav.sticky, header.fixed");
      if (existingNav) {
        existingNav.style.top = bar.offsetHeight + "px";
        bar.style.top = "0";
      }
    })
    .catch(() => {}); // Gateway 挂了静默放行
})();
