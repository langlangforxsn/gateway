/**
 * auth.js — 登录模块
 * 提供：登录弹窗、邮箱验证码发送、登录、状态检查、登出
 * 依赖：Alpine.js（通过 CDN）
 */

// ---- 全局状态 ----
const AuthState = {
  user: null,
  loading: false,
  showModal: false,
  // 邮箱登录表单
  email: "",
  code: "",
  codeSent: false,
  countdown: 0,
  sending: false,
  verifying: false,
  error: "",
};

let countdownTimer = null;

// ---- API 请求封装 ----
async function authFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "请求失败");
  }
  return data;
}

// ---- 登录状态检查 ----
async function checkAuthStatus() {
  try {
    const data = await authFetch("/api/auth/status");
    if (data.logged_in) {
      AuthState.user = data.user;
    } else {
      AuthState.user = null;
    }
  } catch {
    AuthState.user = null;
  }
}

// ---- 发送验证码 ----
async function sendEmailCode() {
  AuthState.error = "";

  if (!AuthState.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(AuthState.email)) {
    AuthState.error = "请输入正确的邮箱地址";
    return;
  }

  AuthState.sending = true;
  try {
    await authFetch("/api/auth/email/send", {
      method: "POST",
      body: JSON.stringify({ email: AuthState.email }),
    });
    AuthState.codeSent = true;
    startCountdown();
  } catch (e) {
    AuthState.error = e.message;
  } finally {
    AuthState.sending = false;
  }
}

// ---- 倒计时 ----
function startCountdown() {
  AuthState.countdown = 60;
  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = setInterval(() => {
    AuthState.countdown--;
    if (AuthState.countdown <= 0) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  }, 1000);
}

// ---- 验证码登录 ----
async function verifyEmailCode() {
  AuthState.error = "";

  if (!AuthState.email) {
    AuthState.error = "请输入邮箱地址";
    return;
  }
  if (!AuthState.code || AuthState.code.length !== 6) {
    AuthState.error = "请输入 6 位验证码";
    return;
  }

  AuthState.verifying = true;
  try {
    const data = await authFetch("/api/auth/email/verify", {
      method: "POST",
      body: JSON.stringify({ email: AuthState.email, code: AuthState.code }),
    });
    AuthState.user = data.user;
    AuthState.showModal = false;
    resetLoginForm();
    // 登录成功回调（页面可覆盖）
    if (typeof onLoginSuccess === "function") {
      onLoginSuccess(data.user);
    }
  } catch (e) {
    AuthState.error = e.message;
  } finally {
    AuthState.verifying = false;
  }
}

// ---- 退出登录 ----
async function logout() {
  try {
    await authFetch("/api/auth/logout", { method: "POST" });
  } catch {
    // 即使请求失败也清除本地状态
  }
  AuthState.user = null;
  // 登出成功回调
  if (typeof onLogoutSuccess === "function") {
    onLogoutSuccess();
  }
}

// ---- 打开登录弹窗 ----
function openLoginModal() {
  resetLoginForm();
  AuthState.showModal = true;
}

// ---- 关闭登录弹窗 ----
function closeLoginModal() {
  AuthState.showModal = false;
  resetLoginForm();
}

// ---- 重置表单 ----
function resetLoginForm() {
  AuthState.email = "";
  AuthState.code = "";
  AuthState.codeSent = false;
  AuthState.countdown = 0;
  AuthState.error = "";
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

// ---- 格式化用户序号 ----
function formatUserNo(no) {
  return "#" + String(no).padStart(5, "0");
}

// ---- 登录弹窗 HTML 模板 ----
function getLoginModalHTML() {
  return `
  <div x-show="AuthState.showModal" x-cloak
       class="fixed inset-0 z-50 flex items-center justify-center"
       @keydown.escape.window="closeLoginModal()">
    <!-- 遮罩 -->
    <div class="absolute inset-0 bg-black/50" @click="closeLoginModal()"></div>
    <!-- 弹窗 -->
    <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
         x-transition:enter="transition ease-out duration-200"
         x-transition:enter-start="opacity-0 scale-95"
         x-transition:enter-end="opacity-100 scale-100">
      <!-- 关闭按钮 -->
      <button @click="closeLoginModal()"
              class="absolute top-4 right-4 text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
      <!-- 头部 -->
      <div class="bg-gradient-to-r from-indigo-500 to-purple-500 px-8 py-6 text-center">
        <div class="text-4xl mb-2">🐱</div>
        <h2 class="text-white text-xl font-bold">登录叮当猫的口袋</h2>
        <p class="text-white/80 text-sm mt-1">登录后解锁无限使用 + 个人中心</p>
      </div>
      <!-- 表单 -->
      <div class="px-8 py-6">
        <!-- 错误提示 -->
        <div x-show="AuthState.error" class="mb-4 p-3 bg-red-50 text-red-600 text-sm rounded-lg" x-text="AuthState.error"></div>

        <!-- 邮箱输入 -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">邮箱地址</label>
          <input type="email" x-model="AuthState.email"
                 placeholder="your@email.com"
                 :disabled="AuthState.codeSent"
                 class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition disabled:bg-gray-50">
        </div>

        <!-- 发送验证码按钮 -->
        <button x-show="!AuthState.codeSent"
                @click="sendEmailCode()"
                :disabled="AuthState.sending || !AuthState.email"
                class="w-full py-2.5 bg-indigo-500 text-white rounded-lg font-medium hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition mb-4">
          <span x-show="!AuthState.sending">发送验证码</span>
          <span x-show="AuthState.sending">发送中...</span>
        </button>

        <!-- 验证码输入（发送后显示） -->
        <div x-show="AuthState.codeSent" x-transition>
          <div class="mb-1 text-sm text-green-600">验证码已发送至 <span x-text="AuthState.email" class="font-medium"></span></div>
          <div class="flex gap-2 mb-4">
            <input type="text" x-model="AuthState.code"
                   placeholder="6 位验证码" maxlength="6"
                   @keyup.enter="verifyEmailCode()"
                   class="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition text-center text-lg tracking-[0.5em]">
            <button @click="sendEmailCode()"
                    :disabled="AuthState.countdown > 0 || AuthState.sending"
                    class="px-4 py-2.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition whitespace-nowrap">
              <span x-show="AuthState.countdown > 0" x-text="AuthState.countdown + 's'"></span>
              <span x-show="AuthState.countdown <= 0">重新发送</span>
            </button>
          </div>
          <button @click="verifyEmailCode()"
                  :disabled="AuthState.verifying || AuthState.code.length !== 6"
                  class="w-full py-2.5 bg-indigo-500 text-white rounded-lg font-medium hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition mb-4">
            <span x-show="!AuthState.verifying">登  录</span>
            <span x-show="AuthState.verifying">登录中...</span>
          </button>
        </div>

        <!-- 分隔线 -->
        <div class="flex items-center gap-3 my-4">
          <div class="flex-1 h-px bg-gray-200"></div>
          <span class="text-xs text-gray-400">或者</span>
          <div class="flex-1 h-px bg-gray-200"></div>
        </div>

        <!-- Gitee 登录 -->
        <button @click="alert('Gitee 登录即将上线，敬请期待')"
                class="w-full py-2.5 border border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50 transition flex items-center justify-center gap-2">
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="#c71d23"><path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm4.5 14.5h-9v-1h9v1zm0-3h-9v-1h9v1zm0-3h-9v-1h9v1z"/></svg>
          使用 Gitee 账号登录
        </button>
      </div>
    </div>
  </div>`;
}

// ---- 导航栏用户信息 HTML ----
function getNavUserHTML() {
  return `
  <!-- 未登录 -->
  <template x-if="!AuthState.user">
    <button @click="openLoginModal()"
            class="px-4 py-2 bg-indigo-500 text-white text-sm rounded-lg hover:bg-indigo-600 transition font-medium">
      登录
    </button>
  </template>
  <!-- 已登录 -->
  <template x-if="AuthState.user">
    <div class="relative" x-data="{ open: false }">
      <button @click="open = !open" class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 transition">
        <div class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-sm font-bold"
             x-text="AuthState.user.nickname.charAt(0).toUpperCase()"></div>
        <span class="text-sm text-gray-700 hidden sm:inline" x-text="AuthState.user.nickname"></span>
        <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
      </button>
      <!-- 下拉菜单 -->
      <div x-show="open" @click.away="open = false" x-cloak
           class="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border py-1 z-50">
        <div class="px-4 py-2 border-b">
          <div class="text-sm font-medium" x-text="AuthState.user.nickname"></div>
          <div class="text-xs text-gray-400" x-text="formatUserNo(AuthState.user.user_no)"></div>
        </div>
        <a href="/personal.html" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">个人中心</a>
        <a x-show="AuthState.user.is_admin" href="/admin.html" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">管理后台</a>
        <button @click="logout(); open = false" class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50">退出登录</button>
      </div>
    </div>
  </template>`;
}

// ---- 页面初始化 ----
document.addEventListener("DOMContentLoaded", () => {
  checkAuthStatus();
});
