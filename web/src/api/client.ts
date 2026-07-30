/**
 * 统一配置 Axios：注入登录 token，并把后端错误结构转换成页面可直接展示的异常。
 */
import axios from "axios";
import { getAuthToken } from "../services/authToken";

export const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? ""
});

client.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});
