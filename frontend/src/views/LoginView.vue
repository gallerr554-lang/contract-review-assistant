<template>
  <main class="auth-page">
    <section class="auth-visual" aria-label="合同审查品牌区">
      <div class="auth-brand"><img src="@/assets/logo.svg" alt="合审通 Logo" /><strong>合审通</strong></div>
      <div class="auth-copy"><span>CONTRACT REVIEW</span><h1>合同审查工作台</h1><p>统一管理审查任务、风险结果和审查配置。</p></div>
    </section>
    <section class="auth-form-panel">
      <div class="auth-form-wrap">
        <header><h2>{{ mode === "login" ? "登录" : "创建账号" }}</h2><p>{{ mode === "login" ? "使用邮箱和密码进入工作台" : "注册后即可发起合同审查" }}</p></header>
        <el-segmented v-model="mode" :options="modeOptions" class="auth-mode" @change="switchMode" />
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submit">
          <el-form-item label="邮箱" prop="email"><el-input v-model="form.email" autocomplete="email" placeholder="name@company.com" /></el-form-item>
          <el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" show-password :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" placeholder="至少 8 位，包含字母和数字" /></el-form-item>
          <el-form-item label="图片验证码" prop="captcha_code">
            <div class="captcha-row"><el-input v-model="form.captcha_code" maxlength="4" inputmode="numeric" placeholder="4 位数字" /><button type="button" class="captcha-image" title="刷新验证码" @click="loadCaptcha"><img v-if="captcha.image_data" :src="captcha.image_data" alt="数字验证码" /><el-icon v-else class="is-loading"><Loading /></el-icon></button></div>
          </el-form-item>
          <p v-if="errorMessage" class="auth-error">{{ errorMessage }}</p>
          <el-button class="auth-submit" type="primary" :loading="submitting" @click="submit">{{ mode === "login" ? "登录" : "注册并登录" }}</el-button>
        </el-form>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Loading } from "@element-plus/icons-vue";
import type { FormInstance, FormRules } from "element-plus";
import { getCaptcha, login, register } from "@/api/auth";
import { apiErrorMessage } from "@/api/http";
import { useAppStore } from "@/stores/app";

type Mode = "login" | "register";
const mode = ref<Mode>("login");
const modeOptions = [{ label: "登录", value: "login" }, { label: "注册", value: "register" }];
const formRef = ref<FormInstance>();
const form = reactive({ email: "", password: "", captcha_code: "" });
const captcha = reactive({ captcha_id: "", image_data: "" });
const errorMessage = ref("");
const submitting = ref(false);
const router = useRouter();
const route = useRoute();
const appStore = useAppStore();
const rules: FormRules = {
  email: [{ required: true, message: "请输入邮箱", trigger: "blur" }, { type: "email", message: "请输入有效邮箱", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }, { min: 8, message: "密码至少 8 位", trigger: "blur" }],
  captcha_code: [{ required: true, message: "请输入验证码", trigger: "blur" }, { pattern: /^\d{4}$/, message: "请输入 4 位数字", trigger: "blur" }]
};

async function loadCaptcha() {
  captcha.image_data = "";
  try { Object.assign(captcha, await getCaptcha()); form.captcha_code = ""; }
  catch (error) { errorMessage.value = apiErrorMessage(error, "验证码加载失败，请刷新页面。"); }
}
function switchMode() { errorMessage.value = ""; formRef.value?.clearValidate(); loadCaptcha(); }
async function submit() {
  if (!await formRef.value?.validate().catch(() => false) || !captcha.captcha_id) return;
  submitting.value = true; errorMessage.value = "";
  try {
    const action = mode.value === "login" ? login : register;
    const result = await action({ ...form, captcha_id: captcha.captcha_id });
    appStore.setSession(result.access_token, result.user);
    await router.replace(typeof route.query.redirect === "string" ? route.query.redirect : "/contract-review");
  } catch (error) {
    errorMessage.value = apiErrorMessage(error, mode.value === "login" ? "登录失败。" : "注册失败。");
    await loadCaptcha();
  } finally { submitting.value = false; }
}
loadCaptcha();
</script>

<style scoped>
.auth-page{min-height:100vh;display:grid;grid-template-columns:minmax(320px,.85fr) minmax(430px,1.15fr);background:#f4f7f6}.auth-visual{position:relative;display:flex;min-height:100vh;flex-direction:column;justify-content:space-between;padding:38px 46px;background:#173f3b;color:#fff}.auth-visual::after{content:"";position:absolute;inset:0;background:linear-gradient(145deg,transparent 48%,rgba(255,255,255,.06) 48% 49%,transparent 49% 64%,rgba(255,255,255,.04) 64% 65%,transparent 65%);pointer-events:none}.auth-brand{z-index:1;display:flex;align-items:center;gap:12px;font-size:18px}.auth-brand img{width:36px;height:36px}.auth-copy{z-index:1;max-width:480px;margin-bottom:8vh}.auth-copy span{font-size:12px;color:#a7d4ce}.auth-copy h1{margin:14px 0 12px;font-size:38px;letter-spacing:0}.auth-copy p{margin:0;color:#d7e8e5;font-size:16px;line-height:1.7}.auth-form-panel{display:grid;place-items:center;padding:32px}.auth-form-wrap{width:min(430px,100%);border:1px solid var(--line);border-radius:8px;padding:32px;background:#fff;box-shadow:0 14px 36px rgba(23,32,30,.08)}.auth-form-wrap header h2{margin:0;font-size:26px}.auth-form-wrap header p{margin:7px 0 22px;color:var(--muted)}.auth-mode{width:100%;margin-bottom:24px}.captcha-row{width:100%;display:grid;grid-template-columns:1fr 160px;gap:10px}.captcha-image{height:52px;overflow:hidden;border:1px solid #d8e1df;border-radius:5px;padding:0;background:#f4f9f7;cursor:pointer}.captcha-image img{display:block;width:100%;height:100%;object-fit:cover}.auth-error{margin:-4px 0 14px;color:var(--danger);font-size:12px}.auth-submit{width:100%;height:42px}@media(max-width:760px){.auth-page{grid-template-columns:1fr}.auth-visual{min-height:180px;padding:24px}.auth-copy{margin:28px 0 0}.auth-copy h1{font-size:28px}.auth-copy p{font-size:14px}.auth-form-panel{padding:20px 14px}.auth-form-wrap{padding:24px}.captcha-row{grid-template-columns:1fr 140px}}
</style>
