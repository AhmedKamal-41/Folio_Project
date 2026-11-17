import { state } from "./state.js";

export async function api(path, options = {}) {
  const { userId = state.userId, ...request } = options;
  const headers = new Headers(request.headers);
  headers.set("X-User-Id", String(userId));
  if (request.body && !(request.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`/api${path}`, { ...request, headers, signal: controller.signal });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      let message = body.detail || "Something went wrong. Please try again.";
      if (Array.isArray(message)) message = message.map((item) => item.msg).join(" ");
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return response.status === 204 ? null : await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Request timed out. Your unsaved draft is still here.");
    if (error instanceof TypeError) throw new Error("Could not reach the server. Check your connection and retry.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
