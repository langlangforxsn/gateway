/**
 * limit-check.js — 使用限制提示组件
 * 功能：
 * - 每次请求后从 X-Remaining header 读取剩余次数
 * - 剩余 ≤1 时显示提醒 toast
 * - 超限时弹出登录引导弹窗
 * 依赖：auth.js（AuthState, openLoginModal）
 */

const LimitCheck = {
  // 当前剩余次数（-1 = 无限制/未获取）
  remaining: -1,
  // toast 消息
  toastMsg: "",
  toastType: "info", // info | warning | error
  toastVisible: false,
  toastTimer: null,
  // 超限弹窗
  limitModalVisible: false,
  limitModalMsg: "",
  limitModalToolLabel: "",
};

// ---- 从 fetch 响应中读取使用限制信息 ----
function checkLimitFromResponse(response) {
  const remaining = response.headers.get("X-Remaining");
  if (remaining !== null) {
    LimitCheck.remaining = parseInt(remaining, 10);
    updateRemainingBadge();
  }

  // 处理超限响应
  if (response.status === 429) {
    response.clone().json().then(data => {
      if (data.code === "DAILY_LIMIT") {
        LimitCheck.limitModalMsg = data.error || "今日免费次数已用完";
        LimitCheck.limitModalVisible = true;
      }
    }).catch(() => {});
  }

  // 处理需要登录的响应
  if (response.status === 403) {
    response.clone().json().then(data => {
      if (data.code === "LOGIN_REQUIRED") {
        LimitCheck.limitModalToolLabel = data.tool_label || "";
        LimitCheck.limitModalMsg = data.error || "此功能需要登录后使用";
        LimitCheck.limitModalVisible = true;
      }
    }).catch(() => {});
  }
}

// ---- 更新剩余次数角标 ----
function updateRemainingBadge() {
  const badge = document.getElementById("remaining-badge");
  if (!badge) return;

  if (LimitCheck.remaining < 0) {
    badge.style.display = "none";
    return;
  }

  badge.style.display = "flex";
  if (LimitCheck.remaining <= 0) {
    badge.className = "fixed bottom-4 right-4 z-40 px-4 py-2 bg-red-500 text-white rounded-full shadow-lg text-sm font-medium flex items-center gap-2";
    badge.innerHTML = `<span>⛔ 今日免费次数已用完</span>`;
  } else if (LimitCheck.remaining <= 1) {
    badge.className = "fixed bottom-4 right-4 z-40 px-4 py-2 bg-amber-500 text-white rounded-full shadow-lg text-sm font-medium flex items-center gap-2";
    badge.innerHTML = `<span>⚡ 今日剩余 ${LimitCheck.remaining} 次</span>`;
    if (!AuthState.user) {
      badge.innerHTML += `<button onclick="openLoginModal()" class="underline hover:no-underline">登录</button>`;
    }
  } else {
    badge.className = "fixed bottom-4 right-4 z-40 px-4 py-2 bg-green-500/90 text-white rounded-full shadow-lg text-sm flex items-center gap-2";
    badge.innerHTML = `<span>✓ 今日剩余 ${LimitCheck.remaining} 次</span>`;
  }
}

// ---- 显示 toast ----
function showLimitToast(msg, type = "info") {
  LimitCheck.toastMsg = msg;
  LimitCheck.toastType = type;
  LimitCheck.toastVisible = true;
  if (LimitCheck.toastTimer) clearTimeout(LimitCheck.toastTimer);
  LimitCheck.toastTimer = setTimeout(() => {
    LimitCheck.toastVisible = false;
  }, 4000);
}

// ---- 关闭超限弹窗 ----
function closeLimitModal() {
  LimitCheck.limitModalVisible = false;
}

// ---- Hook fetch 以自动检查限制 ----
(function hookFetch() {
  const originalFetch = window.fetch;
  window.fetch = async function(...args) {
    const response = await originalFetch.apply(this, args);
    // 仅对代理路径检查限制
    const url = typeof args[0] === "string" ? args[0] : args[0]?.url || "";
    if (url.startsWith("/proxy/")) {
      checkLimitFromResponse(response);
    }
    return response;
  };
})();

// ---- 限制提示组件 HTML（注入到页面） ----
function getLimitCheckHTML() {
  return `
  <!-- 剩余次数角标 -->
  <div id="remaining-badge" style="display:none"></div>

  <!-- 超限弹窗 -->
  <div x-show="LimitCheck.limitModalVisible" x-cloak
       class="fixed inset-0 z-50 flex items-center justify-center"
       @keydown.escape.window="closeLimitModal()">
    <div class="absolute inset-0 bg-black/50" @click="closeLimitModal()"></div>
    <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-8 text-center"
         x-transition:enter="transition ease-out duration-200"
         x-transition:enter-start="opacity-0 scale-95"
         x-transition:enter-end="opacity-100 scale-100">
      <div class="text-5xl mb-4">🔒</div>
      <h3 class="text-lg font-bold mb-2" x-text="LimitCheck.limitModalToolLabel ? LimitCheck.limitModalToolLabel + ' 需要登录' : '使用次数已达上限'"></h3>
      <p class="text-gray-500 text-sm mb-6" x-text="LimitCheck.limitModalMsg"></p>
      <button onclick="closeLimitModal(); openLoginModal()"
              class="w-full py-2.5 bg-indigo-500 text-white rounded-lg font-medium hover:bg-indigo-600 transition mb-3">
        立即登录
      </button>
      <button onclick="closeLimitModal()"
              class="w-full py-2 text-gray-400 text-sm hover:text-gray-600 transition">
        稍后再说
      </button>
    </div>
  </div>

  <!-- Toast -->
  <div x-show="LimitCheck.toastVisible" x-cloak
       class="fixed top-20 right-4 z-50 max-w-sm"
       x-transition:enter="transition ease-out duration-300"
       x-transition:enter-start="opacity-0 translate-x-8"
       x-transition:enter-end="opacity-100 translate-x-0"
       x-transition:leave="transition ease-in duration-200"
       x-transition:leave-start="opacity-100"
       x-transition:leave-end="opacity-0">
    <div class="rounded-lg shadow-lg px-4 py-3 text-sm"
         :class="{
           'bg-blue-50 text-blue-700 border border-blue-200': LimitCheck.toastType === 'info',
           'bg-amber-50 text-amber-700 border border-amber-200': LimitCheck.toastType === 'warning',
           'bg-red-50 text-red-700 border border-red-200': LimitCheck.toastType === 'error',
         }"
         x-text="LimitCheck.toastMsg">
    </div>
  </div>`;
}

// ---- 页面加载时初始化 ----
document.addEventListener("DOMContentLoaded", () => {
  // 注入剩余次数角标
  const badge = document.createElement("div");
  badge.id = "remaining-badge";
  badge.style.display = "none";
  document.body.appendChild(badge);
});
