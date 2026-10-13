import { createRouter, createWebHistory } from "vue-router";

import { getCurrentUser } from "@/api/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/contract-review"
    },
    {
      path: "/login",
      name: "login",
      component: () => import("@/views/LoginView.vue"),
      meta: { public: true }
    },
    {
      path: "/contract-review",
      name: "contract-review",
      component: () => import("@/views/ContractReviewView.vue")
    },
    {
      path: "/scenes",
      name: "scenes",
      component: () => import("@/views/SceneConfigView.vue"),
      meta: { admin: true }
    },
    {
      path: "/rules",
      name: "rules",
      component: () => import("@/views/RuleConfigView.vue"),
      meta: { admin: true }
    },
    {
      path: "/models",
      name: "models",
      component: () => import("@/views/ModelConfigView.vue"),
      meta: { admin: true }
    },
    {
      path: "/users",
      name: "users",
      component: () => import("@/views/UserManagementView.vue"),
      meta: { admin: true }
    }
  ]
});

router.beforeEach(async (to) => {
  const token = localStorage.getItem("auth_token");
  let role = "";
  try { role = JSON.parse(localStorage.getItem("auth_user") || "null")?.role || ""; }
  catch { role = ""; }
  if (to.meta.public) return token ? "/contract-review" : true;
  if (!token) return { path: "/login", query: { redirect: to.fullPath } };
  if (to.meta.admin) {
    if (role !== "admin") return "/contract-review";
    try {
      const user = await getCurrentUser();
      localStorage.setItem("auth_user", JSON.stringify(user));
      window.dispatchEvent(new CustomEvent("auth:user-updated", { detail: user }));
      if (user.role !== "admin") return "/contract-review";
    } catch {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_user");
      return { path: "/login", query: { redirect: to.fullPath } };
    }
  }
  return true;
});

export default router;
