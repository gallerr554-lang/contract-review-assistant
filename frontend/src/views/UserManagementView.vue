<template>
  <section class="config-page">
    <div class="config-panel">
      <header class="config-page-header">
        <div><h1>用户管理</h1><p>查询系统账号，维护用户角色、启停状态和登录密码。</p></div>
      </header>

      <form class="config-toolbar" @submit.prevent="searchUsers">
        <el-input v-model="filters.keyword" class="search-input" clearable placeholder="按用户邮箱查询" :prefix-icon="Search" />
        <el-select v-model="filters.role" class="filter-select" clearable placeholder="用户角色">
          <el-option label="管理员" value="admin" />
          <el-option label="普通用户" value="user" />
        </el-select>
        <el-select v-model="filters.enabled" class="filter-select" clearable placeholder="账号状态">
          <el-option label="启用" value="true" />
          <el-option label="停用" value="false" />
        </el-select>
        <div class="config-toolbar-actions"><el-button @click="resetFilters">重置</el-button><el-button type="primary" native-type="submit">查询</el-button></div>
      </form>

      <div class="config-table-wrap user-table-wrap">
        <el-table v-loading="loading" :data="users" empty-text="未查询到符合条件的用户">
          <el-table-column label="用户邮箱" min-width="230">
            <template #default="{ row }"><strong class="item-title">{{ row.email }}</strong><small v-if="isSelf(row)" class="item-subtitle">当前登录账号</small></template>
          </el-table-column>
          <el-table-column label="用户角色" width="120"><template #default="{ row }"><span :class="row.role === 'admin' ? 'role-tag-admin' : 'role-tag-user'">{{ roleLabel(row.role) }}</span></template></el-table-column>
          <el-table-column label="账号状态" width="105"><template #default="{ row }"><span :class="row.status ? 'state-tag-on' : 'state-tag-off'">{{ row.status ? "启用" : "停用" }}</span></template></el-table-column>
          <el-table-column label="注册时间" width="180"><template #default="{ row }">{{ formatTime(row.create_time) }}</template></el-table-column>
          <el-table-column label="最近登录时间" width="180"><template #default="{ row }">{{ formatTime(row.last_login_time) }}</template></el-table-column>
          <el-table-column prop="task_count" label="审查任务数量" width="125" align="center" />
          <el-table-column label="操作" width="218" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
                <button class="table-icon-button" type="button" title="查看用户详情" @click="openDetail(row)"><el-icon><View /></el-icon></button>
                <button class="table-icon-button" type="button" :title="row.role === 'admin' ? '调整为普通用户' : '调整为管理员'" :disabled="isSelf(row)" @click="confirmRoleChange(row)"><el-icon><UserFilled /></el-icon></button>
                <el-switch :model-value="row.status" :disabled="isSelf(row)" inline-prompt active-text="启" inactive-text="停" @change="(value: string | number | boolean) => confirmStatusChange(row, Boolean(value))" />
                <button class="table-icon-button" type="button" title="重置用户密码" :disabled="isSelf(row)" @click="openPasswordReset(row)"><el-icon><Key /></el-icon></button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <footer class="user-pagination">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next" @current-change="loadUsers" @size-change="handlePageSizeChange" />
      </footer>
    </div>

    <el-dialog v-model="detailVisible" title="用户详情" width="min(620px, 94vw)">
      <dl v-if="selectedUser" class="user-detail-grid">
        <div><dt>用户邮箱</dt><dd>{{ selectedUser.email }}</dd></div>
        <div><dt>用户角色</dt><dd>{{ roleLabel(selectedUser.role) }}</dd></div>
        <div><dt>账号状态</dt><dd>{{ selectedUser.status ? "启用" : "停用" }}</dd></div>
        <div><dt>审查任务数量</dt><dd>{{ selectedUser.task_count }}</dd></div>
        <div><dt>注册时间</dt><dd>{{ formatTime(selectedUser.create_time) }}</dd></div>
        <div><dt>最近登录时间</dt><dd>{{ formatTime(selectedUser.last_login_time) }}</dd></div>
      </dl>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="passwordVisible" title="重置用户密码" width="min(560px, 94vw)" destroy-on-close>
      <p class="password-target">正在为 <strong>{{ selectedUser?.email }}</strong> 设置新密码。保存后该用户的现有会话将立即失效。</p>
      <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-position="top">
        <el-form-item label="新密码" prop="newPassword"><el-input v-model="passwordForm.newPassword" type="password" show-password autocomplete="new-password" maxlength="128" /></el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword"><el-input v-model="passwordForm.confirmPassword" type="password" show-password autocomplete="new-password" maxlength="128" /></el-form-item>
      </el-form>
      <template #footer><div class="dialog-footer"><el-button @click="passwordVisible = false">取消</el-button><el-button type="primary" :loading="savingPassword" @click="savePassword">确认重置</el-button></div></template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { Key, Search, UserFilled, View } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus/es/components/message/index";
import { ElMessageBox } from "element-plus/es/components/message-box/index";
import type { FormInstance, FormRules } from "element-plus";

import { apiErrorMessage } from "@/api/http";
import { getManagedUser, listUsers, resetUserPassword, setUserRole, setUserStatus, type ManagedUser, type UserRole } from "@/api/user";
import { useAppStore } from "@/stores/app";

interface PasswordForm { newPassword: string; confirmPassword: string }

const appStore = useAppStore();
const filters = reactive({ keyword: "", role: "", enabled: "" });
const users = ref<ManagedUser[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);
const loading = ref(false);
const detailVisible = ref(false);
const passwordVisible = ref(false);
const savingPassword = ref(false);
const selectedUser = ref<ManagedUser>();
const passwordFormRef = ref<FormInstance>();
const passwordForm = reactive<PasswordForm>({ newPassword: "", confirmPassword: "" });
const passwordRules: FormRules<PasswordForm> = {
  newPassword: [
    { required: true, message: "请输入新密码", trigger: "blur" },
    { min: 8, max: 128, message: "密码长度为 8 至 128 位", trigger: "blur" },
    { validator: (_rule, value, callback) => { const text = String(value || ""); if (!/[A-Za-z]/.test(text) || !/\d/.test(text)) callback(new Error("密码必须同时包含字母和数字")); else callback(); }, trigger: "blur" }
  ],
  confirmPassword: [{ validator: (_rule, value, callback) => { if (!value) callback(new Error("请再次输入新密码")); else if (value !== passwordForm.newPassword) callback(new Error("两次输入的密码不一致")); else callback(); }, trigger: "blur" }]
};

function isSelf(user: ManagedUser) { return user.id === appStore.user?.id; }
function roleLabel(role: UserRole) { return role === "admin" ? "管理员" : "普通用户"; }
function formatTime(value: string | null) { return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "从未登录"; }

async function loadUsers() {
  loading.value = true;
  try {
    const result = await listUsers({
      keyword: filters.keyword.trim() || undefined,
      role: (filters.role || undefined) as UserRole | undefined,
      enabled: filters.enabled ? filters.enabled === "true" : undefined,
      page: page.value,
      page_size: pageSize.value
    });
    users.value = result.items;
    total.value = result.total;
  } catch (error) { ElMessage.error(apiErrorMessage(error, "用户列表加载失败。")); }
  finally { loading.value = false; }
}

function searchUsers() { page.value = 1; loadUsers(); }
function resetFilters() { Object.assign(filters, { keyword: "", role: "", enabled: "" }); page.value = 1; loadUsers(); }
function handlePageSizeChange() { page.value = 1; loadUsers(); }

async function openDetail(user: ManagedUser) {
  try { selectedUser.value = await getManagedUser(user.id); detailVisible.value = true; }
  catch (error) { ElMessage.error(apiErrorMessage(error, "用户详情加载失败。")); }
}

async function confirmStatusChange(user: ManagedUser, enabled: boolean) {
  try {
    await ElMessageBox.confirm(`确认${enabled ? "启用" : "停用"}用户“${user.email}”吗？${enabled ? "" : "停用后该用户的现有会话将立即失效。"}`, `${enabled ? "启用" : "停用"}用户`, { type: "warning", confirmButtonText: "确认", cancelButtonText: "取消" });
    await setUserStatus(user.id, enabled);
    ElMessage.success(enabled ? "用户已启用" : "用户已停用");
    await loadUsers();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(apiErrorMessage(error, "用户状态更新失败。"));
  }
}

async function confirmRoleChange(user: ManagedUser) {
  const role: UserRole = user.role === "admin" ? "user" : "admin";
  try {
    await ElMessageBox.confirm(`确认将用户“${user.email}”调整为${roleLabel(role)}吗？`, "调整用户角色", { type: "warning", confirmButtonText: "确认调整", cancelButtonText: "取消" });
    await setUserRole(user.id, role);
    ElMessage.success(`用户已调整为${roleLabel(role)}`);
    await loadUsers();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(apiErrorMessage(error, "用户角色更新失败。"));
  }
}

function openPasswordReset(user: ManagedUser) {
  selectedUser.value = user;
  Object.assign(passwordForm, { newPassword: "", confirmPassword: "" });
  passwordVisible.value = true;
}

async function savePassword() {
  if (!selectedUser.value || !await passwordFormRef.value?.validate().catch(() => false)) return;
  savingPassword.value = true;
  try {
    await resetUserPassword(selectedUser.value.id, passwordForm.newPassword);
    ElMessage.success("用户密码已重置，原有会话已失效");
    passwordVisible.value = false;
  } catch (error) { ElMessage.error(apiErrorMessage(error, "用户密码重置失败。")); }
  finally { savingPassword.value = false; }
}

loadUsers();
</script>

<style scoped>
.user-table-wrap .el-table{min-width:1240px}.role-tag-admin,.role-tag-user{display:inline-flex;min-height:24px;align-items:center;border-radius:4px;padding:0 8px;font-size:12px;font-weight:600}.role-tag-admin{background:#e8edfb;color:#4159a3}.role-tag-user{background:#eaf4f2;color:#176c64}.table-icon-button:disabled{opacity:.35;cursor:not-allowed}.table-icon-button:disabled:hover{background:transparent;color:#53615e}.user-pagination{display:flex;justify-content:flex-end;padding:16px 22px;border-top:1px solid #edf1f0}.user-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:0}.user-detail-grid div{min-width:0;border:1px solid #e5ecea;border-radius:7px;padding:12px;background:#fbfcfc}.user-detail-grid dt{margin-bottom:6px;color:#788480;font-size:12px}.user-detail-grid dd{overflow-wrap:anywhere;margin:0;color:var(--ink);font-weight:600}.password-target{margin:0 0 18px;color:var(--muted);line-height:1.7}@media(max-width:720px){.user-pagination{justify-content:flex-start;overflow-x:auto}.user-detail-grid{grid-template-columns:1fr}}
</style>
