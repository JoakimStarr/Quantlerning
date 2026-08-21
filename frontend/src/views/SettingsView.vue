<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  Bot,
  Check,
  Globe,
  List,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-vue-next'
import {
  activateAIProvider,
  createAIProvider,
  deleteAIProvider,
  fetchAIModelsByConfig,
  fetchAISettings,
  saveAISettings,
  testAIProvider,
  testAISettings,
  updateAIProvider,
  type AIProvider,
} from '@/api'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'
import PageBreadcrumb from '@/components/common/PageBreadcrumb.vue'

// AI 模型设置页：多 provider 管理（内置三家 + 自定义，均持久化到后端）+ 联网搜索 + 生成参数。
// provider 增删改/切换各自即时落盘（调独立端点）；底部「保存设置」只存全局参数。

// 新增 provider 时的预设快捷填充
interface Preset {
  name: string
  base_url: string
  model: string
}
const EDIT_PRESETS: Preset[] = [
  {
    name: '智谱 GLM',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    model: 'glm-4.7-flash',
  },
  {
    name: 'OpenCodeZen',
    base_url: 'https://opencode.ai/zen/v1',
    model: 'deepseek-v4-flash-free',
  },
  {
    name: '硅基流动 SiliconFlow',
    base_url: 'https://api.siliconflow.cn/v1',
    model: 'Qwen/Qwen2.5-7B-Instruct',
  },
  { name: '自定义', base_url: '', model: '' },
]

const providers = ref<AIProvider[]>([])
const activeProviderId = ref('')
const activeProvider = computed(
  () => providers.value.find((p) => p.id === activeProviderId.value) || providers.value[0],
)

// 全局参数（生成参数 + 联网搜索，底部统一保存）
const maxTokens = ref(1024)
const temperature = ref(0.4)
const webSearchKey = ref('')
const webKeyMasked = ref('')
const webConfigured = ref(false)

const loading = ref(true)
const saving = ref(false)
const error = ref('')

// 浮动提示（toast）：测试/保存/切换等操作反馈，任何滚动位置都可见
const toast = ref<{ type: 'ok' | 'bad' | 'info'; text: string; reply?: string } | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(type: 'ok' | 'bad' | 'info', text: string, reply?: string) {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { type, text, reply }
  toastTimer = setTimeout(() => {
    toast.value = null
    toastTimer = null
  }, 5000)
}

// 已保存全局值快照（用于「未保存修改」提示）
const savedGlobal = reactive({ maxTokens: 1024, temperature: 0.4 })
const dirty = computed(
  () =>
    maxTokens.value !== savedGlobal.maxTokens ||
    temperature.value !== savedGlobal.temperature ||
    webSearchKey.value.trim() !== '',
)

const tempHint = computed(() => {
  const t = temperature.value
  if (t <= 0.2) return '接近确定性：答案稳定、适合追问知识点'
  if (t <= 0.7) return '平衡：日常讲解与批改的推荐区间'
  if (t <= 1.2) return '较有创造力：可能给出不同表述'
  return '高随机：创意优先，但可能不够严谨'
})

async function reloadSettings() {
  loading.value = true
  error.value = ''
  try {
    const cfg = await fetchAISettings()
    providers.value = cfg.providers
    activeProviderId.value = cfg.active_provider_id
    maxTokens.value = cfg.max_tokens || 1024
    temperature.value = typeof cfg.temperature === 'number' ? cfg.temperature : 0.4
    webKeyMasked.value = cfg.web_search_key_masked || ''
    webConfigured.value = !!cfg.web_search_configured
    savedGlobal.maxTokens = maxTokens.value
    savedGlobal.temperature = temperature.value
  } catch (e: any) {
    error.value = e?.message || '加载设置失败'
    showToast('bad', error.value)
  } finally {
    loading.value = false
  }
}

onMounted(reloadSettings)

// ---------- provider 操作 ----------
const actingId = ref('') // 设为当前/删除 进行中的 id
const testingId = ref('')

async function activate(id: string) {
  actingId.value = id
  error.value = ''
  try {
    const res = await activateAIProvider(id)
    activeProviderId.value = res.active_provider_id
    const name = providers.value.find((x) => x.id === res.active_provider_id)?.name || ''
    showToast('ok', `已切换使用「${name}」。课程内「AI 追问」的模型下拉将跟随该 provider。`)
  } catch (e: any) {
    error.value = e?.message || '切换失败'
    showToast('bad', error.value)
  } finally {
    actingId.value = ''
  }
}

async function testProvider(p: AIProvider) {
  testingId.value = p.id
  error.value = ''
  try {
    const res = await testAIProvider(p.id)
    showToast(res.ok ? 'ok' : 'bad', `「${p.name}」${res.message}`, res.reply)
  } catch (e: any) {
    showToast('bad', `「${p.name}」连接测试失败：${e?.message || ''}`)
  } finally {
    testingId.value = ''
  }
}

async function removeProvider(p: AIProvider) {
  const label = p.builtin ? '重置为内置默认' : '删除该 provider'
  if (!window.confirm(`${label}「${p.name}」？`)) return
  actingId.value = p.id
  error.value = ''
  try {
    await deleteAIProvider(p.id)
    await reloadSettings()
    showToast('ok', p.builtin ? `「${p.name}」已重置为内置默认。` : `「${p.name}」已删除。`)
  } catch (e: any) {
    error.value = e?.message || '操作失败'
    showToast('bad', error.value)
  } finally {
    actingId.value = ''
  }
}

// ---------- 添加 / 编辑表单 ----------
const editorOpen = ref(false)
const editor = reactive({
  id: null as string | null, // null = 新增
  name: '',
  baseUrl: '',
  model: '',
  apiKey: '',
})
const editorConfigured = ref(false) // 编辑的 provider 是否已有 key（打码提示）
const editPreset = ref('自定义')
const editorSaving = ref(false)
const editorTesting = ref(false)

function openCreate() {
  editor.id = null
  editor.name = ''
  editor.baseUrl = ''
  editor.model = ''
  editor.apiKey = ''
  editorConfigured.value = false
  editPreset.value = '自定义'
  editorOpen.value = true
  modelList.value = []
  modelError.value = ''
}

function openEdit(p: AIProvider) {
  editor.id = p.id
  editor.name = p.name
  editor.baseUrl = p.base_url
  editor.model = p.model
  editor.apiKey = ''
  editorConfigured.value = p.configured
  editPreset.value = '自定义'
  editorOpen.value = true
  modelList.value = []
  modelError.value = ''
}

function closeEditor() {
  editorOpen.value = false
}

function applyEditPreset(e: Event) {
  const p = EDIT_PRESETS.find((x) => x.name === (e.target as HTMLSelectElement).value)
  if (!p) return
  editor.name = p.name
  editor.baseUrl = p.base_url
  editor.model = p.model
}

async function saveProvider() {
  error.value = ''
  const name = editor.name.trim()
  const baseUrl = editor.baseUrl.trim()
  const model = editor.model.trim()
  if (!name || !baseUrl || !model) {
    showToast('bad', '请填写 名称 / Base URL / 模型名称 后再保存')
    return
  }
  editorSaving.value = true
  try {
    if (editor.id) {
      const payload: { name?: string; base_url?: string; model?: string; api_key?: string } = {
        name,
        base_url: baseUrl,
        model,
      }
      if (editor.apiKey.trim()) payload.api_key = editor.apiKey.trim()
      await updateAIProvider(editor.id, payload)
      showToast('ok', '已保存。')
    } else {
      await createAIProvider({
        name,
        base_url: baseUrl,
        model,
        ...(editor.apiKey.trim() ? { api_key: editor.apiKey.trim() } : {}),
      })
      showToast('ok', '已添加并保存。可在列表中设为当前使用。')
    }
    editorOpen.value = false
    await reloadSettings()
  } catch (e: any) {
    error.value = e?.message || '保存失败'
    showToast('bad', error.value)
  } finally {
    editorSaving.value = false
  }
}

// 编辑器内「获取模型」下拉（按当前表单 base_url/api_key 拉取）
const modelList = ref<string[]>([])
const modelOpen = ref(false)
const modelQuery = ref('')
const modelLoading = ref(false)
const modelError = ref('')
const modelPopRef = ref<HTMLElement | null>(null)

const filteredModels = computed(() => {
  const q = modelQuery.value.trim().toLowerCase()
  if (!q) return modelList.value
  return modelList.value.filter((m) => m.toLowerCase().includes(q))
})

async function fetchEditorModels() {
  modelLoading.value = true
  modelError.value = ''
  modelOpen.value = true
  try {
    const res = await fetchAIModelsByConfig({
      base_url: editor.baseUrl.trim(),
      api_key: editor.apiKey.trim() || undefined,
      model: editor.model.trim(),
    })
    modelList.value = res.models
    modelError.value = res.error || ''
  } catch (e: any) {
    modelError.value = e?.message || '获取模型列表失败'
    modelList.value = []
  } finally {
    modelLoading.value = false
  }
}

function pickEditorModel(m: string) {
  editor.model = m
  modelOpen.value = false
}

function onDocClick(e: MouseEvent) {
  if (modelPopRef.value && !modelPopRef.value.contains(e.target as Node)) modelOpen.value = false
}
watch(modelOpen, (v) => {
  if (v) document.addEventListener('click', onDocClick)
  else document.removeEventListener('click', onDocClick)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  if (toastTimer) clearTimeout(toastTimer)
})

async function testEditor() {
  error.value = ''
  editorTesting.value = true
  try {
    const res = await testAISettings({
      base_url: editor.baseUrl.trim(),
      api_key: editor.apiKey.trim() || undefined,
      model: editor.model.trim(),
      max_tokens: maxTokens.value,
      temperature: temperature.value,
    })
    showToast(res.ok ? 'ok' : 'bad', res.message, res.reply)
  } catch (e: any) {
    showToast('bad', `连接测试失败：${e?.message || ''}`)
  } finally {
    editorTesting.value = false
  }
}

// ---------- 全局参数保存（底部） ----------
async function saveGlobal() {
  error.value = ''
  saving.value = true
  try {
    const cfg = await saveAISettings({
      max_tokens: maxTokens.value,
      temperature: temperature.value,
      ...(webSearchKey.value.trim() ? { web_search_key: webSearchKey.value.trim() } : {}),
    })
    webKeyMasked.value = cfg.web_search_key_masked || ''
    webConfigured.value = !!cfg.web_search_configured
    webSearchKey.value = ''
    savedGlobal.maxTokens = maxTokens.value
    savedGlobal.temperature = temperature.value
    showToast('ok', '已保存。生成参数与联网搜索设置已生效。')
  } catch (e: any) {
    error.value = e?.message || '保存失败'
    showToast('bad', error.value)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="settings-page">
    <PageBreadcrumb current="设置" />
    <h1 class="page-title">设置</h1>
    <p class="page-desc">
      配置课程内「AI 追问」与应用题批改所使用的模型。可管理多个供应商（内置三家 + 自定义），配置保存在后端，
      api key 不会显示在浏览器中。
    </p>

    <AppSpinner v-if="loading" text="加载设置…" />
    <AppError v-else-if="error && !activeProvider" :message="error" @retry="reloadSettings" />

    <div v-else class="settings-stack">
      <!-- 当前使用 provider 状态条 -->
      <div class="status-bar">
        <span class="status-dot" :class="activeProvider?.configured ? 'ok' : 'warn'"></span>
        <div class="status-info">
          <span class="status-label">
            {{ activeProvider?.configured ? '已配置' : '未配置 API Key' }} · {{ activeProvider?.name }}
          </span>
          <span class="status-model">{{ activeProvider?.model || '（未设置模型）' }}</span>
          <span class="status-url">{{ activeProvider?.base_url }}</span>
        </div>
        <button
          class="btn btn-ghost status-test"
          :disabled="testingId === activeProvider?.id"
          @click="activeProvider && testProvider(activeProvider)"
        >
          {{ testingId === activeProvider?.id ? '测试中…' : '测试连接' }}
        </button>
      </div>

      <!-- Provider 管理 -->
      <section class="settings-card">
        <div class="card-head card-head-icon">
          <Bot :size="16" class="card-head-ico" />
          <div class="card-head-txt">
            <h2 class="card-title">模型 Provider</h2>
            <p class="card-desc">
              当前使用（绿点）的 provider 用于日常回答；主 provider 限流或模型不可用时，自动轮换其他已配置 key 的
              provider。内置三家可修改（保存覆盖）、可重置，不可删除。
            </p>
          </div>
        </div>

        <!-- provider 列表 -->
        <ul class="prov-list">
          <li
            v-for="p in providers"
            :key="p.id"
            class="prov-item"
            :class="{ active: p.id === activeProviderId }"
          >
            <div class="prov-main">
              <div class="prov-head">
                <span class="prov-name">{{ p.name }}</span>
                <span v-if="p.builtin" class="badge badge-builtin">内置</span>
                <span v-if="p.id === activeProviderId" class="badge badge-active">使用中</span>
              </div>
              <div class="prov-sub">
                <span class="prov-model">{{ p.model || '（未设置模型）' }}</span>
                <span class="prov-url">{{ p.base_url }}</span>
              </div>
            </div>
            <div class="prov-key">
              <span v-if="p.configured" class="key-ok" :title="p.api_key_masked">key {{ p.api_key_masked }}</span>
              <span v-else class="key-miss">未配置 key</span>
            </div>
            <div class="prov-actions">
              <button
                v-if="p.id !== activeProviderId"
                class="btn btn-ghost"
                :disabled="actingId === p.id"
                @click="activate(p.id)"
              >
                设为当前
              </button>
              <button class="btn btn-ghost" :disabled="testingId === p.id" @click="testProvider(p)">
                {{ testingId === p.id ? '测试中…' : '测试' }}
              </button>
              <button class="btn btn-ghost" @click="openEdit(p)">
                <Pencil :size="12" /> 编辑
              </button>
              <button
                class="btn btn-ghost danger"
                :disabled="actingId === p.id"
                :title="p.builtin ? '重置为内置默认' : '删除该 provider'"
                @click="removeProvider(p)"
              >
                <RotateCcw v-if="p.builtin" :size="12" />
                <Trash2 v-else :size="12" />
                {{ p.builtin ? '重置' : '删除' }}
              </button>
            </div>
          </li>
        </ul>

        <!-- 添加 / 编辑表单 -->
        <div class="prov-editor">
          <button v-if="!editorOpen" class="btn btn-primary add-btn" @click="openCreate">
            <Plus :size="14" /> 添加 Provider
          </button>

          <div v-else class="editor-box">
            <div class="editor-title">{{ editor.id ? '编辑 Provider' : '添加 Provider' }}</div>

            <div class="field-group">
              <label class="field-label" for="edit-preset">预设快捷填充</label>
              <select id="edit-preset" class="preset-select" :value="editPreset" @change="applyEditPreset">
                <option v-for="p in EDIT_PRESETS" :key="p.name" :value="p.name">{{ p.name }}</option>
              </select>
              <p class="field-help">选择预设自动填入名称 / Base URL / 模型；自定义则手动填写。</p>
            </div>

            <div class="field-group">
              <label class="field-label" for="edit-name">名称</label>
              <input
                id="edit-name"
                v-model="editor.name"
                class="field-input"
                type="text"
                placeholder="如：我的 DeepSeek"
                spellcheck="false"
              />
            </div>

            <div class="field-group">
              <label class="field-label" for="edit-base-url">Base URL</label>
              <input
                id="edit-base-url"
                v-model="editor.baseUrl"
                class="field-input"
                type="text"
                placeholder="https://open.bigmodel.cn/api/paas/v4"
                spellcheck="false"
              />
              <p class="field-help">OpenAI 兼容接口地址，末尾无需斜杠。</p>
            </div>

            <div class="field-row">
              <div class="field-group grow">
                <label class="field-label" for="edit-model">模型名称</label>
                <div ref="modelPopRef" class="model-picker">
                  <div class="model-input-wrap">
                    <input
                      id="edit-model"
                      v-model="editor.model"
                      class="field-input"
                      type="text"
                      placeholder="glm-4-flash"
                      spellcheck="false"
                    />
                    <button
                      type="button"
                      class="model-fetch-btn"
                      :disabled="modelLoading"
                      :title="'从当前 base_url 拉取可用模型列表'"
                      @click="fetchEditorModels"
                    >
                      <RefreshCw v-if="modelLoading" :size="13" class="spin" />
                      <List v-else :size="13" />
                      {{ modelLoading ? '获取中' : '获取模型' }}
                    </button>
                  </div>
                  <Transition name="drop">
                    <div v-if="modelOpen" class="model-pop">
                      <div class="model-search">
                        <Search :size="13" />
                        <input v-model="modelQuery" placeholder="搜索模型…" spellcheck="false" @click.stop />
                      </div>
                      <div v-if="modelError" class="model-pop-error">{{ modelError }}</div>
                      <div class="model-list">
                        <button
                          v-for="m in filteredModels"
                          :key="m"
                          type="button"
                          class="model-item"
                          :class="{ cur: m === editor.model }"
                          @click="pickEditorModel(m)"
                        >
                          <span class="model-name">{{ m }}</span>
                        </button>
                        <div v-if="modelList.length === 0 && !modelError" class="model-empty">
                          点击「获取模型」从服务商拉取列表；也可直接手动输入模型名称。
                        </div>
                      </div>
                    </div>
                  </Transition>
                </div>
              </div>
              <div class="field-group grow">
                <label class="field-label" for="edit-api-key">API Key</label>
                <input
                  id="edit-api-key"
                  v-model="editor.apiKey"
                  class="field-input"
                  type="password"
                  :placeholder="editorConfigured ? '已配置，留空保持不变' : '粘贴 API Key'"
                  autocomplete="off"
                />
                <p class="field-help" v-if="editorConfigured">已配置 key，留空则保留原值。</p>
              </div>
            </div>

            <div class="editor-actions">
              <button class="btn btn-ghost" :disabled="editorTesting || editorSaving" @click="testEditor">
                {{ editorTesting ? '测试中…' : '测试连接' }}
              </button>
              <span class="spacer"></span>
              <button class="btn btn-ghost" :disabled="editorSaving" @click="closeEditor">取消</button>
              <button class="btn btn-primary" :disabled="editorSaving" @click="saveProvider">
                {{ editorSaving ? '保存中…' : '保存' }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 联网搜索（可选） -->
      <section class="settings-card">
        <div class="card-head card-head-icon">
          <Globe :size="16" class="card-head-ico" />
          <div>
            <h2 class="card-title">联网搜索</h2>
            <p class="card-desc">可选。AI 面板开启「联网」开关后，回答会检索外部实时信息并列出参考文献。</p>
          </div>
        </div>

        <div class="field-group">
          <label class="field-label" for="web-search-key">Tavily API Key</label>
          <input
            id="web-search-key"
            v-model="webSearchKey"
            class="field-input"
            type="password"
            placeholder="输入 Tavily API Key"
            autocomplete="off"
          />
          <p class="field-help" v-if="webConfigured">
            已配置：<code class="masked">{{ webKeyMasked }}</code>（重新输入可更换；不输入则保留原 key）
          </p>
          <p class="field-help" v-else>
            未配置——面板的「联网」开关将不可用。Tavily 有免费额度（约 1000 次/月），在
            <a href="https://tavily.com" target="_blank" rel="noreferrer">tavily.com</a> 注册后复制 API Key 填入。
          </p>
        </div>
      </section>

      <!-- 生成参数 -->
      <section class="settings-card">
        <div class="card-head card-head-icon">
          <SlidersHorizontal :size="16" class="card-head-ico" />
          <div>
            <h2 class="card-title">生成参数</h2>
            <p class="card-desc">控制 AI 回答的随机度与长度（作用于当前 provider）</p>
          </div>
        </div>

        <div class="field-group">
          <div class="slider-head">
            <label class="field-label" for="temperature">温度 temperature</label>
            <span class="slider-value">{{ temperature.toFixed(1) }}</span>
          </div>
          <input
            id="temperature"
            v-model.number="temperature"
            class="slider"
            type="range"
            min="0"
            max="2"
            step="0.1"
          />
          <p class="field-help">{{ tempHint }}（0=稳定，2=随机）</p>
        </div>

        <div class="field-group">
          <div class="slider-head">
            <label class="field-label" for="max-tokens">最大输出 token 数</label>
            <span class="slider-value">{{ maxTokens }}</span>
          </div>
          <input
            id="max-tokens"
            v-model.number="maxTokens"
            class="slider"
            type="range"
            min="64"
            max="4096"
            step="64"
          />
          <p class="field-help">单次回答的最大长度，AI 追问默认可到 1024。</p>
        </div>
      </section>

      <!-- 状态与操作 -->
      <div v-if="error" class="msg-error">{{ error }}</div>

      <div class="actions-bar">
        <span v-if="dirty" class="dirty-hint">有未保存的生成参数 / 联网搜索修改</span>
        <div class="actions">
          <button class="btn btn-primary" :disabled="saving" @click="saveGlobal">
            {{ saving ? '保存中…' : '保存设置' }}
          </button>
        </div>
      </div>
      <p class="actions-help">Provider 的增删改、切换即时保存；此按钮只保存生成参数与联网搜索。</p>
    </div>

    <!-- 浮动提示 -->
    <Transition name="toast">
      <div v-if="toast" class="toast" :class="toast.type">
        <strong class="toast-mark">
          <Check v-if="toast.type === 'ok'" :size="14" />
          <X v-else :size="14" />
          {{ toast.text }}
        </strong>
        <div v-if="toast.reply" class="toast-reply">{{ toast.reply }}</div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.settings-page { max-width: 960px; margin: 0 auto; }
.page-title { font-size: 24px; margin-bottom: 8px; }
.page-desc { color: var(--text-3); font-size: 14px; line-height: 1.7; margin-bottom: 20px; }

.settings-stack { display: flex; flex-direction: column; gap: 16px; }

/* 当前使用 provider 状态条 */
.status-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--primary-soft);
  border: 1px solid color-mix(in srgb, var(--primary) 40%, transparent);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  flex-wrap: wrap;
}
.status-dot {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--warning);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--warning) 25%, transparent);
}
.status-dot.ok {
  background: var(--success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--success) 25%, transparent);
}
.status-info { display: flex; flex-direction: column; gap: 1px; min-width: 0; flex: 1; }
.status-label { font-size: 11px; color: var(--text-3); }
.status-model { font-size: 15px; font-weight: 700; color: var(--primary); }
.status-url { font-size: 11.5px; color: var(--text-3); font-family: var(--font-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-test { flex-shrink: 0; }

.settings-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px 24px;
  box-shadow: var(--shadow-sm);
}
.card-head { margin-bottom: 18px; }
.card-title { font-size: 16px; margin: 0 0 2px; }
.card-desc { font-size: 12.5px; color: var(--text-3); margin: 0; }
.card-head-icon { display: flex; align-items: flex-start; gap: 10px; }
.card-head-txt { min-width: 0; }
.card-head-ico { color: var(--primary); margin-top: 2px; flex-shrink: 0; }

.field-group { margin-bottom: 18px; }
.field-group:last-child { margin-bottom: 0; }
.field-row { display: flex; gap: 16px; }
.field-row .grow { flex: 1; }
.field-label {
  display: block; font-size: 13px; font-weight: 600;
  color: var(--text-2); margin-bottom: 6px;
}
.field-input {
  width: 100%; box-sizing: border-box;
  font-family: var(--font-mono); font-size: 13.5px; color: var(--text-1);
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 8px 10px;
}
.field-input:focus { outline: none; border-color: var(--primary); }
.field-help { font-size: 12px; color: var(--text-3); margin-top: 5px; line-height: 1.6; }
.masked { font-family: var(--font-mono); background: var(--bg-hover); padding: 1px 6px; border-radius: 4px; }

/* provider 列表 */
.prov-list { list-style: none; margin: 0 0 16px; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.prov-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  flex-wrap: wrap;
}
.prov-item.active {
  border-color: color-mix(in srgb, var(--primary) 55%, transparent);
  background: color-mix(in srgb, var(--primary) 6%, var(--bg-card));
}
.prov-main { min-width: 0; flex: 1; }
.prov-head { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; flex-wrap: wrap; }
.prov-name { font-size: 13.5px; font-weight: 700; color: var(--text-1); }
.prov-sub { display: flex; flex-direction: column; gap: 1px; }
.prov-model { font-size: 12px; color: var(--text-2); font-family: var(--font-mono); }
.prov-url { font-size: 11px; color: var(--text-3); font-family: var(--font-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 360px; }
.badge {
  font-size: 10.5px; line-height: 1; padding: 3px 6px; border-radius: 999px;
  font-weight: 600;
}
.badge-builtin { background: var(--bg-hover); color: var(--text-3); }
.badge-active { background: color-mix(in srgb, var(--success) 15%, transparent); color: var(--success); }
.prov-key { font-size: 11.5px; font-family: var(--font-mono); flex-shrink: 0; }
.key-ok { color: var(--success); }
.key-miss { color: var(--warning); }
.prov-actions { display: flex; gap: 6px; flex-shrink: 0; flex-wrap: wrap; }
.prov-actions .btn { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; font-size: 12px; }
.btn.danger { color: var(--danger, #dc2626); }
.btn.danger:hover { border-color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger, #dc2626) 6%, transparent); }

/* 添加 / 编辑表单 */
.prov-editor { border-top: 1px solid var(--border); padding-top: 16px; }
.add-btn { display: inline-flex; align-items: center; gap: 6px; }
.editor-box {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--bg-hover) 40%, transparent);
  padding: 16px;
}
.editor-title { font-size: 13.5px; font-weight: 700; color: var(--text-1); margin-bottom: 14px; }
.editor-actions { display: flex; gap: 8px; margin-top: 4px; }
.spacer { flex: 1; }

/* 供应商预设下拉 */
.preset-select {
  width: 100%;
  box-sizing: border-box;
  font-size: 13.5px;
  font-family: inherit;
  color: var(--text-1);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  cursor: pointer;
}
.preset-select:focus { outline: none; border-color: var(--primary); }

/* 模型选择器：输入框 + 获取按钮 + 可搜索下拉 */
.model-picker { position: relative; }
.model-input-wrap { position: relative; }
.model-input-wrap .field-input { padding-right: 92px; }
.model-fetch-btn {
  position: absolute;
  right: 4px;
  top: 4px;
  bottom: 4px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  background: var(--bg-hover);
  color: var(--text-2);
  font-size: 12px;
  padding: 0 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.12s;
}
.model-fetch-btn:hover:not(:disabled) { background: var(--primary-soft); color: var(--primary); }
.model-fetch-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.spin { animation: rotate 0.8s linear infinite; }
@keyframes rotate { to { transform: rotate(360deg); } }

.model-pop {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  width: min(340px, 78vw);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  z-index: 30;
}
.model-search {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-3);
}
.model-search input {
  flex: 1;
  border: none;
  background: none;
  outline: none;
  font-size: 12.5px;
  color: var(--text-1);
  font-family: inherit;
}
.model-pop-error {
  padding: 8px 10px;
  font-size: 12px;
  color: var(--danger, #dc2626);
  background: color-mix(in srgb, var(--danger, #dc2626) 6%, transparent);
  border-bottom: 1px solid var(--border);
  line-height: 1.5;
}
.model-list { max-height: 240px; overflow-y: auto; padding: 4px; }
.model-item {
  display: block;
  width: 100%;
  border: none;
  background: none;
  text-align: left;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.model-item:hover { background: var(--bg-hover); }
.model-item.cur { background: var(--primary-soft); color: var(--primary); }
.model-empty { padding: 14px 10px; text-align: center; font-size: 12px; color: var(--text-3); line-height: 1.6; }
.drop-enter-active, .drop-leave-active { transition: opacity 0.12s, transform 0.12s; }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(-6px); }

.slider-head { display: flex; align-items: baseline; justify-content: space-between; }
.slider-head .field-label { margin-bottom: 2px; }
.slider-value {
  font-size: 14px; font-weight: 700; color: var(--primary);
  font-variant-numeric: tabular-nums;
}
.slider { width: 100%; accent-color: var(--primary); cursor: pointer; margin: 6px 0 2px; }

.msg-error { font-size: 13px; padding: 9px 12px; border-radius: var(--radius-sm); line-height: 1.6; color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent); }

/* 浮动提示 toast：右上角固定，操作反馈立即可见 */
.toast {
  position: fixed;
  top: 72px;
  right: 20px;
  z-index: 1000;
  max-width: min(400px, 86vw);
  font-size: 13px;
  line-height: 1.6;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: var(--bg-card);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-lg);
}
.toast.ok {
  color: var(--success, #16a34a);
  border-color: color-mix(in srgb, var(--success) 45%, transparent);
  background: color-mix(in srgb, var(--success) 8%, var(--bg-card));
}
.toast.bad {
  color: var(--danger, #dc2626);
  border-color: color-mix(in srgb, var(--danger, #dc2626) 45%, transparent);
  background: color-mix(in srgb, var(--danger, #dc2626) 8%, var(--bg-card));
}
.toast-mark { display: inline-flex; align-items: center; gap: 6px; }
.toast-reply { margin-top: 4px; color: var(--text-2); font-size: 12px; }
.toast-enter-active, .toast-leave-active { transition: opacity 0.18s, transform 0.18s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-8px); }

.actions-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.dirty-hint {
  font-size: 12px;
  color: var(--warning);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.dirty-hint::before {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--warning);
}
.actions { display: flex; justify-content: flex-end; gap: 10px; }
.actions-help { font-size: 12px; color: var(--text-3); text-align: right; margin: 8px 0 0; }
.btn { font-size: 13px; padding: 7px 18px; border-radius: var(--radius-sm); cursor: pointer; border: none; }
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost { background: none; border: 1px solid var(--border); color: var(--text-2); }
.btn-ghost:disabled { opacity: 0.6; cursor: not-allowed; }

@media (max-width: 560px) {
  .field-row { flex-direction: column; gap: 0; }
  .prov-actions { width: 100%; justify-content: flex-end; }
}
</style>
