<template>
  <section class="page review-page">
    <header class="page-heading"><h1>合同审查</h1></header>

    <section class="launch-workspace" aria-label="合同审查任务工作区">
      <form v-if="!task" class="launch-form" @submit.prevent="startReview">
        <div class="section-kicker">TASK SETUP</div>
        <h2 class="section-title">发起审查任务</h2>
        <p class="section-description">合同主文件为必填，附件可补充技术规范、报价清单等审查依据。</p>
        <div class="upload-grid">
          <label class="upload-box" :class="{ dragging: draggingZone === 'main', selected: mainFile }" @dragenter.prevent="draggingZone = 'main'" @dragover.prevent @dragleave.prevent="draggingZone = null" @drop.prevent="handleDrop($event, 'main')">
            <input ref="mainInput" type="file" accept=".doc,.docx,.pdf,.txt" @change="selectMainFile" />
            <span class="upload-icon"><el-icon><UploadFilled /></el-icon></span><strong>上传合同主文件 <span class="required">*</span></strong><small>支持 DOC、DOCX、PDF、TXT，单文件不超过 20 MB</small><span class="file-name"><b v-if="mainFile" class="file-type">{{ fileExtension(mainFile) }}</b>{{ mainFile?.name || "未选择文件" }}</span>
          </label>
          <label class="upload-box" :class="{ dragging: draggingZone === 'attachments', selected: attachments.length }" @dragenter.prevent="draggingZone = 'attachments'" @dragover.prevent @dragleave.prevent="draggingZone = null" @drop.prevent="handleDrop($event, 'attachments')">
            <input ref="attachmentInput" type="file" accept=".doc,.docx,.pdf,.txt" multiple @change="selectAttachments" />
            <span class="upload-icon"><el-icon><Files /></el-icon></span><strong>补充附件</strong><small>最多 3 份</small><span class="file-name">{{ attachmentLabel }}</span>
          </label>
        </div>
        <div class="form-grid">
          <label class="field"><span class="field-label">审查场景 <span class="required">*</span></span><select v-model.number="form.sceneId" :disabled="loadingScenes || !scenes.length"><option v-if="loadingScenes" :value="undefined">正在加载场景</option><option v-else-if="!scenes.length" :value="undefined">暂无可用场景</option><option v-for="scene in scenes" :key="scene.id" :value="scene.id">{{ scene.scene_name }}</option></select></label>
          <label class="field"><span class="field-label">审查尺度 <span class="required">*</span></span><select v-model="form.scale"><option value="宽松">宽松 · 聚焦重大风险</option><option value="标准">标准 · 平衡风险与效率</option><option value="严格">严格 · 全面识别风险</option></select></label>
          <div class="field"><span class="field-label">审查立场 <span class="required">*</span></span><div class="position-switch"><label><input v-model="form.position" type="radio" value="甲方" /><span>甲方立场</span></label><label><input v-model="form.position" type="radio" value="乙方" /><span>乙方立场</span></label></div></div>
        </div>
        <footer class="form-footer"><p class="form-tip" role="alert">{{ errorMessage }}</p><button class="primary-btn" type="submit" :disabled="submitting || loadingScenes || !scenes.length"><el-icon v-if="submitting" class="is-loading"><Loading /></el-icon>{{ submitting ? submitLabel : "开始审查" }}</button></footer>
      </form>

      <section v-else class="task-panel" aria-live="polite">
        <div class="section-kicker">TASK STATUS</div><h2 class="section-title">任务执行进度</h2><p class="section-description">解析、规则加载与风险生成状态将在此实时更新。</p>
        <div class="task-content">
          <div class="task-summary"><div><h3>{{ task.contract_name }}</h3><div class="task-facts"><span>{{ task.task_no }}</span><span>{{ task.scene_name }}</span><span>{{ task.scale }}尺度</span><span>{{ task.position }}立场</span></div></div><span class="status-badge" :class="statusClass">{{ statusLabel }}</span></div>
          <div class="progress-track"><div class="progress-bar" :style="{ width: `${task.progress}%` }" /></div><div class="progress-meta"><span>{{ task.current_message }}</span><strong>{{ task.progress }}%</strong></div>
          <div class="step-list"><div v-for="(name, index) in processSteps" :key="name" class="step" :class="stepState(index)"><span class="step-dot"><el-icon v-if="stepState(index) === 'complete'"><Check /></el-icon><span v-else>{{ stepState(index) === "failed" ? "!" : index + 1 }}</span></span><p>{{ name }}</p><span>{{ stepStatus(index) }}</span></div></div>
          <p v-if="task.error_message" class="task-error">{{ task.error_message }}</p><p v-if="pollError" class="task-error">{{ pollError }}</p>
          <div v-if="task.status !== 'PROCESSING'" class="task-actions"><button class="secondary-btn" type="button" @click="newReview"><el-icon><Plus /></el-icon>发起新审查</button><button v-if="task.status === 'FAILED'" class="secondary-btn" type="button" :disabled="retrying" @click="retry"><el-icon><Refresh /></el-icon>重新审查</button><button v-if="task.status === 'SUCCESS'" class="primary-btn" type="button" @click="openResult(task.id)"><el-icon><View /></el-icon>查看审查结果</button></div>
        </div>
      </section>
    </section>

    <section class="history-panel" aria-labelledby="history-title">
      <header class="history-head"><div><h2 id="history-title">审查记录</h2><p>查看当前及历史任务，已完成任务可直接打开审查结果。</p></div><button class="icon-btn" type="button" title="刷新记录" aria-label="刷新审查记录" @click="loadHistory()"><el-icon :class="{ 'is-loading': historyLoading }"><Refresh /></el-icon></button></header>
      <form class="history-toolbar" @submit.prevent="loadHistory(true)"><el-input v-model="historyFilters.keyword" clearable placeholder="搜索合同名称或任务编号" :prefix-icon="Search" /><el-select v-model="historyFilters.status" clearable placeholder="任务状态"><el-option label="已完成" value="SUCCESS" /><el-option label="处理中" value="PROCESSING" /><el-option label="失败" value="FAILED" /></el-select><div class="history-toolbar-actions"><el-button @click="resetHistoryFilters">重置</el-button><el-button type="primary" native-type="submit">查询</el-button></div></form>
      <div class="history-table-wrap" v-loading="historyLoading">
        <table><thead><tr><th>合同 / 任务编号</th><th>审查场景</th><th>审查尺度</th><th>审查立场</th><th>风险概览</th><th>状态</th><th>发起时间</th><th>操作</th></tr></thead><tbody>
          <tr v-for="item in history.items" :key="item.id"><td class="contract-cell"><strong>{{ item.contract_name }}</strong><small>{{ item.task_no }}</small></td><td>{{ item.scene_name }}</td><td>{{ item.scale }}</td><td>{{ item.position }}</td><td>{{ item.status === "SUCCESS" ? `${item.risk_total} 项（高 ${item.high_risk_count}）` : "—" }}</td><td><span class="history-status" :class="historyStatusClass(item.status)">{{ historyStatusLabel(item.status) }}</span><el-tooltip v-if="item.status === 'FAILED' && item.error_message" :content="item.error_message" placement="top"><el-icon class="failure-info"><WarningFilled /></el-icon></el-tooltip></td><td>{{ formatTime(item.create_time) }}</td><td><button v-if="item.status === 'SUCCESS'" class="text-command" type="button" @click="openResult(item.id)">查看结果</button><span v-else class="unavailable-action">—</span></td></tr>
          <tr v-if="!history.items.length"><td class="empty-history" colspan="8">未查询到符合条件的审查记录</td></tr>
        </tbody></table>
      </div>
      <footer v-if="history.total > history.page_size" class="history-pagination"><el-pagination v-model:current-page="history.page" :page-size="history.page_size" :total="history.total" layout="prev, pager, next" @current-change="loadHistory" /></footer>
    </section>

    <Teleport to="body">
      <div v-if="resultVisible" class="modal-layer" @click.self="closeResult">
        <section class="result-modal" role="dialog" aria-modal="true" aria-labelledby="result-title">
          <header class="modal-head"><div><h2 id="result-title">合同审查结果</h2><p>{{ resultMeta }}</p></div><div class="modal-actions"><button class="secondary-btn" type="button" :disabled="!result || downloadLoading" @click="downloadResult('original')"><el-icon :class="{ 'is-loading': downloadLoading }"><Loading v-if="downloadLoading" /><Download v-else /></el-icon>下载带标记版 {{ defaultDownloadExtension.toUpperCase() }}</button><button v-if="defaultDownloadExtension === 'docx'" class="secondary-btn pdf-export-button" type="button" :disabled="downloadLoading" @click="downloadResult('pdf')">导出 PDF</button><button class="icon-btn" type="button" title="关闭" aria-label="关闭审查结果" @click="closeResult"><el-icon><Close /></el-icon></button></div></header>
          <template v-if="result">
            <div class="result-overview">
              <button class="risk-stat" :class="{ active: riskFilter === 'all' }" type="button" @click="setRiskFilter('all')"><span>风险总数</span><strong>{{ result.statistics.total }}</strong></button>
              <button class="risk-stat high" :class="{ active: riskFilter === 'high' }" type="button" @click="setRiskFilter('high')"><span>高风险</span><strong>{{ result.statistics.high }}</strong></button>
              <button class="risk-stat medium" :class="{ active: riskFilter === 'medium' }" type="button" @click="setRiskFilter('medium')"><span>中风险</span><strong>{{ result.statistics.medium }}</strong></button>
              <button class="risk-stat low" :class="{ active: riskFilter === 'low' }" type="button" @click="setRiskFilter('low')"><span>低风险</span><strong>{{ result.statistics.low }}</strong></button>
              <p class="result-summary">{{ result.summary }}</p>
            </div>
            <div class="result-body">
              <section ref="documentPaneRef" class="document-pane">
                <div class="pane-title document-pane-title"><div><h3>合同原文</h3><span>{{ currentDocumentMeta?.file_name }} · {{ currentDocumentMeta?.file_extension.toUpperCase() }}</span></div><el-segmented v-if="currentDocumentMeta?.preview_available" v-model="documentMode" :options="documentModeOptions" size="small" @change="changeDocumentMode" /></div>
                <el-tabs v-if="result.documents.length > 1" v-model="currentFileId" class="material-tabs" @tab-change="changeDocument"><el-tab-pane v-for="(material, index) in result.documents" :key="material.file_id" :name="material.file_id" :label="index === 0 ? '主合同' : `附件 ${index}`" /></el-tabs>
                <div v-if="currentDocumentMeta?.ocr_message" class="ocr-notice" :class="currentDocumentMeta.ocr_status"><el-icon><WarningFilled /></el-icon><span>{{ currentDocumentMeta.ocr_message }}</span></div>
                <div class="document-page-toolbar"><el-button :disabled="currentPage <= 1 || pageLoading" @click="changePage(currentPage - 1)">上一页</el-button><strong>第 {{ currentPage }} / {{ currentDocumentMeta?.page_count || 1 }} 页</strong><el-button :disabled="currentPage >= (currentDocumentMeta?.page_count || 1) || pageLoading" @click="changePage(currentPage + 1)">下一页</el-button></div>
                <div v-loading="pageLoading" class="document-page-stage">
                  <article v-if="documentMode === 'layout' && previewUrl" class="document-preview"><img :src="previewUrl" :alt="`${currentDocumentMeta?.file_name || '合同'}第 ${currentPage} 页版式预览`" /></article>
                  <article v-else-if="currentDocumentPage" class="contract-paper paged-paper">
                    <h3>{{ currentDocumentTitle }}</h3>
                    <div class="document-source"><span>{{ pageSourceLabel }}</span><span>第 {{ currentPage }} 页</span></div>
                    <div class="contract-blocks">
                      <template v-for="block in renderedBlocks" :key="block.blockId">
                        <table v-if="block.type === 'table'" class="contract-table" :data-block-id="block.blockId"><tbody><tr v-for="(row, rowIndex) in block.rows" :key="rowIndex"><td v-for="(cell, cellIndex) in row" :key="cellIndex"><template v-for="(segment, segmentIndex) in cell" :key="segmentIndex"><mark v-if="segment.riskIds?.length" :data-risk-ids="segment.riskIds.join(' ')" :title="markTitle(segment.riskIds)" :class="[segment.level, { active: activeRiskId && segment.riskIds.includes(activeRiskId), muted: !segment.riskIds.some(riskVisible) }]" role="button" tabindex="0" @click="focusRiskGroup(segment.riskIds)" @keydown.enter="focusRiskGroup(segment.riskIds)" @keydown.space.prevent="focusRiskGroup(segment.riskIds)">{{ segment.text }}<sup v-if="segment.riskIds.length > 1" class="mark-count">{{ segment.riskIds.length }}</sup></mark><template v-else>{{ segment.text }}</template></template></td></tr></tbody></table>
                        <p v-else class="contract-paragraph" :data-block-id="block.blockId" :class="{ heading: block.heading }"><template v-for="(segment, segmentIndex) in block.segments" :key="segmentIndex"><mark v-if="segment.riskIds?.length" :data-risk-ids="segment.riskIds.join(' ')" :title="markTitle(segment.riskIds)" :class="[segment.level, { active: activeRiskId && segment.riskIds.includes(activeRiskId), muted: !segment.riskIds.some(riskVisible) }]" role="button" tabindex="0" @click="focusRiskGroup(segment.riskIds)" @keydown.enter="focusRiskGroup(segment.riskIds)" @keydown.space.prevent="focusRiskGroup(segment.riskIds)">{{ segment.text }}<sup v-if="segment.riskIds.length > 1" class="mark-count">{{ segment.riskIds.length }}</sup></mark><template v-else>{{ segment.text }}</template></template></p>
                      </template>
                    </div>
                  </article>
                  <div v-else class="result-loading"><el-icon class="is-loading"><Loading /></el-icon>正在加载第 {{ currentPage }} 页</div>
                </div>
                <div class="page-risk-links"><span>本页风险</span><button v-for="risk in currentPageRisks" :key="risk.id" type="button" @click="focusRisk(risk.id)">{{ risk.risk_name }}</button><small v-if="!currentPageRisks.length">本页无可定位风险</small></div>
              </section>
              <section ref="riskPaneRef" class="risk-pane"><div class="pane-title"><h3>重点风险</h3><span>显示 {{ filteredRisks.length }} / {{ result.statistics.total }} 项</span></div>
                <div v-if="filteredRisks.length" class="risk-list"><article v-for="risk in filteredRisks" :id="`risk-card-${risk.id}`" :key="risk.id" class="risk-card" :class="[risk.risk_level, { active: activeRiskId === risk.id }]">
                  <button class="risk-card-head" type="button" :aria-expanded="expandedRiskIds.has(risk.id)" @click="toggleRisk(risk)"><div><h4>{{ risk.risk_name }}</h4><p class="rule-ref">{{ risk.rule_id }} · {{ risk.rule_name }}</p></div><span class="risk-level-wrap"><span class="risk-level" :class="risk.risk_level">{{ levelLabel(risk.risk_level) }}</span><el-icon><ArrowUp v-if="expandedRiskIds.has(risk.id)" /><ArrowDown v-else /></el-icon></span></button>
                  <div v-if="expandedRiskIds.has(risk.id)" class="risk-card-detail"><dl><dt>风险原文</dt><dd>{{ risk.original_text || "未提供可定位原文" }}</dd><dt>来源</dt><dd>{{ risk.source || "需人工核验" }}<span v-if="!risk.locatable" class="manual-tag">需人工核验</span></dd><dt>风险说明</dt><dd>{{ risk.description }}</dd><dt>修改建议</dt><dd>{{ risk.suggestion }}</dd></dl><footer><button class="text-command feedback-button" type="button" :disabled="risk.feedback_submitted" @click="openFeedback(risk)">{{ risk.feedback_submitted ? "已反馈" : "反馈有误" }}</button></footer></div>
                </article></div>
                <div v-else class="empty-result"><el-icon><CircleCheckFilled /></el-icon><strong>{{ result.risks.length ? "当前等级暂无风险" : "未识别到明显风险" }}</strong><p>仍建议结合交易背景和业务要求进行人工复核。</p></div>
              </section>
            </div>
          </template>
          <div v-else class="result-loading"><el-icon class="is-loading"><Loading /></el-icon>正在加载审查结果</div>
        </section>
      </div>
    </Teleport>

    <el-dialog v-model="feedbackVisible" title="反馈审查问题" width="min(520px, 94vw)" destroy-on-close append-to-body>
      <el-form label-position="top" @submit.prevent><el-form-item label="风险项"><el-input :model-value="feedbackRisk?.risk_name" disabled /></el-form-item><el-form-item label="反馈原因" required><el-input v-model="feedbackContent" type="textarea" :rows="5" maxlength="500" show-word-limit placeholder="请说明规则不适用、原文匹配或风险判断等问题" /><p v-if="feedbackError" class="feedback-error">{{ feedbackError }}</p></el-form-item></el-form>
      <template #footer><div class="dialog-footer"><el-button @click="feedbackVisible = false">取消</el-button><el-button type="primary" :loading="feedbackSubmitting" @click="submitFeedback">提交反馈</el-button></div></template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ArrowDown, ArrowUp, Check, CircleCheckFilled, Close, Download, Files, Loading, Plus, Refresh, Search, UploadFilled, View, WarningFilled } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus/es/components/message/index";

import { apiErrorMessage, createReview, downloadMarkedDocument, getDocumentPage, getDocumentPageImage, getReviewResult, getReviewStatus, listReviewHistory, retryReview, submitRiskFeedback, uploadContract, type DocumentPage, type ReviewHistoryItem, type ReviewHistoryResponse, type ReviewResult, type ReviewRisk, type ReviewStatus, type ReviewTask } from "@/api/review";
import { listAvailableScenes, type AvailableScene } from "@/api/configuration";
import { generateUuid } from "@/utils/uuid";

const processSteps = ["解析合同及附件", "读取场景与审查规则", "执行合同风险识别", "合并并校验风险", "生成审查结果"];
const allowedExtensions = ["doc", "docx", "pdf", "txt"];
const form = reactive<{ sceneId?: number; scale: string; position: string }>({ sceneId: undefined, scale: "标准", position: "甲方" });
const scenes = ref<AvailableScene[]>([]);
const loadingScenes = ref(true);
const mainInput = ref<HTMLInputElement>();
const attachmentInput = ref<HTMLInputElement>();
const mainFile = ref<File>();
const attachments = ref<File[]>([]);
const draggingZone = ref<"main" | "attachments" | null>(null);
const submitting = ref(false);
const submitLabel = ref("正在上传材料");
const errorMessage = ref("");
const pollError = ref("");
const task = ref<ReviewTask>();
const result = ref<ReviewResult>();
const resultVisible = ref(false);
const retrying = ref(false);
const historyFilters = reactive<{ keyword: string; status: "" | ReviewStatus }>({ keyword: "", status: "" });
const history = ref<ReviewHistoryResponse>({ items: [], total: 0, page: 1, page_size: 10 });
const historyLoading = ref(false);
const riskFilter = ref<"all" | ReviewRisk["risk_level"]>("all");
const activeRiskId = ref<number>();
const expandedRiskIds = ref(new Set<number>());
const feedbackVisible = ref(false);
const feedbackRisk = ref<ReviewRisk>();
const feedbackContent = ref("");
const feedbackError = ref("");
const feedbackSubmitting = ref(false);
const downloadLoading = ref(false);
const currentPage = ref(1);
const currentFileId = ref("main");
const currentDocumentPage = ref<DocumentPage>();
const pageLoading = ref(false);
const documentMode = ref<"layout" | "text">("text");
const documentModeOptions = [{ label: "版式", value: "layout" }, { label: "风险文本", value: "text" }];
const pageCache = new Map<string, DocumentPage>();
const previewCache = new Map<string, string>();
const previewUrl = ref("");
const documentPaneRef = ref<HTMLElement>();
const riskPaneRef = ref<HTMLElement>();
let pollTimer: number | undefined;
let documentRequestId = 0;

const attachmentLabel = computed(() => attachments.value.length ? `${attachments.value.length} 份：${attachments.value.map((file) => file.name).join("、")}` : "未添加附件");
const statusLabel = computed(() => historyStatusLabel(task.value?.status || "PROCESSING"));
const statusClass = computed(() => task.value?.status === "SUCCESS" ? "done" : task.value?.status === "FAILED" ? "failed" : "");
const resultMeta = computed(() => result.value ? `${result.value.task.contract_name} · ${result.value.task.scene_name} · ${result.value.task.scale}尺度 · ${result.value.task.position}立场` : "正在读取结果");
const contractTitle = computed(() => result.value?.task.contract_name.replace(/\.[^.]+$/, "") || "合同原文");
const currentDocumentMeta = computed(() => result.value?.documents.find((item) => item.file_id === currentFileId.value) || result.value?.document);
const currentDocumentTitle = computed(() => currentDocumentMeta.value?.file_name.replace(/\.[^.]+$/, "") || contractTitle.value);
const defaultDownloadExtension = computed(() => result.value?.document.file_extension.toLowerCase() === "docx" ? "docx" : "pdf");
const filteredRisks = computed(() => !result.value ? [] : riskFilter.value === "all" ? result.value.risks : result.value.risks.filter((risk) => risk.risk_level === riskFilter.value));
const currentPageRisks = computed(() => result.value?.risks.filter((risk) => risk.locatable && riskSpans(risk).some((span) => span.source_file_id === currentFileId.value && span.page_number === currentPage.value)) || []);

interface TextSegment { text: string; riskIds?: number[]; level?: ReviewRisk["risk_level"] }
interface RenderedBlock { blockId: string; type: "paragraph" | "table"; heading?: boolean; segments?: TextSegment[]; rows?: TextSegment[][][] }

function highestLevel(riskIds: number[]): ReviewRisk["risk_level"] {
  const levels = riskIds.map((id) => result.value?.risks.find((risk) => risk.id === id)?.risk_level);
  return levels.includes("high") ? "high" : levels.includes("medium") ? "medium" : "low";
}

function segmentsForText(text: string, blockId: string, baseOffset = 0): TextSegment[] {
  if (!result.value) return [{ text }];
  const matches = result.value.risks
    .flatMap((risk) => riskSpans(risk).filter((span) => risk.locatable && span.source_file_id === currentFileId.value && span.page_number === currentPage.value && span.block_id === blockId).map((span) => ({ risk, start: Math.max(span.start_offset, baseOffset) - baseOffset, end: Math.min(span.end_offset, baseOffset + text.length) - baseOffset })))
    .filter((item) => item.start >= 0 && item.end <= text.length && item.start < item.end)
    .sort((a, b) => a.start - b.start || b.end - a.end);
  const groups: Array<{ start: number; end: number; riskIds: number[] }> = [];
  for (const match of matches) {
    const previous = groups[groups.length - 1];
    if (previous && match.start < previous.end) {
      previous.end = Math.max(previous.end, match.end);
      previous.riskIds.push(match.risk.id);
    } else {
      groups.push({ start: match.start, end: match.end, riskIds: [match.risk.id] });
    }
  }
  const segments: TextSegment[] = [];
  let cursor = 0;
  for (const group of groups) {
    if (group.start > cursor) segments.push({ text: text.slice(cursor, group.start) });
    segments.push({ text: text.slice(group.start, group.end), riskIds: group.riskIds, level: highestLevel(group.riskIds) });
    cursor = group.end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) });
  return segments;
}

function tableSegments(rows: string[][], blockId: string): TextSegment[][][] {
  let offset = 0;
  return rows.map((row, rowIndex) => {
    const renderedRow = row.map((cell, cellIndex) => {
      const segments = segmentsForText(cell, blockId, offset);
      offset += cell.length;
      if (cellIndex < row.length - 1) offset += 3;
      return segments;
    });
    if (rowIndex < rows.length - 1) offset += 1;
    return renderedRow;
  });
}

const renderedBlocks = computed<RenderedBlock[]>(() => {
  if (!currentDocumentPage.value) return [];
  const blocks = currentDocumentPage.value.blocks.length
    ? currentDocumentPage.value.blocks
    : [{ block_id: `p${currentPage.value}:b1`, type: "paragraph" as const, text: currentDocumentPage.value.text }];
  return blocks.map((block) => block.type === "table"
    ? { blockId: block.block_id, type: "table", rows: tableSegments(block.rows || [], block.block_id) }
    : { blockId: block.block_id, type: "paragraph", heading: /title|heading|标题/i.test(block.style || ""), segments: segmentsForText(block.text, block.block_id) });
});
const pageSourceLabel = computed(() => currentDocumentPage.value?.text_source === "ocr" ? "OCR 识别文本" : currentDocumentPage.value?.text_source === "unavailable" ? "文本识别失败" : "原生文本");

function riskSpans(risk: ReviewRisk) {
  if (risk.location_spans?.length) return risk.location_spans;
  if (!risk.source_file_id || !risk.page_number || !risk.block_id || risk.start_offset === null || risk.end_offset === null || !risk.anchor_text || !risk.anchor_hash) return [];
  return [{ source_file_id: risk.source_file_id, page_number: risk.page_number, block_id: risk.block_id, start_offset: risk.start_offset, end_offset: risk.end_offset, anchor_text: risk.anchor_text, anchor_hash: risk.anchor_hash }];
}

function validateFiles(files: File[]) { const invalid = files.find((file) => !allowedExtensions.includes(file.name.split(".").pop()?.toLowerCase() || "")); if (invalid) return `文件“${invalid.name}”格式不支持，请上传 DOC、DOCX、PDF 或 TXT 文件。`; const oversized = files.find((file) => file.size > 20 * 1024 * 1024); return oversized ? `文件“${oversized.name}”超过 20 MB 限制。` : ""; }
function fileExtension(file: File) { return file.name.split(".").pop()?.toUpperCase() || "FILE"; }
function selectMainFile(event: Event) { const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return; const error = validateFiles([file]); if (error) { errorMessage.value = error; (event.target as HTMLInputElement).value = ""; return; } mainFile.value = file; errorMessage.value = ""; }
function selectAttachments(event: Event) { setAttachments(Array.from((event.target as HTMLInputElement).files || [])); }
function setAttachments(files: File[]) { if (files.length > 3) { errorMessage.value = "合同附件最多上传 3 份，请重新选择。"; if (attachmentInput.value) attachmentInput.value.value = ""; return; } const error = validateFiles(files); if (error) { errorMessage.value = error; return; } attachments.value = files; errorMessage.value = ""; }
function handleDrop(event: DragEvent, zone: "main" | "attachments") { draggingZone.value = null; const files = Array.from(event.dataTransfer?.files || []); if (!files.length) return; if (zone === "main") { const error = validateFiles([files[0]]); if (error) { errorMessage.value = error; return; } mainFile.value = files[0]; errorMessage.value = ""; } else setAttachments(files); }

async function startReview() {
  if (!mainFile.value) { errorMessage.value = "请先上传合同主文件。"; return; }
  if (!form.sceneId) { errorMessage.value = "请选择可用的审查场景。"; return; }
  errorMessage.value = ""; submitting.value = true; submitLabel.value = "正在上传材料";
  try { const upload = await uploadContract(mainFile.value, attachments.value); submitLabel.value = "正在创建任务"; task.value = await createReview({ upload_id: upload.upload_id, scene_id: form.sceneId, scale: form.scale, position: form.position }, generateUuid()); await loadHistory(); beginPolling(); }
  catch (error) { errorMessage.value = apiErrorMessage(error, "任务创建失败，请稍后重试。"); }
  finally { submitting.value = false; }
}
function beginPolling() { window.clearTimeout(pollTimer); if (task.value?.status === "PROCESSING") pollTimer = window.setTimeout(pollStatus, 900); }
async function pollStatus() { if (!task.value) return; try { task.value = await getReviewStatus(task.value.id); pollError.value = ""; syncTaskInHistory(task.value); if (task.value.status === "SUCCESS") { ElMessage.success("合同审查已完成"); await loadHistory(); } else if (task.value.status === "FAILED") await loadHistory(); } catch (error) { pollError.value = apiErrorMessage(error, "任务状态更新失败，将自动重试。"); } if (task.value?.status === "PROCESSING") beginPolling(); }
function stepState(index: number) { if (!task.value) return ""; if (task.value.status === "SUCCESS" || index < task.value.current_step) return "complete"; if (task.value.status === "FAILED" && index === task.value.current_step) return "failed"; if (task.value.status === "PROCESSING" && index === task.value.current_step) return "active"; return ""; }
function stepStatus(index: number) { const state = stepState(index); return state === "complete" ? "已完成" : state === "active" ? "处理中" : state === "failed" ? "失败" : "等待"; }
async function retry() { if (!task.value) return; retrying.value = true; try { task.value = await retryReview(task.value.id); pollError.value = ""; syncTaskInHistory(task.value); beginPolling(); } catch (error) { pollError.value = apiErrorMessage(error, "重新审查失败，请稍后重试。"); } finally { retrying.value = false; } }
function newReview() { window.clearTimeout(pollTimer); task.value = undefined; result.value = undefined; mainFile.value = undefined; attachments.value = []; form.sceneId = scenes.value[0]?.id; form.scale = "标准"; form.position = "甲方"; errorMessage.value = ""; pollError.value = ""; if (mainInput.value) mainInput.value.value = ""; if (attachmentInput.value) attachmentInput.value.value = ""; }

async function loadHistory(resetPage = false) { if (resetPage) history.value.page = 1; historyLoading.value = true; try { history.value = await listReviewHistory({ keyword: historyFilters.keyword.trim() || undefined, status: historyFilters.status || undefined, page: history.value.page, page_size: history.value.page_size }); } catch (error) { ElMessage.error(apiErrorMessage(error, "审查记录加载失败。")); } finally { historyLoading.value = false; } }
function resetHistoryFilters() { historyFilters.keyword = ""; historyFilters.status = ""; loadHistory(true); }
function syncTaskInHistory(current: ReviewTask) { const item = history.value.items.find((record) => record.id === current.id); if (item) { item.status = current.status; item.error_message = current.error_message; } }
function historyStatusLabel(status: ReviewStatus) { return ({ PROCESSING: "处理中", SUCCESS: "已完成", FAILED: "失败" })[status]; }
function historyStatusClass(status: ReviewStatus) { return status === "SUCCESS" ? "done" : status === "FAILED" ? "failed" : "processing"; }
function formatTime(value: string) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }

async function openResult(taskId: number) { resultVisible.value = true; result.value = undefined; pageCache.clear(); clearPreviewCache(); try { result.value = await getReviewResult(taskId); if (!result.value.documents.length) result.value.documents = [result.value.document]; currentFileId.value = result.value.documents[0]?.file_id || "main"; riskFilter.value = "all"; currentPage.value = 1; const firstRisk = result.value.risks[0]; activeRiskId.value = firstRisk?.id; expandedRiskIds.value = new Set(firstRisk ? [firstRisk.id] : []); documentMode.value = currentDocumentMeta.value?.preview_available ? "layout" : "text"; await loadDocumentPage(1); } catch (error) { resultVisible.value = false; ElMessage.error(apiErrorMessage(error, "审查结果加载失败。")); } }
function closeResult() { resultVisible.value = false; feedbackVisible.value = false; clearPreviewCache(); }
function levelLabel(level: ReviewRisk["risk_level"]) { return ({ high: "高风险", medium: "中风险", low: "低风险" })[level]; }
function setRiskFilter(level: "all" | ReviewRisk["risk_level"]) { riskFilter.value = level; if (activeRiskId.value && !riskVisible(activeRiskId.value)) activeRiskId.value = undefined; }
function riskVisible(riskId: number) { const risk = result.value?.risks.find((item) => item.id === riskId); return Boolean(risk && (riskFilter.value === "all" || risk.risk_level === riskFilter.value)); }
async function focusRisk(riskId?: number) { if (!riskId) return; const risk = result.value?.risks.find((item) => item.id === riskId); if (!risk) return; riskFilter.value = "all"; activeRiskId.value = risk.id; expandedRiskIds.value = new Set([...expandedRiskIds.value, risk.id]); await nextTick(); riskPaneRef.value?.querySelector<HTMLElement>(`#risk-card-${risk.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }); }
async function focusRiskGroup(riskIds: number[]) { if (!riskIds.length) return; const currentIndex = activeRiskId.value ? riskIds.indexOf(activeRiskId.value) : -1; await focusRisk(riskIds[(currentIndex + 1) % riskIds.length]); }
function markTitle(riskIds: number[]) { return riskIds.map((id) => result.value?.risks.find((risk) => risk.id === id)?.risk_name).filter(Boolean).join("；"); }
async function waitForRiskMark(riskId: number) {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    await nextTick();
    const mark = documentPaneRef.value?.querySelector<HTMLElement>(`mark[data-risk-ids~="${riskId}"]`);
    if (mark) return mark;
    await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
  }
  return undefined;
}
async function focusMark(risk: ReviewRisk) { activeRiskId.value = risk.id; const span = riskSpans(risk)[0]; if (!risk.locatable || !span) return; documentMode.value = "text"; currentFileId.value = span.source_file_id; const loaded = await loadDocumentPage(span.page_number); if (!loaded) return; const mark = await waitForRiskMark(risk.id); mark?.scrollIntoView({ behavior: "smooth", block: "center" }); }
async function toggleRisk(risk: ReviewRisk) { const next = new Set(expandedRiskIds.value); if (next.has(risk.id)) next.delete(risk.id); else next.add(risk.id); expandedRiskIds.value = next; await focusMark(risk); }

function openFeedback(risk: ReviewRisk) { if (risk.feedback_submitted) return; feedbackRisk.value = risk; feedbackContent.value = ""; feedbackError.value = ""; feedbackVisible.value = true; }
async function submitFeedback() { const content = feedbackContent.value.trim(); if (!content) { feedbackError.value = "请填写反馈原因"; return; } if (!result.value || !feedbackRisk.value) return; feedbackSubmitting.value = true; try { await submitRiskFeedback(result.value.task.id, feedbackRisk.value.id, content); feedbackRisk.value.feedback_submitted = true; feedbackVisible.value = false; ElMessage.success("反馈已提交"); } catch (error) { feedbackError.value = apiErrorMessage(error, "反馈提交失败，请稍后重试。"); } finally { feedbackSubmitting.value = false; } }

async function loadDocumentPage(pageNumber: number) { if (!result.value) return false; const requestId = ++documentRequestId; const fileId = currentFileId.value; const cacheKey = `${fileId}:${pageNumber}`; pageLoading.value = true; try { const page = pageCache.get(cacheKey) || await getDocumentPage(result.value.task.id, fileId, pageNumber); pageCache.set(cacheKey, page); if (requestId !== documentRequestId || fileId !== currentFileId.value) return false; currentDocumentPage.value = page; currentPage.value = pageNumber; if (currentDocumentMeta.value?.preview_available && documentMode.value === "layout") { if (!previewCache.has(cacheKey)) { const blob = await getDocumentPageImage(result.value.task.id, fileId, pageNumber); previewCache.set(cacheKey, URL.createObjectURL(blob)); } if (requestId !== documentRequestId || fileId !== currentFileId.value) return false; previewUrl.value = previewCache.get(cacheKey) || ""; } else previewUrl.value = ""; return true; } catch (error) { if (requestId === documentRequestId) { documentMode.value = "text"; previewUrl.value = ""; ElMessage.error(apiErrorMessage(error, "文档页面加载失败。")); } return false; } finally { if (requestId === documentRequestId) pageLoading.value = false; } }
async function changePage(pageNumber: number) { if (!result.value || pageNumber < 1 || pageNumber > (currentDocumentMeta.value?.page_count || 1)) return; await loadDocumentPage(pageNumber); }
async function changeDocument(fileId: string | number) { currentFileId.value = String(fileId); documentMode.value = currentDocumentMeta.value?.preview_available ? "layout" : "text"; await loadDocumentPage(1); }
async function changeDocumentMode(mode: string | number | boolean) { documentMode.value = String(mode) === "layout" ? "layout" : "text"; await loadDocumentPage(currentPage.value); }
function clearPreviewCache() { documentRequestId += 1; pageLoading.value = false; previewCache.forEach((url) => URL.revokeObjectURL(url)); previewCache.clear(); previewUrl.value = ""; currentDocumentPage.value = undefined; }
function downloadFileName(disposition: string, extension: string) { const fallback = `${contractTitle.value}_带标记版.${extension}`; const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]; const quoted = disposition.match(/filename="([^"]+)"/i)?.[1]; try { return decodeURIComponent(encoded || quoted || fallback).replace(/[\\/\u0000-\u001f]/g, "_"); } catch { return fallback; } }
async function downloadFailureMessage(error: unknown) { const payload = (error as { response?: { data?: unknown } })?.response?.data; if (payload instanceof Blob) { try { const parsed = JSON.parse(await payload.text()) as { detail?: string }; if (parsed.detail) return parsed.detail; } catch { /* Response was not JSON. */ } } return error instanceof Error && error.message ? error.message : apiErrorMessage(error, "标记版 PDF 生成失败。"); }
async function downloadResult(format: "original" | "pdf") { if (!result.value || downloadLoading.value) return; downloadLoading.value = true; const extension = format === "pdf" ? "pdf" : defaultDownloadExtension.value; try { const { blob, disposition, contentType } = await downloadMarkedDocument(result.value.task.id, format); const expectedType = extension === "docx" ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document" : "application/pdf"; if (!blob.size || !contentType.toLowerCase().includes(expectedType)) throw new Error(`下载响应不是有效的 ${extension.toUpperCase()} 文件。`); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = downloadFileName(disposition, extension); link.hidden = true; document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 3000); ElMessage.success(`带标记版 ${extension.toUpperCase()} 已开始下载`); } catch (error) { ElMessage.error(await downloadFailureMessage(error)); } finally { downloadLoading.value = false; } }
async function loadScenes() { loadingScenes.value = true; try { scenes.value = await listAvailableScenes(); form.sceneId = scenes.value[0]?.id; if (!scenes.value.length) errorMessage.value = "当前没有可用的审查场景，请先完成场景与规则配置。"; } catch (error) { errorMessage.value = apiErrorMessage(error, "审查场景加载失败，请刷新页面重试。"); } finally { loadingScenes.value = false; } }

onMounted(() => { loadScenes(); loadHistory(); });
onBeforeUnmount(() => { window.clearTimeout(pollTimer); clearPreviewCache(); });
</script>

<style scoped src="../assets/review-workbench.css"></style>
