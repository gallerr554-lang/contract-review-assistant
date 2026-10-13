<template>
  <section class="config-page">
    <div class="config-panel">
      <header class="config-page-header">
        <div><h1>模型配置</h1><p>维护审查任务使用的模型 Provider、访问地址和生成参数。</p></div>
        <button class="command-button" type="button" @click="openCreate"><el-icon><Plus /></el-icon>新增模型</button>
      </header>

      <form class="config-toolbar" @submit.prevent="loadModels">
        <el-select v-model="filters.provider" class="filter-select" clearable placeholder="Provider">
          <el-option v-for="option in providerOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <el-select v-model="filters.enabled" class="filter-select" clearable placeholder="状态">
          <el-option label="已启用" value="true" /><el-option label="已停用" value="false" />
        </el-select>
        <div class="config-toolbar-actions"><el-button @click="resetFilters">重置</el-button><el-button type="primary" native-type="submit">查询</el-button></div>
      </form>

      <div class="config-table-wrap model-table-wrap">
        <el-table v-loading="loading" :data="models" empty-text="未查询到符合条件的模型配置">
          <el-table-column label="Provider / 模型" min-width="240">
            <template #default="{ row }"><div class="model-name-cell"><span :class="`provider-badge ${row.provider}`">{{ providerLabel(row.provider) }}</span><div><strong class="item-title">{{ row.model_name }}</strong><small class="item-subtitle">{{ row.api_base || "未配置 API Base" }}</small></div></div></template>
          </el-table-column>
          <el-table-column label="API Key" width="180">
            <template #default="{ row }"><strong class="key-mask">{{ row.api_key_masked }}</strong><small class="item-subtitle">{{ keySourceLabel(row.api_key_source) }}</small></template>
          </el-table-column>
          <el-table-column label="Temperature" width="125"><template #default="{ row }">{{ row.temperature }}</template></el-table-column>
          <el-table-column prop="max_tokens" label="Max Tokens" width="125" />
          <el-table-column label="状态" width="100"><template #default="{ row }"><span :class="row.status ? 'state-tag-on' : 'state-tag-off'">{{ row.status ? "当前使用" : "已停用" }}</span></template></el-table-column>
          <el-table-column label="更新时间" width="178"><template #default="{ row }">{{ formatTime(row.update_time) }}</template></el-table-column>
          <el-table-column label="操作" width="174" fixed="right">
            <template #default="{ row }"><div class="table-actions"><button class="table-icon-button" title="测试连接" type="button" :disabled="testingId === row.id" @click="testConnection(row)"><el-icon :class="{ 'is-loading': testingId === row.id }"><Loading v-if="testingId === row.id" /><Connection v-else /></el-icon></button><button class="table-icon-button" title="编辑模型" type="button" @click="openEdit(row)"><el-icon><Edit /></el-icon></button><el-switch :model-value="row.status" inline-prompt active-text="启" inactive-text="停" @change="(value: string | number | boolean) => toggleStatus(row, Boolean(value))" /></div></template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingModel ? '编辑模型配置' : '新增模型配置'" width="min(720px, 96vw)" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top">
        <div class="dialog-form-grid model-form-grid">
          <el-form-item label="Provider" prop="provider">
            <el-select v-model="form.provider" @change="applyProviderDefaults"><el-option v-for="option in providerOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select>
          </el-form-item>
          <el-form-item label="模型名称" prop="model_name"><el-input v-model="form.model_name" maxlength="120" /></el-form-item>
          <el-form-item class="full-row" label="API Base" prop="api_base"><el-input v-model="form.api_base" maxlength="255" /></el-form-item>
          <el-form-item class="full-row" :label="editingModel ? 'API Key（留空则保持原值）' : 'API Key'" prop="api_key"><el-input v-model="form.api_key" type="password" show-password maxlength="500" autocomplete="new-password" /></el-form-item>
          <el-form-item label="Temperature" prop="temperature"><el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" :precision="1" controls-position="right" /></el-form-item>
          <el-form-item label="Max Tokens" prop="max_tokens"><el-input-number v-model="form.max_tokens" :min="1" :max="128000" :step="512" controls-position="right" /></el-form-item>
          <el-form-item class="full-row" label="是否启用"><el-switch v-model="form.status" active-text="启用" inactive-text="停用" /></el-form-item>
        </div>
      </el-form>
      <template #footer><div class="dialog-footer"><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveModel">保存</el-button></div></template>
    </el-dialog>

    <el-dialog v-model="connectionVisible" title="模型连接测试" width="min(560px, 94vw)" append-to-body>
      <el-descriptions v-if="connectionResult" :column="1" border>
        <el-descriptions-item label="Provider">{{ providerLabel(connectionResult.provider) }}</el-descriptions-item>
        <el-descriptions-item label="模型名称">{{ connectionResult.model_name }}</el-descriptions-item>
        <el-descriptions-item label="接口地址"><span class="connection-base">{{ connectionResult.api_base }}</span></el-descriptions-item>
        <el-descriptions-item label="HTTP 状态">{{ connectionResult.http_status ?? "未建立连接" }}</el-descriptions-item>
        <el-descriptions-item label="测试结果"><el-tag :type="connectionResult.success ? 'success' : 'danger'">{{ connectionResult.success ? "连接成功" : "连接失败" }}</el-tag><span class="connection-message">{{ connectionResult.message }}</span></el-descriptions-item>
      </el-descriptions>
      <template #footer><el-button @click="connectionVisible = false">关闭</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { Connection, Edit, Loading, Plus } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus/es/components/message/index";
import type { FormInstance, FormRules } from "element-plus";

import { apiErrorMessage } from "@/api/http";
import { createModelConfig, listModelConfigs, setModelConfigStatus, testModelConnection, updateModelConfig, type ModelConfig, type ModelConfigPayload, type ModelConnectionResult, type ModelProvider } from "@/api/model";

interface ModelForm extends ModelConfigPayload { api_key: string }
const providerOptions: Array<{ label: string; value: ModelProvider }> = [
  { label: "DeepSeek", value: "deepseek" },
  { label: "OpenAI", value: "openai" },
  { label: "Qwen", value: "qwen" }
];
const providerDefaults: Record<ModelProvider, { model: string; base: string }> = {
  deepseek: { model: "deepseek-chat", base: "https://api.deepseek.com" },
  openai: { model: "gpt-4.1", base: "https://api.openai.com/v1" },
  qwen: { model: "qwen-plus", base: "https://dashscope.aliyuncs.com/compatible-mode/v1" }
};

const filters = reactive({ provider: "", enabled: "" });
const models = ref<ModelConfig[]>([]);
const loading = ref(false);
const saving = ref(false);
const testingId = ref<number>();
const connectionVisible = ref(false);
const connectionResult = ref<ModelConnectionResult>();
const dialogVisible = ref(false);
const editingModel = ref<ModelConfig>();
const formRef = ref<FormInstance>();
const form = reactive<ModelForm>(emptyForm());
const formRules: FormRules<ModelForm> = {
  provider: [{ required: true, message: "请选择 Provider", trigger: "change" }],
  model_name: [{ required: true, message: "请输入模型名称", trigger: "blur" }],
  api_base: [
    { required: true, message: "请输入 API Base", trigger: "blur" },
    { pattern: /^https?:\/\//, message: "API Base 必须以 http:// 或 https:// 开头", trigger: "blur" }
  ],
  api_key: [{ validator: (_rule, value, callback) => { if (!editingModel.value && !String(value || "").trim()) callback(new Error("请输入 API Key")); else callback(); }, trigger: "blur" }],
  temperature: [{ required: true, message: "请输入 Temperature", trigger: "change" }],
  max_tokens: [{ required: true, message: "请输入 Max Tokens", trigger: "change" }]
};

function emptyForm(): ModelForm { return { provider: "deepseek", model_name: providerDefaults.deepseek.model, api_base: providerDefaults.deepseek.base, api_key: "", temperature: 0.2, max_tokens: 4096, status: false }; }
function assignForm(value: ModelForm) { Object.assign(form, value); }
function applyProviderDefaults(provider: ModelProvider) { form.model_name = providerDefaults[provider].model; form.api_base = providerDefaults[provider].base; }

async function loadModels() {
  loading.value = true;
  try { models.value = await listModelConfigs({ provider: filters.provider || undefined, enabled: filters.enabled || undefined }); }
  catch (error) { ElMessage.error(apiErrorMessage(error, "模型配置加载失败。")); }
  finally { loading.value = false; }
}

function resetFilters() { Object.assign(filters, { provider: "", enabled: "" }); loadModels(); }
function openCreate() { editingModel.value = undefined; assignForm(emptyForm()); dialogVisible.value = true; }
function openEdit(model: ModelConfig) { editingModel.value = model; assignForm({ provider: model.provider, model_name: model.model_name, api_base: model.api_base || providerDefaults[model.provider].base, api_key: "", temperature: model.temperature, max_tokens: model.max_tokens, status: model.status }); dialogVisible.value = true; }

async function saveModel() {
  if (!await formRef.value?.validate().catch(() => false)) return;
  saving.value = true;
  try {
    if (editingModel.value) {
      const payload: ModelConfigPayload = { provider: form.provider, model_name: form.model_name, api_base: form.api_base, temperature: form.temperature, max_tokens: form.max_tokens, status: form.status };
      if (form.api_key.trim()) payload.api_key = form.api_key.trim();
      await updateModelConfig(editingModel.value.id, payload);
      ElMessage.success("模型配置已更新");
    } else {
      await createModelConfig({ ...form, api_key: form.api_key.trim() });
      ElMessage.success("模型配置已创建");
    }
    dialogVisible.value = false; await loadModels();
  } catch (error) { ElMessage.error(apiErrorMessage(error, "模型配置保存失败。")); }
  finally { saving.value = false; }
}

async function toggleStatus(model: ModelConfig, enabled: boolean) {
  try { await setModelConfigStatus(model.id, enabled); ElMessage.success(enabled ? "已切换当前使用模型" : "模型已停用"); await loadModels(); }
  catch (error) { ElMessage.error(apiErrorMessage(error, "模型状态更新失败。")); }
}

async function testConnection(model: ModelConfig) {
  if (testingId.value) return;
  testingId.value = model.id;
  try {
    connectionResult.value = await testModelConnection(model.id);
    connectionVisible.value = true;
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "模型连接测试失败。"));
  } finally {
    testingId.value = undefined;
  }
}

function providerLabel(provider: ModelProvider) { return providerOptions.find((item) => item.value === provider)?.label || provider; }
function keySourceLabel(source: ModelConfig["api_key_source"]) { return ({ encrypted: "数据库密文", environment: "环境变量", missing: "不可用" })[source]; }
function formatTime(value: string) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }

loadModels();
</script>

<style scoped>
.model-table-wrap .el-table{min-width:1090px}.model-name-cell{display:flex;align-items:center;gap:12px;min-width:0}.model-name-cell>div{min-width:0}.provider-badge{min-width:74px;display:inline-flex;align-items:center;justify-content:center;border-radius:4px;padding:5px 8px;font-size:11px;font-weight:700}.provider-badge.deepseek{background:#e6f4f1;color:#176c64}.provider-badge.openai{background:#edf1f0;color:#263b36}.provider-badge.qwen{background:#edf0fa;color:#40589a}.key-mask{display:block;color:#34413e;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}.model-form-grid :deep(.el-select),.model-form-grid :deep(.el-input-number){width:100%}.connection-base{overflow-wrap:anywhere}.connection-message{margin-left:10px;color:#52615d}.is-loading{animation:rotate 1s linear infinite}@keyframes rotate{to{transform:rotate(360deg)}}
</style>
