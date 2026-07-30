/**
 * 协调浏览器扩展探测、受限 token 配对、BOSS 登录检查和搜索请求。
 */
import { computed, onUnmounted, ref, type ComputedRef } from "vue";

import {
  checkBossLoginStatus,
  openBossLoginPage,
  pingBrowserHelper,
  type BossLoginStatus,
  type BrowserHelperStatus
} from "../services/browserHelper";

export function useBrowserHelperSession(isActive: ComputedRef<boolean>) {
  const browserHelperStatus = ref<BrowserHelperStatus | null>(null);
  const bossLoginStatus = ref<BossLoginStatus | null>(null);
  const isBrowserHelperChecking = ref(false);
  const isBossLoginChecking = ref(false);
  const browserHelperMessage = ref<string | null>(null);
  let bossLoginRefreshTimer: number | null = null;

  const browserHelperStatusTag = computed(() => {
    if (!browserHelperStatus.value) {
      return "Not checked";
    }
    return browserHelperStatus.value.installed ? "Detected" : "Not detected";
  });
  const bossLoginStatusTag = computed(() => {
    if (!bossLoginStatus.value) {
      return "Not checked";
    }
    return bossLoginStatus.value.loggedIn ? "Logged in" : "Login required";
  });
  const bossLoginStatusSummary = computed(() => {
    if (!bossLoginStatus.value) {
      return "Check after detecting helper";
    }
    return formatBossLoginStatusSummary(bossLoginStatus.value);
  });
  const canCheckBossLogin = computed(() => Boolean(browserHelperStatus.value?.installed));

  async function checkBrowserHelper(): Promise<void> {
    isBrowserHelperChecking.value = true;
    browserHelperMessage.value = null;
    try {
      browserHelperStatus.value = await pingBrowserHelper();
      browserHelperMessage.value = browserHelperStatus.value.error;
      if (browserHelperStatus.value.installed) {
        await checkBossLogin();
      } else {
        bossLoginStatus.value = null;
      }
    } finally {
      isBrowserHelperChecking.value = false;
    }
  }

  async function checkBossLogin(): Promise<void> {
    if (!browserHelperStatus.value?.installed) {
      browserHelperMessage.value = "Install and detect the Browser Helper first.";
      return;
    }
    isBossLoginChecking.value = true;
    browserHelperMessage.value = null;
    try {
      bossLoginStatus.value = await checkBossLoginStatus();
      browserHelperMessage.value = formatBossLoginStatusMessage(bossLoginStatus.value);
      if (bossLoginStatus.value.loggedIn) {
        stopBossLoginAutoRefresh();
      }
    } catch (error) {
      browserHelperMessage.value =
        error instanceof Error ? error.message : "BOSS login status check failed.";
    } finally {
      isBossLoginChecking.value = false;
    }
  }

  async function openBossLogin(): Promise<void> {
    if (!browserHelperStatus.value?.installed) {
      browserHelperMessage.value = "Install and detect the Browser Helper first.";
      return;
    }
    try {
      await openBossLoginPage();
      bossLoginStatus.value = null;
      browserHelperMessage.value =
        "BOSS login page opened. Login status will refresh automatically.";
      startBossLoginAutoRefresh();
    } catch (error) {
      browserHelperMessage.value =
        error instanceof Error ? error.message : "Failed to open BOSS login page.";
    }
  }

  function startBossLoginAutoRefresh(): void {
    stopBossLoginAutoRefresh();
    let attempts = 0;
    const poll = async () => {
      attempts += 1;
      if (!isActive.value || !browserHelperStatus.value?.installed) {
        stopBossLoginAutoRefresh();
        return;
      }
      await checkBossLogin();
      if (bossLoginStatus.value?.loggedIn || attempts >= 24) {
        if (!bossLoginStatus.value?.loggedIn && attempts >= 24) {
          browserHelperMessage.value =
            "BOSS login was not verified after automatic refresh. Use Check BOSS Login after completing login or verification.";
        }
        stopBossLoginAutoRefresh();
        return;
      }
      bossLoginRefreshTimer = window.setTimeout(() => {
        void poll();
      }, 5000);
    };
    bossLoginRefreshTimer = window.setTimeout(() => {
      void poll();
    }, 3000);
  }

  function stopBossLoginAutoRefresh(): void {
    if (bossLoginRefreshTimer !== null) {
      window.clearTimeout(bossLoginRefreshTimer);
      bossLoginRefreshTimer = null;
    }
  }

  onUnmounted(stopBossLoginAutoRefresh);

  return {
    browserHelperStatus,
    bossLoginStatus,
    isBrowserHelperChecking,
    isBossLoginChecking,
    browserHelperMessage,
    browserHelperStatusTag,
    bossLoginStatusTag,
    bossLoginStatusSummary,
    canCheckBossLogin,
    checkBrowserHelper,
    checkBossLogin,
    openBossLogin
  };
}

function formatBossLoginStatusMessage(status: BossLoginStatus): string {
  if (status.loggedIn) {
    return "BOSS login verified by a live page probe.";
  }
  if (status.cookieLoggedIn) {
    return `BOSS cookies exist but the live session is not usable: ${status.verificationReason ?? status.verificationStatus}.`;
  }
  return status.verificationReason ?? "BOSS login is required before helper search.";
}

function formatBossLoginStatusSummary(status: BossLoginStatus): string {
  const cookieSummary = `${status.cookieCount} cookies, ${status.matchedAuthCookies.length} auth-like`;
  const probeSummary = `${status.probeJobCardCount} cards, ${status.probeValidJobDetailLinkCount} valid links`;
  if (status.loggedIn) {
    return `Verified session - ${cookieSummary}; probe ${probeSummary}`;
  }
  if (status.cookieLoggedIn) {
    return `Cookies present but not verified - ${status.verificationStatus}; probe ${probeSummary}`;
  }
  return `Not logged in - ${cookieSummary}; ${status.verificationStatus}`;
}
