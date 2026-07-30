/**
 * 前端启动入口：安装 Pinia 与路由后挂载根组件，具体业务状态由各 Store 恢复。
 */
import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import "./style.css";

createApp(App).use(createPinia()).use(router).mount("#app");
