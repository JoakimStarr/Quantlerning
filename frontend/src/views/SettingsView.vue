<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Globe,
  List,
  RefreshCw,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-vue-next'
import { fetchAIModelsByConfig, fetchAISettings, saveAISettings, testAISettings } from '@/api'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'
import PageBreadcrumb from '@/components/common/PageBreadcrumb.vue'

// AI 模型设置页：主/备用模型 + 联网搜索 + 生成参数。
// 显式保存：底部操作栏 + 「未保存修改」提示；api key 只存后端，不回显。

// 内置供应商预设（OpenAI 兼容接口）
interface ProviderPreset {
  name: string
  base_url: string
  model: string
  hint: string
}
const PRESETS: ProviderPreset[] = [
  {
    name: '智谱 GLM',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    model: 'glm-4.7-flash',
    hint: '智谱 AI 开放平台，glm-4.7-flash 永久免费（200K 上下文）',
  },
  {
    name: 'OpenCodeZen',
    base_url: 'https://opencode.ai/zen/v1',
    model: 'deepseek-v4-flash-free',
    hint: '当前 .env 默认配置',
  },
  {
    name: '硅基流动 SiliconFlow',
    base_url: 'https://api.siliconflow.cn/v1',
    model: 'Qwen/Qwen2.5-7B-Instruct',
    hint: '硅基流动，需在其平台申请 key',
  },
  {
    name: '自定义',
    base_url: '',
    model: '',
    hint: '任何 OpenAI 兼容接口：填 base_url + model + api key',
  },
]

const activePreset = ref('')
const activePresetHint = computed(
  () => PRESETS.find((p) => p.name === activePreset.value)?.hint || '',
)
const baseUrl = ref('')
const model = ref('')
const apiKey = ref('')
const maxTokens = ref(1024)
const temperature = ref(0.4)

// 备用模型（主模型限流时自动切换）；默认折叠
const fbOpen = ref(false)
const fbBaseUrl = ref('')
const fbModel = ref('')
const fbApiKey = ref('')
const fbMaxTokens = ref(1024)
const fbKeyMasked = ref('')
const fbConfigured = ref(false)

// 联网搜索（Tavily，可选）
const webSearchKey = ref('')
const webKeyMasked = ref('')
const webConfigured = ref(false)

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const savedKeyMasked = ref('')
const configured = ref(false)
const error = ref('')
const notice = ref('')
const testResult = ref<{ ok: boolean; message: string; reply?: string } | null>(null)

// 已保存值快照：用于「未保存修改」提示（key 输入框始终清空，非空即视为待保存）
const savedSnapshot = reactive({
  baseUrl: '',
  model: '',
  maxTokens: 1024,
  temperature: 0.4,
  fbBaseUrl: '',
  fbModel: '',
  fbMaxTokens: 1024,
})
function snapshotCurrent() {
  savedSnapshot.baseUrl = baseUrl.value
  savedSnapshot.model = model.value
  savedSnapshot.maxTokens = maxTokens.value
  savedSnapshot.temperature = temperature.value
  savedSnapshot.fbBaseUrl = fbBaseUrl.value
  savedSnapshot.fbModel = fbModel.value
  savedSnapshot.fbMaxTokens = fbMaxTokens.value
}
const dirty = computed(() => {
  if (apiKey.value.trim() || fbApiKey.value.trim() || webSearchKey.value.trim()) return true
  return (
    baseUrl.value !== savedSnapshot.baseUrl ||
    model.value !== savedSnapshot.model ||
    maxTokens.value !== savedSnapshot.maxTokens ||
    temperature.value !== savedSnapshot.temperature ||
    fbBaseUrl.value !== savedSnapshot.fbBaseUrl ||
    fbModel.value !== savedSnapshot.fbModel ||
    fbMaxTokens.value !== savedSnapshot.fbMaxTokens
  )
})

const tempHint = computed(() => {
  const t = temperature.value
  if (t <= 0.2) return '接近确定性：答案稳定、适合追问知识点'
  if (t <= 0.7) return '平衡：日常讲解与批改的推荐区间'
  if (t <= 1.2) return '较有创造力：可能给出不同表述'
  return '高随机：创意优先，但可能不够严谨'
})

// 模型选择器：点「获取模型」按当前表单 base_url/api_key 拉列表，支持搜索筛选
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

async function fetchModels() {
  modelLoading.value = true
  modelError.value = ''
  modelOpen.value = true
  try {
    const res = await fetchAIModelsByConfig({
      base_url: baseUrl.value.trim(),
      api_key: apiKey.value.trim() || undefined,
      model: model.value.trim(),
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

function pickModel(m: string) {
  model.value = m
  testResult.value = null
  modelOpen.value = false
}

function onDocClick(e: MouseEvent) {
  if (modelPopRef.value && !modelPopRef.value.contains(e.target as Node)) modelOpen.value = false
}
watch(modelOpen, (v) => {
  if (v) document.addEventListener('click', onDocClick)
  else document.removeEventListener('click', onDocClick)
})
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

// 提取 host 用于「是否同一供应商」判断（容错 base_url 尾斜杠/路径差异）
function hostOf(u: string): string {
  try {
    return new URL(u).hostname
  } catch {
    return ''
  }
}

function applyPreset(p: ProviderPreset) {
  const sameProvider = !!p.base_url && hostOf(p.base_url) === hostOf(baseUrl.value.trim())
  activePreset.value = p.name
  baseUrl.value = p.base_url
  // 已配置同一供应商时保留当前 model；切换供应商或 model 为空才用预设默认值
  if (!sameProvider || !model.value) {
    model.value = p.model
  }
  modelOpen.value = false
  modelList.value = []
  testResult.value = null
}
function onPresetChange(e: Event) {
  const p = PRESETS.find((x) => x.name === (e.target as HTMLSelectElement).value)
  if (p) applyPreset(p)
}

async function reloadSettings() {
  loading.value = true
  error.value = ''
  try {
    const cfg = await fetchAISettings()
    baseUrl.value = cfg.base_url
    model.value = cfg.model
    maxTokens.value = cfg.max_tokens || 1024
    temperature.value = typeof cfg.temperature === 'number' ? cfg.temperature : 0.4
    savedKeyMasked.value = cfg.api_key_masked
    configured.value = cfg.configured
    fbBaseUrl.value = cfg.fallback_base_url || ''
    fbModel.value = cfg.fallback_model || ''
    fbMaxTokens.value = cfg.fallback_max_tokens || 1024
    fbKeyMasked.value = cfg.fallback_api_key_masked || ''
    fbConfigured.value = !!cfg.fallback_configured
    webKeyMasked.value = cfg.web_search_key_masked || ''
    webConfigured.value = !!cfg.web_search_configured
    // 匹配预设（按 base_url 前缀）
    const hit = PRESETS.find((p) => p.base_url && cfg.base_url.startsWith(p.base_url.split('/')[2] ?? ''))
    activePreset.value = hit?.name ?? (PRESETS[PRESETS.length - 1].name)
    snapshotCurrent()
  } catch (e: any) {
    error.value = e?.message || '加载设置失败'
  } finally {
    loading.value = false
  }
}

onMounted(reloadSettings)

async function save() {
  error.value = ''
  notice.value = ''
  saving.value = true
  // 已拉取过模型列表且当前 model 不在其中 → 保存后提示可能失效
  const modelWarn =
    modelList.value.length > 0 && !modelList.value.includes(model.value.trim())
  try {
    const payload: {
      base_url: string
      model: string
      max_tokens: number
      temperature: number
      api_key?: string
      fallback_base_url?: string
      fallback_model?: string
      fallback_max_tokens?: number | null
      fallback_api_key?: string
      web_search_key?: string
    } = {
      base_url: baseUrl.value.trim(),
      model: model.value.trim(),
      max_tokens: maxTokens.value,
      temperature: temperature.value,
      fallback_base_url: fbBaseUrl.value.trim(),
      fallback_model: fbModel.value.trim(),
      fallback_max_tokens: fbMaxTokens.value,
    }
    // api_key 未输入 → 不发该字段，保留后端已保存的 key（避免误删）
    if (apiKey.value.trim()) payload.api_key = apiKey.value.trim()
    if (fbApiKey.value.trim()) payload.fallback_api_key = fbApiKey.value.trim()
    if (webSearchKey.value.trim()) payload.web_search_key = webSearchKey.value.trim()
    const cfg = await saveAISettings(payload)
    savedKeyMasked.value = cfg.api_key_masked
    configured.value = cfg.configured
    apiKey.value = '' // 清空输入（已保存到后端，不回显）
    fbKeyMasked.value = cfg.fallback_api_key_masked || ''
    fbConfigured.value = !!cfg.fallback_configured
    fbApiKey.value = ''
    webKeyMasked.value = cfg.web_search_key_masked || ''
    webConfigured.value = !!cfg.web_search_configured
    webSearchKey.value = ''
    snapshotCurrent()
    notice.value = modelWarn
      ? '已保存。注意：该模型不在当前供应商列表中，可能已失效，建议点「测试连接」验证。'
      : '已保存并设为默认模型。api key 仅存后端；如需修改重新输入即可。'
  } catch (e: any) {
    error.value = e?.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function test() {
  error.value = ''
  notice.value = ''
  testResult.value = null
  testing.value = true
  try {
    testResult.value = await testAISettings({
      base_url: baseUrl.value.trim(),
      api_key: apiKey.value.trim(),
      model: model.value.trim(),
      max_tokens: maxTokens.value,
      temperature: temperature.value,
    })
  } catch (e: any) {
    testResult.value = { ok: false, message: e?.message || '连接测试失败' }
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <div class="settings-page">
    <PageBreadcrumb current="设置" />
    <h1 class="page-title">设置</h1>
    <p class="page-desc">配置课程内「AI 追问」与应用题批改所使用的模型。配置保存在后端，api key 不会显示在浏览器中。</p>

    <AppSpinner v-if="loading" text="加载设置…" />
    <AppError v-else-if="error && !baseUrl && !model" :message="error" @retry="reloadSettings" />

    <div v-else class="settings-stack">
      <!-- 当前配置状态条 -->
      <div class="status-bar">
        <span class="status-dot" :class="configured ? 'ok' : 'warn'"></span>
        <div class="status-info">
          <span class="status-label">{{ configured ? '已配置' : '未配置 API Key' }}</span>
          <span class="status-model">{{ model || '（未设置模型）' }}</span>
          <span class="status-url">{{ baseUrl }}</span>
        </div>
        <button class="btn btn-ghost status-test" :disabled="testing || saving" @click="test">
          {{ testing ? '测试中…' : '测试连接' }}
        </button>
      </div>

      <!-- 模型：主模型 + 备用模型（折叠） -->
      <section class="settings-card">
        <div class="card-head card-head-icon">
          <Bot :size="16" class="card-head-ico" />
          <div>
            <h2 class="card-title">模型</h2>
            <p class="card-desc">主模型用于日常回答；备用模型在主模型限流时自动顶上。</p>
          </div>
        </div>

        <div class="field-group">
          <label class="field-label" for="preset">供应商预设</label>
          <select id="preset" class="preset-select" :value="activePreset" @change="onPresetChange">
            <option v-for="p in PRESETS" :key="p.name" :value="p.name">{{ p.name }}</option>
          </select>
          <p class="field-help" v-if="activePresetHint">{{ activePresetHint }}</p>
        </div>

        <!-- 主模型（默认） -->
        <div class="section-block">
          <div class="section-title">主模型（默认）</div>

          <div class="field-group">
            <label class="field-label" for="base-url">Base URL</label>
            <input
              id="base-url"
              v-model="baseUrl"
              class="field-input"
              type="text"
              placeholder="https://open.bigmodel.cn/api/paas/v4"
              spellcheck="false"
            />
            <p class="field-help">OpenAI 兼容接口地址，末尾无需斜杠。</p>
          </div>

          <div class="field-row">
            <div class="field-group grow">
              <label class="field-label" for="model">模型名称</label>
              <div ref="modelPopRef" class="model-picker">
                <div class="model-input-wrap">
                  <input
                    id="model"
                    v-model="model"
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
                    @click="fetchModels"
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
                        :class="{ cur: m === model }"
                        @click="pickModel(m)"
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
              <label class="field-label" for="api-key">API Key</label>
              <input
                id="api-key"
                v-model="apiKey"
                class="field-input"
                type="password"
                placeholder="输入后保存到后端"
                autocomplete="off"
              />
              <p class="field-help" v-if="configured">
                已配置：<code class="masked">{{ savedKeyMasked }}</code>（重新输入可更换）
              </p>
              <p class="field-help help-warn" v-else>尚未配置 api key——AI 追问与应用题批改将不可用。</p>
            </div>
          </div>
        </div>

        <!-- 备用模型（折叠） -->
        <div class="section-block fb-block">
          <button
            type="button"
            class="fb-head"
            :aria-expanded="fbOpen"
            @click="fbOpen = !fbOpen"
          >
            <ChevronDown v-if="fbOpen" :size="14" class="fb-chev" />
            <ChevronRight v-else :size="14" class="fb-chev" />
            <span class="fb-title">备用模型（可选）</span>
            <span v-if="fbConfigured" class="fb-status ok">已配置 {{ fbKeyMasked }}</span>
            <span v-else class="fb-status">未配置</span>
          </button>
          <Transition name="fb">
            <div v-if="fbOpen" class="fb-body">
              <p class="field-help fb-desc">
                主模型限流（429）时自动切换，避免追问/批改中断。API Key 留空时复用主模型 key。
              </p>
              <div class="field-row">
                <div class="field-group grow">
                  <label class="field-label" for="fb-base-url">Base URL</label>
                  <input
                    id="fb-base-url"
                    v-model="fbBaseUrl"
                    class="field-input"
                    type="text"
                    placeholder="如 https://opencode.ai/zen/v1"
                    spellcheck="false"
                  />
                </div>
                <div class="field-group grow">
                  <label class="field-label" for="fb-model">模型名称</label>
                  <input
                    id="fb-model"
                    v-model="fbModel"
                    class="field-input"
                    type="text"
                    placeholder="如 deepseek-v4-flash-free"
                    spellcheck="false"
                  />
                </div>
              </div>
              <div class="field-row">
                <div class="field-group grow">
                  <label class="field-label" for="fb-api-key">API Key</label>
                  <input
                    id="fb-api-key"
                    v-model="fbApiKey"
                    class="field-input"
                    type="password"
                    placeholder="留空则复用主模型 key"
                    autocomplete="off"
                  />
                  <p class="field-help" v-if="fbConfigured">
                    已配置：<code class="masked">{{ fbKeyMasked }}</code>（重新输入可更换）
                  </p>
                </div>
                <div class="field-group grow">
                  <label class="field-label" for="fb-max-tokens">最大输出 token 数</label>
                  <input
                    id="fb-max-tokens"
                    v-model.number="fbMaxTokens"
                    class="field-input"
                    type="number"
                    min="16"
                    max="8192"
                    step="16"
                  />
                </div>
              </div>
            </div>
          </Transition>
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
            <p class="card-desc">控制 AI 回答的随机度与长度（作用于主模型）</p>
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
      <div v-if="notice" class="msg-notice">{{ notice }}</div>
      <div v-if="testResult" class="msg-test" :class="testResult.ok ? 'ok' : 'bad'">
        <strong class="test-mark"><Check v-if="testResult.ok" :size="14" /><X v-else :size="14" /> {{ testResult.message }}</strong>
        <div v-if="testResult.reply" class="test-reply">{{ testResult.reply }}</div>
      </div>

      <div class="actions-bar">
        <span v-if="dirty" class="dirty-hint">有未保存的修改</span>
        <div class="actions">
          <button class="btn btn-ghost" :disabled="testing || saving" @click="test">
            {{ testing ? '测试中…' : '测试连接' }}
          </button>
          <button class="btn btn-primary" :disabled="saving" @click="save">
            {{ saving ? '保存中…' : '保存设置' }}
          </button>
        </div>
      </div>
      <p class="actions-help">保存后，课程内的「AI 追问」与应用题批改立即使用该配置。</p>
    </div>
  </div>
</template>

<style scoped>
.settings-page { max-width: 960px; margin: 0 auto; }
.page-title { font-size: 24px; margin-bottom: 8px; }
.page-desc { color: var(--text-3); font-size: 14px; line-height: 1.7; margin-bottom: 20px; }

.settings-stack { display: flex; flex-direction: column; gap: 16px; }

/* 当前配置状态条 */
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
.field-help.help-warn { color: var(--warning); }
.masked { font-family: var(--font-mono); background: var(--bg-hover); padding: 1px 6px; border-radius: 4px; }

/* 卡片内分区（主模型 / 备用模型） */
.section-block {
  border-top: 1px solid var(--border);
  padding-top: 16px;
  margin-bottom: 18px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  margin-bottom: 12px;
}

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

/* 备用模型折叠面板 */
.fb-block { margin-bottom: 0; }
.fb-head {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  border: 1px solid var(--border);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  padding: 9px 12px;
  cursor: pointer;
  font-family: inherit;
  transition: border-color 0.12s, background 0.12s;
}
.fb-head:hover { border-color: var(--primary); background: var(--bg-hover); }
.fb-chev { color: var(--text-3); flex-shrink: 0; }
.fb-title { font-size: 13px; font-weight: 600; color: var(--text-1); }
.fb-status {
  margin-left: auto;
  font-size: 11.5px;
  color: var(--text-3);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fb-status.ok { color: var(--success); }
.fb-body {
  border: 1px solid var(--border);
  border-top: none;
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  background: color-mix(in srgb, var(--bg-hover) 40%, transparent);
  padding: 14px;
}
.fb-desc { margin-top: 0; margin-bottom: 12px; }
.fb-enter-active, .fb-leave-active { transition: opacity 0.15s, transform 0.15s; }
.fb-enter-from, .fb-leave-to { opacity: 0; transform: translateY(-6px); }

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

.msg-error, .msg-notice, .msg-test { font-size: 13px; padding: 9px 12px; border-radius: var(--radius-sm); line-height: 1.6; }
.msg-error { color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent); }
.msg-notice { color: var(--success, #16a34a); background: color-mix(in srgb, var(--success) 8%, transparent); }
.msg-test { border: 1px solid var(--border); }
.msg-test.ok { color: var(--success, #16a34a); background: color-mix(in srgb, var(--success) 6%, transparent); }
.msg-test.bad { color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger, #dc2626) 6%, transparent); }
.test-reply { margin-top: 4px; color: var(--text-2); }

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
}
</style>
