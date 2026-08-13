<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Check, Star, X } from 'lucide-vue-next'
import { fetchAISettings, saveAISettings, testAISettings } from '@/api'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'
import PageBreadcrumb from '@/components/common/PageBreadcrumb.vue'

// AI 模型设置页：连接配置（供应商/base_url/model/api key）+ 生成参数（temperature/max_tokens）
// 参考主流做法：分「连接」「生成」两个卡片分组，默认模型状态条置顶，测试/保存操作在底部。
// api key 只存后端，不回显；temperature 影响 AI 追问与应用题批改的随机度。

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
const baseUrl = ref('')
const model = ref('')
const apiKey = ref('')
const maxTokens = ref(1024)
const temperature = ref(0.4)

// 备用模型（主模型限流时自动切换）
const fbBaseUrl = ref('')
const fbModel = ref('')
const fbApiKey = ref('')
const fbMaxTokens = ref(1024)
const fbKeyMasked = ref('')
const fbConfigured = ref(false)

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const savedKeyMasked = ref('')
const configured = ref(false)
const error = ref('')
const notice = ref('')
const testResult = ref<{ ok: boolean; message: string; reply?: string } | null>(null)

const tempHint = computed(() => {
  const t = temperature.value
  if (t <= 0.2) return '接近确定性：答案稳定、适合追问知识点'
  if (t <= 0.7) return '平衡：日常讲解与批改的推荐区间'
  if (t <= 1.2) return '较有创造力：可能给出不同表述'
  return '高随机：创意优先，但可能不够严谨'
})

function applyPreset(p: ProviderPreset) {
  activePreset.value = p.name
  baseUrl.value = p.base_url
  model.value = p.model
  testResult.value = null
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
    // 匹配预设（按 base_url 前缀）
    const hit = PRESETS.find((p) => p.base_url && cfg.base_url.startsWith(p.base_url.split('/')[2] ?? ''))
    activePreset.value = hit?.name ?? (PRESETS[PRESETS.length - 1].name)
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
    const cfg = await saveAISettings(payload)
    savedKeyMasked.value = cfg.api_key_masked
    configured.value = cfg.configured
    apiKey.value = '' // 清空输入（已保存到后端，不回显）
    fbKeyMasked.value = cfg.fallback_api_key_masked || ''
    fbConfigured.value = !!cfg.fallback_configured
    fbApiKey.value = ''
    notice.value = '已保存并设为默认模型。api key 仅存后端；如需修改重新输入即可。'
  } catch (e: any) {
    error.value = e?.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function test() {
  error.value = ''
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
      <!-- 当前默认模型状态 -->
      <div class="default-banner">
        <span class="default-icon"><Star :size="14" /></span>
        <div class="default-info">
          <span class="default-label">当前默认模型</span>
          <span class="default-value">{{ model || '（未设置）' }}</span>
          <span class="default-url">{{ baseUrl }}</span>
        </div>
        <span v-if="configured" class="configured-badge">已配置</span>
        <span v-else class="configured-badge warn">未配置 key</span>
      </div>

      <!-- 连接配置 -->
      <section class="settings-card">
        <div class="card-head">
          <h2 class="card-title">连接配置</h2>
          <p class="card-desc">选择供应商预设或手动填写 OpenAI 兼容接口</p>
        </div>

        <div class="field-group">
          <label class="field-label">供应商预设</label>
          <div class="preset-grid">
            <button
              v-for="p in PRESETS"
              :key="p.name"
              type="button"
              class="preset-btn"
              :class="{ active: activePreset === p.name }"
              @click="applyPreset(p)"
            >
              <span class="preset-name">{{ p.name }}</span>
              <span class="preset-hint">{{ p.hint }}</span>
            </button>
          </div>
        </div>

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
            <input id="model" v-model="model" class="field-input" type="text" placeholder="glm-4-flash" spellcheck="false" />
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
            <p class="field-help" v-else>尚未配置 api key——AI 追问与应用题批改将不可用。</p>
          </div>
        </div>
      </section>

      <!-- 生成参数 -->
      <section class="settings-card">
        <div class="card-head">
          <h2 class="card-title">生成参数</h2>
          <p class="card-desc">控制 AI 回答的随机度与长度</p>
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

      <!-- 备用模型（fallback） -->
      <section class="settings-card">
        <div class="card-head">
          <h2 class="card-title">备用模型</h2>
          <p class="card-desc">主模型限流（429）时自动切换，避免追问/批改中断。留空则不启用。</p>
        </div>

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
            <input id="fb-model" v-model="fbModel" class="field-input" type="text" placeholder="如 deepseek-v4-flash-free" spellcheck="false" />
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
              placeholder="输入后保存到后端"
              autocomplete="off"
            />
            <p class="field-help" v-if="fbConfigured">
              已配置：<code class="masked">{{ fbKeyMasked }}</code>（重新输入可更换）
            </p>
            <p class="field-help" v-else>未配置备用模型——主模型限流时 AI 追问将不可用。</p>
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
      </section>

      <!-- 状态与操作 -->
      <div v-if="error" class="msg-error">{{ error }}</div>
      <div v-if="notice" class="msg-notice">{{ notice }}</div>
      <div v-if="testResult" class="msg-test" :class="testResult.ok ? 'ok' : 'bad'">
        <strong class="test-mark"><Check v-if="testResult.ok" :size="14" /><X v-else :size="14" /> {{ testResult.message }}</strong>
        <div v-if="testResult.reply" class="test-reply">{{ testResult.reply }}</div>
      </div>

      <div class="actions">
        <button class="btn btn-ghost" :disabled="testing || saving" @click="test">
          {{ testing ? '测试中…' : '测试连接' }}
        </button>
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存设置' }}
        </button>
      </div>
      <p class="actions-help">保存后，课程内的「AI 追问」与应用题批改立即使用该配置。</p>
    </div>
  </div>
</template>

<style scoped>
.settings-page { max-width: 720px; margin: 0 auto; }
.page-title { font-size: 24px; margin-bottom: 8px; }
.page-desc { color: var(--text-3); font-size: 14px; line-height: 1.7; margin-bottom: 20px; }

.settings-stack { display: flex; flex-direction: column; gap: 16px; }

.default-banner {
  display: flex; align-items: center; gap: 12px;
  background: var(--primary-soft);
  border: 1px solid color-mix(in srgb, var(--primary) 40%, transparent);
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
.default-icon { font-size: 20px; color: var(--primary); flex-shrink: 0; }
.default-info { display: flex; flex-direction: column; gap: 1px; min-width: 0; flex: 1; }
.default-label { font-size: 11px; color: var(--text-3); }
.default-value { font-size: 15px; font-weight: 700; color: var(--primary); }
.default-url { font-size: 11.5px; color: var(--text-3); font-family: var(--font-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.configured-badge {
  flex-shrink: 0; font-size: 12px; font-weight: 600;
  padding: 3px 10px; border-radius: 999px;
  background: var(--success-soft); color: var(--success);
}
.configured-badge.warn { background: var(--warning-soft); color: var(--warning); }

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

.preset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
.preset-btn {
  text-align: left; padding: 10px 12px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-card); cursor: pointer; transition: all 0.12s;
  display: flex; flex-direction: column; gap: 3px;
}
.preset-btn:hover { border-color: var(--primary); }
.preset-btn.active { border-color: var(--primary); background: var(--primary-soft); }
.preset-name { font-size: 13px; font-weight: 600; color: var(--text-1); }
.preset-hint { font-size: 11px; color: var(--text-3); line-height: 1.4; }

.slider-head { display: flex; align-items: baseline; justify-content: space-between; }
.slider-head .field-label { margin-bottom: 2px; }
.slider-value {
  font-size: 14px; font-weight: 700; color: var(--primary);
  font-variant-numeric: tabular-nums;
}
.slider { width: 100%; accent-color: var(--primary); cursor: pointer; margin: 6px 0 2px; }

.msg-error, .msg-notice, .msg-test { font-size: 13px; padding: 9px 12px; border-radius: var(--radius-sm); line-height: 1.6; }
.msg-error { color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent); }
.msg-notice { color: #16a34a; background: rgba(22, 163, 74, 0.08); }
.msg-test { border: 1px solid var(--border); }
.msg-test.ok { color: #16a34a; background: rgba(22, 163, 74, 0.06); }
.msg-test.bad { color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger, #dc2626) 6%, transparent); }
.test-reply { margin-top: 4px; color: var(--text-2); }

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
