<template>
  <section class="config-page">
    <div class="config-panel">
      <header class="config-page-header">
        <div><h1>审查场景配置</h1><p>维护场景说明、关联审查规则、System Prompt 和启用状态。</p></div>
        <button class="command-button" type="button" @click="openCreate"><el-icon><Plus /></el-icon>新增场景</button>
      </header>

      <form class="config-toolbar" @submit.prevent="loadScenes">
        <el-input v-model="filters.keyword" class="search-input" clearable placeholder="搜索审查场景名称" :prefix-icon="Search" />
        <el-select v-model="filters.enabled" class="filter-select" clearable placeholder="状态"><el-option label="已启用" value="true" /><el-option label="已停用" value="false" /></el-select>
        <div class="config-toolbar-actions"><el-button @click="resetFilters">重置</el-button><el-button type="primary" native-type="submit">查询</el-button></div>
      </form>

      <div class="config-table-wrap">
        <el-table v-loading="loading" :data="scenes" empty-text="未查询到符合条件的审查场景">
          <el-table-column type="index" label="序号" width="74" />
          <el-table-column label="场景名称" min-width="260"><template #default="{ row }"><strong class="item-title">{{ row.scene_name }}</strong><small class="item-subtitle">{{ row.description || "暂无场景说明" }}</small></template></el-table-column>
          <el-table-column prop="business_type" label="业务分类" width="110" />
          <el-table-column label="审查规则" width="150"><template #default="{ row }"><span class="rule-count">{{ row.rule_count }} 条</span><small v-if="row.active_rule_count !== row.rule_count" class="inactive-count">有效 {{ row.active_rule_count }} 条</small></template></el-table-column>
          <el-table-column label="状态" width="100"><template #default="{ row }"><span :class="row.status ? 'state-tag-on' : 'state-tag-off'">{{ row.status ? "已启用" : "已停用" }}</span></template></el-table-column>
          <el-table-column label="更新时间" width="178"><template #default="{ row }">{{ formatTime(row.update_time) }}</template></el-table-column>
          <el-table-column label="操作" width="168" fixed="right"><template #default="{ row }"><div class="table-actions"><button class="table-icon-button" title="编辑场景" type="button" @click="openEdit(row)"><el-icon><Edit /></el-icon></button><el-switch :model-value="row.status" inline-prompt active-text="启" inactive-text="停" @change="(value: string | number | boolean) => toggleStatus(row, Boolean(value))" /><button class="table-icon-button danger" title="删除场景" type="button" @click="confirmDelete(row)"><el-icon><Delete /></el-icon></button></div></template></el-table-column>
        </el-table>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingScene ? '编辑审查场景' : '新增审查场景'" width="min(1080px, 96vw)" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top">
        <div class="scene-basic-grid">
          <el-form-item label="场景名称" prop="scene_name"><el-input v-model="form.scene_name" maxlength="40" show-word-limit /></el-form-item>
          <el-form-item label="业务分类"><el-input model-value="合同审查" disabled /></el-form-item>
          <el-form-item label="是否启用"><el-switch v-model="form.status" active-text="启用" inactive-text="停用" /></el-form-item>
          <el-form-item class="full-row" label="场景说明"><el-input v-model="form.description" type="textarea" :rows="2" maxlength="200" show-word-limit /></el-form-item>
        </div>

        <el-form-item label="审查规则" prop="rule_ids">
          <div class="rule-selection">
            <div class="rule-selection-head"><span>通过勾选关联规则</span><el-input v-model="ruleSearch" clearable placeholder="搜索规则名称或类型" :prefix-icon="Search" /></div>
            <div class="rule-picker">
              <section class="rule-picker-pane">
                <header><strong>已选规则（{{ form.rule_ids.length }} 条）</strong></header>
                <div class="rule-picker-columns"><span></span><span>规则名称</span><span>规则类型</span><span>风险等级</span></div>
                <div class="rule-picker-list">
                  <label v-for="rule in selectedRules" :key="rule.id" class="rule-picker-row"><el-checkbox :model-value="true" @change="removeRule(rule.id)" /><strong :title="rule.rule_name">{{ rule.rule_name }}</strong><span>{{ rule.rule_type }}</span><em :class="`risk-tag-${rule.risk_level}`">{{ riskLabel(rule.risk_level) }}</em></label>
                  <p v-if="!selectedRules.length" class="rule-picker-empty">暂无已选规则</p>
                </div>
              </section>
              <section class="rule-picker-pane">
                <header><strong>可选规则（{{ availableRules.length }} 条）</strong></header>
                <div class="rule-picker-columns"><span></span><span>规则名称</span><span>规则类型</span><span>风险等级</span></div>
                <div class="rule-picker-list">
                  <label v-for="rule in availableRules" :key="rule.id" class="rule-picker-row" :class="{ disabled: !rule.status }"><el-checkbox :model-value="false" @change="addRule(rule.id)" /><strong :title="rule.rule_name">{{ rule.rule_name }}</strong><span>{{ rule.rule_type }}</span><em :class="`risk-tag-${rule.risk_level}`">{{ riskLabel(rule.risk_level) }}</em></label>
                  <p v-if="!availableRules.length" class="rule-picker-empty">暂无可选规则</p>
                </div>
              </section>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="System Prompt" prop="system_prompt"><el-input v-model="form.system_prompt" type="textarea" :rows="4" maxlength="4000" show-word-limit placeholder="描述该场景的角色、目标、审查侧重点和输出约束" /></el-form-item>
        <el-form-item class="order-field" label="展示顺序" prop="display_order"><el-input-number v-model="form.display_order" :min="1" :max="99" controls-position="right" /></el-form-item>
      </el-form>
      <template #footer><div class="dialog-footer"><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveScene">保存</el-button></div></template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Delete, Edit, Plus, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus/es/components/message/index";
import { ElMessageBox } from "element-plus/es/components/message-box/index";
import type { FormInstance, FormRules } from "element-plus";

import { createScene, deleteScene, listRules, listScenes, setSceneStatus, updateScene, type ReviewRule, type ReviewScene, type RiskLevel, type ScenePayload } from "@/api/configuration";
import { apiErrorMessage } from "@/api/http";

type SceneForm = Omit<ScenePayload, "description"> & { description: string };
const filters = reactive({ keyword: "", enabled: "" });
const scenes = ref<ReviewScene[]>([]);
const rules = ref<ReviewRule[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const editingScene = ref<ReviewScene>();
const ruleSearch = ref("");
const formRef = ref<FormInstance>();
const form = reactive<SceneForm>(emptyForm());
const formRules: FormRules<SceneForm> = {
  scene_name: [{ required: true, message: "请输入场景名称", trigger: "blur" }],
  rule_ids: [{ type: "array", required: true, min: 1, message: "请至少关联 1 条审查规则", trigger: "change" }],
  system_prompt: [{ required: true, message: "请输入 System Prompt", trigger: "blur" }],
  display_order: [{ required: true, message: "请输入展示顺序", trigger: "change" }]
};

const normalizedSearch = computed(() => ruleSearch.value.trim().toLowerCase());
const selectedRules = computed(() => rules.value.filter((rule) => form.rule_ids.includes(rule.id) && matchesSearch(rule)));
const availableRules = computed(() => rules.value.filter((rule) => !form.rule_ids.includes(rule.id) && matchesSearch(rule)));

function emptyForm(): SceneForm { return { scene_name: "", business_type: "合同审查", description: "", system_prompt: "", rule_ids: [], status: true, display_order: 1 }; }
function matchesSearch(rule: ReviewRule) { return !normalizedSearch.value || `${rule.rule_id} ${rule.rule_name} ${rule.rule_type}`.toLowerCase().includes(normalizedSearch.value); }
function assignForm(value: SceneForm) { Object.assign(form, value); form.rule_ids = [...value.rule_ids]; }

async function loadScenes() {
  loading.value = true;
  try { scenes.value = await listScenes({ keyword: filters.keyword || undefined, enabled: filters.enabled || undefined }); }
  catch (error) { ElMessage.error(apiErrorMessage(error, "审查场景加载失败。")); }
  finally { loading.value = false; }
}

async function loadAllRules() {
  try { rules.value = await listRules(); }
  catch (error) { ElMessage.error(apiErrorMessage(error, "审查规则加载失败。")); }
}

function resetFilters() { Object.assign(filters, { keyword: "", enabled: "" }); loadScenes(); }
async function openCreate() { editingScene.value = undefined; assignForm(emptyForm()); ruleSearch.value = ""; dialogVisible.value = true; if (!rules.value.length) await loadAllRules(); }
async function openEdit(scene: ReviewScene) { editingScene.value = scene; assignForm({ scene_name: scene.scene_name, business_type: "合同审查", description: scene.description || "", system_prompt: scene.system_prompt, rule_ids: scene.rules.map((rule) => rule.id), status: scene.status, display_order: scene.display_order }); ruleSearch.value = ""; dialogVisible.value = true; await loadAllRules(); }
function addRule(id: number) { if (!form.rule_ids.includes(id)) form.rule_ids.push(id); formRef.value?.validateField("rule_ids"); }
function removeRule(id: number) { form.rule_ids = form.rule_ids.filter((ruleId) => ruleId !== id); formRef.value?.validateField("rule_ids"); }

async function saveScene() {
  if (!await formRef.value?.validate().catch(() => false)) return;
  saving.value = true;
  const payload: ScenePayload = { ...form, description: form.description.trim() || null, rule_ids: [...form.rule_ids] };
  try {
    if (editingScene.value) await updateScene(editingScene.value.id, payload); else await createScene(payload);
    ElMessage.success(editingScene.value ? "审查场景已更新" : "审查场景已创建"); dialogVisible.value = false; await loadScenes();
  } catch (error) { ElMessage.error(apiErrorMessage(error, "审查场景保存失败。")); }
  finally { saving.value = false; }
}

async function toggleStatus(scene: ReviewScene, enabled: boolean) {
  try { await setSceneStatus(scene.id, enabled); scene.status = enabled; ElMessage.success(enabled ? "场景已启用" : "场景已停用"); }
  catch (error) { ElMessage.error(apiErrorMessage(error, "场景状态更新失败。")); }
}

async function confirmDelete(scene: ReviewScene) {
  try {
    await ElMessageBox.confirm(`确认删除审查场景“${scene.scene_name}”吗？已有任务将继续使用保存的配置快照。`, "删除审查场景", { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" });
    await deleteScene(scene.id); ElMessage.success("审查场景已删除"); await loadScenes();
  } catch (error) { if (error !== "cancel" && error !== "close") ElMessage.error(apiErrorMessage(error, "审查场景删除失败。")); }
}

function riskLabel(level: RiskLevel) { return ({ high: "高风险", medium: "中风险", low: "低风险" })[level]; }
function formatTime(value: string) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
onMounted(() => { loadScenes(); loadAllRules(); });
</script>

<style scoped>
.rule-count{display:inline-flex;min-height:24px;align-items:center;border-radius:4px;padding:0 8px;background:#eaf4f2;color:var(--primary-dark);font-size:12px;font-weight:600}.inactive-count{display:block;margin-top:3px;color:#9a5a08}.scene-basic-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 16px}.scene-basic-grid .full-row{grid-column:1/-1}.rule-selection{width:100%}.rule-selection-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:10px;color:var(--muted);font-size:12px}.rule-selection-head .el-input{width:min(320px,48%)}.rule-picker{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.rule-picker-pane{min-width:0;overflow:hidden;border:1px solid #dfe7e5;border-radius:7px;background:#fff}.rule-picker-pane>header{min-height:46px;display:flex;align-items:center;padding:0 12px;border-bottom:1px solid #e8edec;background:#fbfcfc}.rule-picker-columns,.rule-picker-row{display:grid;grid-template-columns:24px minmax(0,1fr) 102px 76px;align-items:center;gap:8px}.rule-picker-columns{min-height:36px;padding:0 12px;border-bottom:1px solid #e8edec;background:#f8faf9;color:#73807d;font-size:11px}.rule-picker-list{min-height:210px;max-height:270px;overflow:auto;padding:0 12px}.rule-picker-row{min-height:50px;border-bottom:1px solid #edf1f0;color:#53615e;font-size:12px;cursor:pointer}.rule-picker-row:last-child{border-bottom:0}.rule-picker-row strong{overflow:hidden;color:#2f3d39;text-overflow:ellipsis;white-space:nowrap}.rule-picker-row em{justify-self:start;font-style:normal;white-space:nowrap}.rule-picker-row.disabled{opacity:.58}.rule-picker-empty{margin:0;padding:70px 12px;color:#8b9794;text-align:center}.order-field{width:220px}:deep(.el-dialog__body){padding-top:14px}:deep(.el-input-number){width:100%}
@media(max-width:900px){.scene-basic-grid,.rule-picker{grid-template-columns:1fr}.scene-basic-grid .full-row{grid-column:auto}.rule-selection-head{align-items:stretch;flex-direction:column}.rule-selection-head .el-input{width:100%}}
</style>
