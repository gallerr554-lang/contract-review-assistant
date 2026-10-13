<template>
  <section class="config-page">
    <div class="config-panel">
      <header class="config-page-header">
        <div><h1>审查规则配置</h1><p>统一维护可供审查场景选择的规则、规则类型和风险等级。</p></div>
        <button class="command-button" type="button" @click="openCreate"><el-icon><Plus /></el-icon>新增规则</button>
      </header>

      <form class="config-toolbar" @submit.prevent="loadRules">
        <el-input v-model="filters.keyword" class="search-input" clearable placeholder="搜索规则 ID/名称" :prefix-icon="Search" />
        <el-select v-model="filters.rule_type" class="filter-select" clearable placeholder="规则类型">
          <el-option v-for="type in ruleTypes" :key="type" :label="type" :value="type" />
        </el-select>
        <el-select v-model="filters.risk_level" class="filter-select" clearable placeholder="风险等级">
          <el-option label="高风险" value="high" /><el-option label="中风险" value="medium" /><el-option label="低风险" value="low" />
        </el-select>
        <el-select v-model="filters.enabled" class="filter-select" clearable placeholder="状态">
          <el-option label="已启用" value="true" /><el-option label="已停用" value="false" />
        </el-select>
        <div class="config-toolbar-actions"><el-button @click="resetFilters">重置</el-button><el-button type="primary" native-type="submit">查询</el-button></div>
      </form>

      <div class="config-table-wrap">
        <el-table v-loading="loading" :data="rules" empty-text="未查询到符合条件的审查规则">
          <el-table-column prop="rule_id" label="规则 ID" width="130" />
          <el-table-column label="规则名称" min-width="220">
            <template #default="{ row }"><strong class="item-title">{{ row.rule_name }}</strong><small class="item-subtitle">{{ row.description || "暂无补充说明" }}</small></template>
          </el-table-column>
          <el-table-column prop="business_type" label="业务分类" width="110" />
          <el-table-column prop="rule_type" label="规则类型" width="130" />
          <el-table-column label="风险等级" width="100"><template #default="{ row }"><span :class="`risk-tag-${row.risk_level}`">{{ riskLabel(row.risk_level) }}</span></template></el-table-column>
          <el-table-column label="状态" width="90"><template #default="{ row }"><span :class="row.status ? 'state-tag-on' : 'state-tag-off'">{{ row.status ? "已启用" : "已停用" }}</span></template></el-table-column>
          <el-table-column label="更新时间" width="178"><template #default="{ row }">{{ formatTime(row.update_time) }}</template></el-table-column>
          <el-table-column label="操作" width="168" fixed="right">
            <template #default="{ row }"><div class="table-actions"><button class="table-icon-button" title="编辑规则" type="button" @click="openEdit(row)"><el-icon><Edit /></el-icon></button><el-switch :model-value="row.status" inline-prompt active-text="启" inactive-text="停" @change="(value: string | number | boolean) => toggleStatus(row, Boolean(value))" /><button class="table-icon-button danger" title="删除规则" type="button" @click="confirmDelete(row)"><el-icon><Delete /></el-icon></button></div></template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingRule ? '编辑审查规则' : '新增审查规则'" width="min(860px, 94vw)" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top">
        <div class="dialog-form-grid">
          <el-form-item label="规则 ID"><el-input :model-value="editingRule?.rule_id || ''" disabled placeholder="保存后自动生成" /></el-form-item>
          <el-form-item label="规则名称" prop="rule_name"><el-input v-model="form.rule_name" maxlength="40" show-word-limit /></el-form-item>
          <el-form-item label="业务分类"><el-input model-value="合同审查" disabled /></el-form-item>
          <el-form-item label="规则类型" prop="rule_type"><el-select v-model="form.rule_type"><el-option v-for="type in ruleTypes" :key="type" :label="type" :value="type" /></el-select></el-form-item>
          <el-form-item label="风险等级" prop="risk_level"><el-select v-model="form.risk_level"><el-option label="高风险" value="high" /><el-option label="中风险" value="medium" /><el-option label="低风险" value="low" /></el-select></el-form-item>
          <el-form-item label="是否启用"><el-switch v-model="form.status" active-text="启用" inactive-text="停用" /></el-form-item>
          <el-form-item class="full-row" label="审查要点描述" prop="review_requirement"><el-input v-model="form.review_requirement" type="textarea" :rows="4" maxlength="1000" show-word-limit placeholder="请输入需要重点识别的条款、风险情形和判断要求" /></el-form-item>
          <el-form-item class="full-row" label="规则描述"><el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="补充说明规则的适用范围和判定边界" /></el-form-item>
        </div>
      </el-form>
      <template #footer><div class="dialog-footer"><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveRule">保存</el-button></div></template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { Delete, Edit, Plus, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus/es/components/message/index";
import { ElMessageBox } from "element-plus/es/components/message-box/index";
import type { FormInstance, FormRules } from "element-plus";

import { createRule, deleteRule, listRules, setRuleStatus, updateRule, type ReviewRule, type RiskLevel, type RulePayload, type RuleType } from "@/api/configuration";
import { apiErrorMessage } from "@/api/http";

const ruleTypes: RuleType[] = ["AI语义审查", "条款完整性", "合规校验", "金额与支付"];
const filters = reactive({ keyword: "", rule_type: "", risk_level: "", enabled: "" });
const rules = ref<ReviewRule[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const editingRule = ref<ReviewRule>();
const formRef = ref<FormInstance>();
const form = reactive<RulePayload>(emptyForm());
const formRules: FormRules<RulePayload> = {
  rule_name: [{ required: true, message: "请输入规则名称", trigger: "blur" }],
  rule_type: [{ required: true, message: "请选择规则类型", trigger: "change" }],
  risk_level: [{ required: true, message: "请选择风险等级", trigger: "change" }],
  review_requirement: [{ required: true, message: "请输入审查要点描述", trigger: "blur" }]
};

function emptyForm(): RulePayload { return { rule_name: "", business_type: "合同审查", rule_type: "AI语义审查", risk_level: "medium", review_requirement: "", description: null, status: true }; }
function assignForm(value: RulePayload) { Object.assign(form, value); }

async function loadRules() {
  loading.value = true;
  try { rules.value = await listRules({ keyword: filters.keyword || undefined, rule_type: filters.rule_type || undefined, risk_level: filters.risk_level || undefined, enabled: filters.enabled || undefined }); }
  catch (error) { ElMessage.error(apiErrorMessage(error, "审查规则加载失败。")); }
  finally { loading.value = false; }
}

function resetFilters() { Object.assign(filters, { keyword: "", rule_type: "", risk_level: "", enabled: "" }); loadRules(); }
function openCreate() { editingRule.value = undefined; assignForm(emptyForm()); dialogVisible.value = true; }
function openEdit(rule: ReviewRule) { editingRule.value = rule; assignForm({ rule_name: rule.rule_name, business_type: "合同审查", rule_type: rule.rule_type, risk_level: rule.risk_level, review_requirement: rule.review_requirement, description: rule.description, status: rule.status }); dialogVisible.value = true; }

async function saveRule() {
  if (!await formRef.value?.validate().catch(() => false)) return;
  saving.value = true;
  try {
    if (editingRule.value) await updateRule(editingRule.value.id, { ...form }); else await createRule({ ...form });
    ElMessage.success(editingRule.value ? "审查规则已更新" : "审查规则已创建"); dialogVisible.value = false; await loadRules();
  } catch (error) { ElMessage.error(apiErrorMessage(error, "审查规则保存失败。")); }
  finally { saving.value = false; }
}

async function toggleStatus(rule: ReviewRule, enabled: boolean) {
  try { await setRuleStatus(rule.id, enabled); rule.status = enabled; ElMessage.success(enabled ? "规则已启用" : "规则已停用"); }
  catch (error) { ElMessage.error(apiErrorMessage(error, "规则状态更新失败。")); }
}

async function confirmDelete(rule: ReviewRule) {
  try {
    await ElMessageBox.confirm(`确认删除审查规则“${rule.rule_name}”吗？关联场景中的该规则也将移除。`, "删除审查规则", { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" });
    await deleteRule(rule.id); ElMessage.success("审查规则已删除"); await loadRules();
  } catch (error) { if (error !== "cancel" && error !== "close") ElMessage.error(apiErrorMessage(error, "审查规则删除失败。")); }
}

function riskLabel(level: RiskLevel) { return ({ high: "高风险", medium: "中风险", low: "低风险" })[level]; }
function formatTime(value: string) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
onMounted(loadRules);
</script>

<style scoped>
:deep(.el-dialog__body){padding-top:14px}:deep(.el-select){width:100%}
</style>
