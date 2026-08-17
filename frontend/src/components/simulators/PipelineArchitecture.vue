<script setup lang="ts">
// 完整量化 pipeline 架构图（教学示意）：数据→因子→策略→组合→风控→实盘 六环节
// 教学点：① 六环节层层递进，前一环输出是后一环输入；
// ② 误差沿链条放大（错误传导方向）；③ 每环节对应的章节与真实数据
import { ref, computed } from 'vue'

interface Stage {
  id: string
  label: string
  sub: string
  chapter: string
  data: string
  check: string
  error: string
}

const stages: Stage[] = [
  {
    id: 'data',
    label: '数据',
    sub: '真实行情',
    chapter: '第一章',
    data: 'quantlab 库，茅台 2024 复权口径',
    check: '复权、不含首日、口径统一',
    error: '数据口径错（未复权）→ 全部后续计算失真',
  },
  {
    id: 'factor',
    label: '因子 / 特征',
    sub: '有预测力的输入',
    chapter: '第三章 / 第五章',
    data: '161 个真实因子 + 8 个 ML 特征',
    check: 'IC/ICIR 检验、中性化、防前视',
    error: '因子选错（过拟合）→ 模型学到噪音',
  },
  {
    id: 'strategy',
    label: '策略 / 模型',
    sub: '从信号到规则',
    chapter: '第二章 / 第五章',
    data: '均线/动量/回归 + 逻辑回归',
    check: '回测无前视、成本已计入',
    error: '模型预测不准 → 组合最优化是对错误预期的精确求解',
  },
  {
    id: 'portfolio',
    label: '组合配置',
    sub: '把资产拼成组合',
    chapter: '第六章',
    data: '5 股 2024 真实收益矩阵',
    check: '有效前沿/风险平价/BL 依据',
    error: '配置再准，无风控 → 一次极端行情清零积累',
  },
  {
    id: 'risk',
    label: '风险控制',
    sub: '守住亏损底线',
    chapter: '第六章',
    data: '止损/压力测试/仓位管理',
    check: '全部代码化、压测通过',
    error: '风控失效 → 回撤失控，实盘出局',
  },
  {
    id: 'live',
    label: '执行 / 实盘',
    sub: '从模拟到真金白银',
    chapter: '第六章',
    data: '模拟盘 → 券商 API → 小资金试运行',
    check: '模拟盘 ≥1 个月、API 只读验证、告警通道',
    error: '回测能赚 ≠ 实盘能赚——成交假设理想化',
  },
]

const active = ref<string | null>(null)
const showError = ref(false)

function toggle(id: string) {
  active.value = active.value === id ? null : id
}

const activeStage = computed(() => stages.find((s) => s.id === active.value) ?? null)
</script>

<template>
  <div class="pipeline">
    <!-- 架构图：六环节串联 -->
    <div class="flow">
      <template v-for="(s, i) in stages" :key="s.id">
        <div
          class="stage"
          :class="['st-' + s.id, { on: active === s.id, err: showError }]"
          @click="toggle(s.id)"
        >
          <div class="idx">{{ i + 1 }}</div>
          <div class="label">{{ s.label }}</div>
          <div class="sub">{{ s.sub }}</div>
          <div class="chapter">{{ s.chapter }}</div>
        </div>
        <div v-if="i < stages.length - 1" class="arrow" :class="{ 'arrow-err': showError }">→</div>
      </template>
    </div>

    <div class="toggles">
      <label class="chk">
        <input type="checkbox" v-model="showError" />
        显示错误传导方向（前一环误差放大到后一环）
      </label>
    </div>

    <!-- 环节详情 -->
    <div v-if="activeStage" class="detail">
      <h4 class="d-title">{{ activeStage.label }} <span class="d-ch">{{ activeStage.chapter }}</span></h4>
      <p class="d-row"><b>真实数据：</b>{{ activeStage.data }}</p>
      <p class="d-row"><b>检查项：</b>{{ activeStage.check }}</p>
      <p class="d-row d-err"><b>这环出错的后果：</b>{{ activeStage.error }}</p>
    </div>
    <div v-else class="detail hint">点击上方任一环节查看细节；打开「错误传导方向」看每一环出错如何连累下游。</div>
  </div>
</template>

<style scoped>
.pipeline { padding: 16px; }
.flow { display: flex; align-items: stretch; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.stage {
  flex: 1 1 120px; min-width: 110px;
  border: 1.5px solid var(--border, rgba(128,128,128,0.35));
  border-radius: 10px; padding: 10px 8px; cursor: pointer;
  background: var(--bg-hover, rgba(128,128,128,0.08));
  text-align: center; transition: all 0.15s;
}
.stage:hover { transform: translateY(-2px); border-color: var(--primary); }
.stage.on { border-color: var(--primary); background: color-mix(in srgb, var(--primary) 12%, transparent); }
.stage.err { border-color: var(--danger, #dc2626); }
.idx {
  width: 22px; height: 22px; line-height: 22px; margin: 0 auto 6px;
  border-radius: 50%; font-size: 12px; font-weight: 700;
  color: #fff; background: var(--primary);
}
.stage.err .idx { background: var(--danger, #dc2626); }
.label { font-size: 14px; font-weight: 600; color: var(--text-1); }
.sub { font-size: 11.5px; color: var(--text-3); margin-top: 2px; }
.chapter { font-size: 11px; color: var(--primary); margin-top: 4px; }
.arrow { align-self: center; font-size: 18px; color: var(--text-3); flex: 0 0 auto; }
.arrow-err { color: var(--danger, #dc2626); font-weight: 700; }
.toggles { margin-bottom: 12px; }
.chk { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--text-2); cursor: pointer; }
.detail {
  border: 1px solid var(--border, rgba(128,128,128,0.3));
  border-radius: 10px; padding: 12px 14px; font-size: 13px; line-height: 1.7;
}
.detail.hint { color: var(--text-3); }
.d-title { margin: 0 0 8px; font-size: 15px; }
.d-ch { font-size: 12px; color: var(--primary); margin-left: 6px; }
.d-row { margin: 4px 0; color: var(--text-2); }
.d-err { color: var(--danger, #dc2626); }
</style>
