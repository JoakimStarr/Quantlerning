<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchAISettings, saveAISettings, testAISettings } from '@/api'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'

// AI 模型设置页：选择供应商预设（自动填 base_url/model）或完全自定义，
// 填 api_key 后保存到后端（key 只存后端，不回显），并可测试连接。

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
    model: 'glm-4-flash',
    hint: '智谱 AI 开放平台，glm-4-flash 免费档',
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

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const savedKeyMasked = ref('')
const configured = ref(false)
const error = ref('')
const notice = ref('')
const testResult = ref<{ ok: boolean; message: string; reply?: string } | null>(null)

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
    savedKeyMasked.value = cfg.api_key_masked
    configured.value = cfg.configured
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
    const payload: { base_url: string; model: string; max_tokens: number; api_key?: string } = {
      base_url: baseUrl.value.trim(),
      model: model.value.trim(),
      max_tokens: maxTokens.value,
    }
    // api_key 未输入 → 不发该字段，保留后端已保存的 key（避免误删）
    if (apiKey.value.trim()) payload.api_key = apiKey.value.trim()
    const cfg = await saveAISettings(payload)
    savedKeyMasked.value = cfg.api_key_masked
    configured.value = cfg.configured
    apiKey.value = '' // 清空输入（已保存到后端，不回显）
    notice.value = '已保存并设为默认模型。api key 仅存后端；如需改 key 重新输入即可。'
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
    <h1 class="page-title">设置</h1>
    <p class="page-desc">配置 AI 模型（用于课程内「AI 追问」与应用题批改）。配置保存在后端，api key 不会显示在浏览器中。</p>

    <AppSpinner v-if="loading" text="加载设置…" />
    <AppError v-else-if="error && !baseUrl && !model" :message="error" @retry="reloadSettings" />

    <div v-else class="settings-card">
      <!-- 当前默认模型状态 -->
      <div class="default-banner">
        <span class="default-icon">★</span>
        <div class="default-info">
          <span class="default-label">当前默认模型</span>
          <span class="default-value">{{ model || '（未设置）' }}</span>
          <span class="default-url">{{ baseUrl }}</span>
        </div>
      </div>

      <!-- 供应商预设 -->
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

      <!-- base_url -->
      <div class="field-group">
        <label class="field-label" for="base-url">Base URL</label>
        <input
          id="base-url"
          v-model="baseUrl"
          class="field-input"
          type="text"
          placeholder="https://open.bigmodel.cn/api/paas/v4"
        />
        <p class="field-help">OpenAI 兼容接口地址，末尾无需斜杠。</p>
      </div>

      <!-- model -->
      <div class="field-group">
        <label class="field-label" for="model">模型名称</label>
        <input id="model" v-model="model" class="field-input" type="text" placeholder="glm-4-flash" />
      </div>

      <!-- api_key -->
      <div class="field-group">
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
          已配置：<code class="masked">{{ savedKeyMasked }}</code>（如需修改，直接输入新 key 保存即可）
        </p>
        <p class="field-help" v-else>尚未配置 api key——AI 追问与应用题批改将不可用。</p>
      </div>

      <!-- max_tokens -->
      <div class="field-group">
        <label class="field-label" for="max-tokens">最大输出 token 数</label>
        <input id="max-tokens" v-model.number="maxTokens" class="field-input" type="number" min="16" max="8192" step="16" />
      </div>

      <div v-if="error" class="msg-error">{{ error }}</div>
      <div v-if="notice" class="msg-notice">{{ notice }}</div>
      <div v-if="testResult" class="msg-test" :class="testResult.ok ? 'ok' : 'bad'">
        <strong>{{ testResult.ok ? '✓' : '✗' }} {{ testResult.message }}</strong>
        <div v-if="testResult.reply" class="test-reply">{{ testResult.reply }}</div>
      </div>

      <div class="actions">
        <button class="btn btn-ghost" :disabled="testing || saving" @click="test">
          {{ testing ? '测试中…' : '测试连接' }}
        </button>
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存并设为默认模型' }}
        </button>
      </div>
      <p class="actions-help">保存后，课程内的「AI 追问」与应用题批改立即使用该默认模型。</p>
    </div>
  </div>
</template>

<style scoped>
.settings-page { max-width: 680px; margin: 0 auto; }
.page-title { font-size: 24px; margin-bottom: 8px; }
.page-desc { color: var(--text-3); font-size: 14px; line-height: 1.7; margin-bottom: 20px; }

.status { padding: 40px; text-align: center; color: var(--text-3); }

.settings-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 24px;
}

.default-banner {
  display: flex; align-items: center; gap: 12px;
  background: var(--primary-soft);
  border: 1px solid color-mix(in srgb, var(--primary) 40%, transparent);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  margin-bottom: 22px;
}
.default-icon { font-size: 20px; color: var(--primary); flex-shrink: 0; }
.default-info { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.default-label { font-size: 11px; color: var(--text-3); }
.default-value { font-size: 15px; font-weight: 700; color: var(--primary); }
.default-url { font-size: 11.5px; color: var(--text-3); font-family: var(--font-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.field-group { margin-bottom: 18px; }
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

.msg-error, .msg-notice, .msg-test { font-size: 13px; padding: 9px 12px; border-radius: var(--radius-sm); margin-bottom: 14px; line-height: 1.6; }
.msg-error { color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent); }
.msg-notice { color: #16a34a; background: rgba(22, 163, 74, 0.08); }
.msg-test { border: 1px solid var(--border); }
.msg-test.ok { color: #16a34a; background: rgba(22, 163, 74, 0.06); }
.msg-test.bad { color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger, #dc2626) 6%, transparent); }
.test-reply { margin-top: 4px; color: var(--text-2); }

.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 6px; }
.actions-help { font-size: 12px; color: var(--text-3); text-align: right; margin: 8px 0 0; }
.btn { font-size: 13px; padding: 7px 18px; border-radius: var(--radius-sm); cursor: pointer; border: none; }
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost { background: none; border: 1px solid var(--border); color: var(--text-2); }
.btn-ghost:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
