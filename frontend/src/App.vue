<template>
  <router-view v-if="$route.meta.public" />
  <el-container v-else class="app-shell">
    <el-aside width="224px" class="app-sidebar">
      <div class="brand"><img src="@/assets/logo.svg" alt="合审通 Logo" /><strong>合审通</strong></div>
      <el-menu :default-active="$route.path" router class="nav-menu">
        <el-menu-item index="/contract-review"><el-icon><DocumentChecked /></el-icon><span>合同审查</span></el-menu-item>
        <el-menu-item v-if="appStore.isAdmin" index="/scenes"><el-icon><CircleCheck /></el-icon><span>审查场景配置</span></el-menu-item>
        <el-menu-item v-if="appStore.isAdmin" index="/rules"><el-icon><Grid /></el-icon><span>审查规则配置</span></el-menu-item>
        <el-menu-item v-if="appStore.isAdmin" index="/models"><el-icon><Cpu /></el-icon><span>模型配置</span></el-menu-item>
        <el-menu-item v-if="appStore.isAdmin" index="/users"><el-icon><UserFilled /></el-icon><span>用户管理</span></el-menu-item>
      </el-menu>
      <div class="sidebar-account">
        <el-icon><User /></el-icon>
        <div><strong>{{ appStore.user?.email }}</strong><small>{{ appStore.isAdmin ? "管理员" : "普通用户" }}</small></div>
        <button type="button" title="退出登录" aria-label="退出登录" @click="signOut"><el-icon><SwitchButton /></el-icon></button>
      </div>
    </el-aside>
    <el-main class="app-main"><router-view /></el-main>
  </el-container>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import { useRouter } from "vue-router";
import { CircleCheck, Cpu, DocumentChecked, Grid, SwitchButton, User, UserFilled } from "@element-plus/icons-vue";
import type { AuthUser } from "@/stores/app";
import { logout } from "@/api/auth";
import { useAppStore } from "@/stores/app";

const appStore = useAppStore();
const router = useRouter();

async function signOut() {
  try { await logout(); } catch { /* The local session still needs to be cleared. */ }
  appStore.clearSession();
  await router.replace("/login");
}

function handleUnauthorized() { appStore.clearSession(); router.replace("/login"); }
function handleUserUpdated(event: Event) {
  const user = (event as CustomEvent<AuthUser>).detail;
  if (user && appStore.token) appStore.setSession(appStore.token, user);
}
onMounted(() => {
  window.addEventListener("auth:unauthorized", handleUnauthorized);
  window.addEventListener("auth:user-updated", handleUserUpdated);
});
onBeforeUnmount(() => {
  window.removeEventListener("auth:unauthorized", handleUnauthorized);
  window.removeEventListener("auth:user-updated", handleUserUpdated);
});
</script>
