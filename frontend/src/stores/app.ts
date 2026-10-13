import { defineStore } from "pinia";

export interface AuthUser {
  id: number;
  email: string;
  role: "user" | "admin";
  status: boolean;
  create_time: string;
}

function storedUser(): AuthUser | null {
  try {
    return JSON.parse(localStorage.getItem("auth_user") || "null") as AuthUser | null;
  } catch {
    return null;
  }
}

export const useAppStore = defineStore("app", {
  state: () => ({
    productName: "合审通",
    token: localStorage.getItem("auth_token") || "",
    user: storedUser()
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
    isAdmin: (state) => state.user?.role === "admin"
  },
  actions: {
    setSession(token: string, user: AuthUser) {
      this.token = token;
      this.user = user;
      localStorage.setItem("auth_token", token);
      localStorage.setItem("auth_user", JSON.stringify(user));
    },
    clearSession() {
      this.token = "";
      this.user = null;
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_user");
    }
  }
});
