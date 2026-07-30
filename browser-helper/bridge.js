/**
 * 网页与扩展后台之间的窄消息桥，只转发带 JobAgent 标记的请求和响应。
 */
// 页面与扩展的窄消息桥：只转发带 __jobagentHelper 标记的请求和响应。
const READY_MESSAGE = {
  __jobagentHelper: true,
  type: "JOBAGENT_HELPER_READY",
  version: "0.4.7"
};

window.postMessage(READY_MESSAGE, "*");

chrome.runtime.onMessage.addListener((message) => {
  if (message?.action !== "assistantContextUpdated") return;
  window.postMessage({
    __jobagentHelper: true,
    type: "JOBAGENT_HELPER_CONTEXT_UPDATED",
    conversationId: String(message.conversationId || "")
  }, "*");
});

window.addEventListener("message", (event) => {
  if (event.source !== window) {
    return;
  }
  const data = event.data;
  if (!data || data.__jobagentHelper !== true || !data.request) {
    return;
  }

  try {
    chrome.runtime.sendMessage(data.request, (response) => {
      const runtimeError = chrome.runtime.lastError;
      window.postMessage(
        {
          __jobagentHelper: true,
          response: {
            id: data.request.id,
            ...(response || {
              ok: false,
              error: runtimeError ? runtimeError.message : "empty helper response"
            })
          }
        },
        "*"
      );
    });
  } catch (error) {
    window.postMessage(
      {
        __jobagentHelper: true,
        response: {
          id: data.request.id,
          ok: false,
          error: String(error)
        }
      },
      "*"
    );
  }
});
