/**
 * 可视化组件注册表：组件名 → 组件定义。
 *
 * 已实现的组件挂载真实模拟器；未实现的显示插图占位（带图注）。
 * 注册表独立成模块，供 VizBlock 渲染与 MarkdownRenderer 的组件名类型共用，
 * 这样 Markdown 里写了未注册的组件名，vue-tsc 即可报错。
 */
import { defineAsyncComponent, markRaw, type Component } from 'vue'

export interface VizComponentDef {
  title: string
  desc: string
  comp?: Component
}

const registry = {
  discount_curve: {
    title: '折现曲线',
    desc: '拖动利率 r / 期数 n，实时看现值 PV 变化',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/DiscountCurve.vue'))),
  },
  bond_duration: {
    title: '债券久期',
    desc: '价格-利率曲线 + 久期敏感度',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/BondDuration.vue'))),
  },
  convexity_demo: {
    title: '债券凸性',
    desc: '真实曲线 vs 久期切线 vs 凸性二阶修正',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/ConvexityDemo.vue'))),
  },
  yield_curve: {
    title: '国债收益率曲线',
    desc: '真实中债 2Y/5Y/10Y/30Y，日期滑块看曲线形态与利差',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/YieldCurve.vue'))),
  },
  ddm_valuation: {
    title: 'DDM 估值滑块',
    desc: 'D/r/g 拖拽，看戈登模型估值',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/DdmValuation.vue'))),
  },
  dcf_sensitivity: {
    title: 'DCF 估值敏感度',
    desc: '拖动 5 年增长 g、WACC、永续增长 g∞，看企业价值爆炸与终值占比',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/DcfSensitivity.vue'))),
  },
  capm_sml: {
    title: 'CAPM / SML',
    desc: '拖动 β，看期望收益在 SML 上移动',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/CapmSml.vue'))),
  },
  beta_regression: {
    title: '真实 β 回归',
    desc: '茅台 vs 沪深300 日收益散点 + OLS 回归线',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/BetaRegression.vue'))),
  },
  macro_series: {
    title: 'CPI/PPI 真实序列',
    desc: 'quantlab 库月度 CPI/PPI 同比，双线对比',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/MacroSeries.vue'))),
  },
  dupont_demo: {
    title: '杜邦分解',
    desc: 'ROE = 净利率 × 周转率 × 权益乘数，拖动三因素',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/DuPontDemo.vue'))),
  },
  real_vs_log: {
    title: '复权与收益口径',
    desc: '真实茅台：复权 vs 未复权、算术 vs 对数',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/RealVsLog.vue'))),
  },
  vol_cluster: {
    title: '波动聚集',
    desc: '真实茅台：收益柱 + 滚动波动曲线',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/VolCluster.vue'))),
  },
  pe_distribution: {
    title: '全市场 PE 分布',
    desc: '真实 quantlab 数据快照 + 中位数/90 分位',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/PeDistribution.vue'))),
  },
  compound_growth: {
    title: '单利 vs 复利',
    desc: '拖动年化收益，看 30 年增长差距',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/CompoundGrowth.vue'))),
  },
  compounding_frequency: {
    title: '复利频率对比',
    desc: '名义利率相同，年/月/日/连续复利终值差异',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/CompoundingFrequency.vue'))),
  },
  npv_cashflows: {
    title: '净现值 NPV',
    desc: '拖动折现率，看各期现金流现值与 IRR',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/NpvCashflows.vue'))),
  },
  normal_dist: {
    title: '正态分布',
    desc: '拖动 μ/σ，观察密度曲线与 ±1/2/3σ 区间（68-95-99.7）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/NormalDist.vue'))),
  },
  binomial_dist: {
    title: '二项分布',
    desc: '拖动 n/p，看概率柱状图与正态逼近（中心极限定理雏形）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/BinomialDist.vue'))),
  },
  venn_diagram: {
    title: '文氏图',
    desc: '拖动 P(A)/P(B)/P(A∩B)，观察各区域概率与互斥/独立',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/VennDiagram.vue'))),
  },
  distribution_explorer: {
    title: '分布浏览器',
    desc: '切换伯努利/二项/泊松/均匀/正态，看 PMF/PDF 与期望、方差',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/DistributionExplorer.vue'))),
  },
  bayes_update: {
    title: '贝叶斯更新',
    desc: '拖动先验与新增观察，看先验如何演化为后验',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/BayesUpdate.vue'))),
  },
  law_of_large_numbers: {
    title: '大数法则',
    desc: '抛硬币模拟，样本均值收敛到真实概率',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/LawOfLargeNumbers.vue'))),
  },
  confidence_interval: {
    title: '置信区间',
    desc: '重复抽样看约 95% 的区间覆盖真值',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/ConfidenceInterval.vue'))),
  },
  sampling_dist: {
    title: '抽样分布与中心极限定理',
    desc: '右偏总体下，样本均值分布随 n 趋近正态',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/SamplingDist.vue'))),
  },
  mle_demo: {
    title: '极大似然估计',
    desc: '似然函数曲线，最高点即 MLE',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/MleDemo.vue'))),
  },
  p_value: {
    title: 'p 值与拒绝域',
    desc: '拖动检验统计量 z，看 p 值与拒绝结论',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/PValueDemo.vue'))),
  },
  chi_square: {
    title: '卡方分布',
    desc: '自由度 k 决定形状，均值= k、方差= 2k',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/ChiSquareDist.vue'))),
  },
  feature_pipeline: {
    title: '特征工程流水线',
    desc: '真实收益 → MAD 去极值 → z-score 标准化',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/FeaturePipeline.vue'))),
  },
  ic_distribution: {
    title: '因子 IC 分布',
    desc: '161 个真实因子的 IC 直方图',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/IcDistribution.vue'))),
  },
  factor_ic: {
    title: '因子 IC 序列',
    desc: 'PE 因子月度 Rank IC（真实数据）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/PeIcSeries.vue'))),
  },
  layer_returns: {
    title: 'PE 分层收益热力图',
    desc: '全市场按 PE 分 5 组的下月收益热力图（真实数据）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/LayerReturns.vue'))),
  },
  ic_scatter: {
    title: 'PE 因子 IC 散点',
    desc: '月末 PE 百分位 vs 下月收益散点 + 趋势线（真实数据）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/IcScatter.vue'))),
  },
  layer_nav: {
    title: 'PE 分层累计净值',
    desc: 'Q1~Q5 月度调仓净值曲线（真实数据）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/LayerNav.vue'))),
  },
  factor_ic_turnover: {
    title: '因子 IC × 换手散点',
    desc: '161 个真实因子的 IC 与换手率散点',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/FactorIcTurnover.vue'))),
  },
  factor_corr: {
    title: '因子相关性矩阵',
    desc: '同类因子高相关、跨类低相关（教学示意）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/FactorCorr.vue'))),
  },
  barra_attribution: {
    title: 'Barra 归因演示',
    desc: '总收益拆解：行业/风格贡献 vs 选股 alpha（教学示意）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/BarraAttribution.vue'))),
  },
  industry_pe: {
    title: '行业 PE 中位数',
    desc: '同一交易日不同行业的估值中枢（真实数据）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/IndustryPe.vue'))),
  },
  factor_backtest_dashboard: {
    title: '多因子回测仪表盘',
    desc: 'QuantLab 真实因子回测净值对比',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/FactorBacktestDashboard.vue'))),
  },
  derivative_tangent: {
    title: '导数与切线',
    desc: '输入任意函数，拖动切点看导数与切线斜率',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/DerivativeTangent.vue'))),
  },
  linear_approx: {
    title: '微分线性近似',
    desc: 'Δy 真实变化 vs dy 线性近似，误差随 dx 缩小',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/LinearApprox.vue'))),
  },
  concavity_demo: {
    title: '凹凸与拐点',
    desc: 'f、f″ 同图，标凹向区间、极值与拐点（符号微分）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/ConcavityDemo.vue'))),
  },
  taylor_series: {
    title: '泰勒展开逼近',
    desc: '泰勒多项式逐阶逼近 f(x)，看展开点附近越贴越紧',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/TaylorSeries.vue'))),
  },
  gradient_field: {
    title: '梯度场',
    desc: 'f(x,y) 高度图 + 梯度箭头，偏导与梯度下降直观演示',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/GradientField.vue'))),
  },
  gradient_descent: {
    title: '梯度下降（经典 3D 曲面）',
    desc: '碗状曲面 + 红色下降路径 + 底面投影，学习率可调',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/GradientDescent.vue'))),
  },
  integral_area: {
    title: '定积分（分割求和取极限）',
    desc: '近似形状 + 收敛曲线逼近真值，左/右/中点/梯形/辛普森',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/IntegralArea.vue'))),
  },
  num_integration: {
    title: '数值积分方法对比',
    desc: '中点/梯形/辛普森同 n 精度对比 + 对数收敛阶曲线',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/NumIntegration.vue'))),
  },
  eigen_demo: {
    title: '特征值与特征向量',
    desc: '矩阵作用在单位圆上，看特征方向与伸缩',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/EigenDemo.vue'))),
  },
  matrix_transform: {
    title: '矩阵变换',
    desc: '2×2 矩阵作用：单位方格→平行四边形，基向量像=矩阵列',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/MatrixTransform.vue'))),
  },
  regression_fit: {
    title: '线性回归拟合',
    desc: '拖动参数看 OLS 拟合与残差',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/RegressionFit.vue'))),
  },
  sharpe_simulator: {
    title: 'Sharpe 滑块模拟器',
    desc: '拖 μ/σ/rf，实时看夏普变化',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/SharpeSimulator.vue'))),
  },
  mdd_simulator: {
    title: '最大回撤',
    desc: '真实净值 + 回撤阴影，回本滑块',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/MddSimulator.vue'))),
  },
  macd_simulator: {
    title: 'MACD 参数拖拽',
    desc: '快慢线参数实时重算',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/MacdSimulator.vue'))),
  },
  rsi_simulator: {
    title: 'RSI 超买超卖',
    desc: '周期可调，实时看超买超卖',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/RsiSimulator.vue'))),
  },
  strategy_signal: {
    title: '策略解剖',
    desc: '信号 → 持仓 → 交易三段式（真实茅台）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/StrategySignal.vue'))),
  },
  trend_follow: {
    title: '趋势跟踪',
    desc: '均线交叉 / 唐奇安通道回测对比',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/TrendFollow.vue'))),
  },
  donchian_channel: {
    title: '唐奇安通道',
    desc: '通道带 + 通道宽度 + 净值对比（真实茅台）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/DonchianChannel.vue'))),
  },
  bollinger_bands: {
    title: '布林带',
    desc: '中轨 + ±kσ，触轨回归信号',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/BollingerBands.vue'))),
  },
  financial_trends: {
    title: '财务比率趋势',
    desc: '营收/净利柱状 + 可切换比率指标（真实 quantlab 财务数据）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/FinancialTrends.vue'))),
  },
  dupont_compare: {
    title: '三公司杜邦对比',
    desc: '净利率/周转/乘数/ROE 真实杜邦分解对比（茅台/五粮液/招行）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/DuPontCompare.vue'))),
  },
  pe_band: {
    title: 'PE 历史分位带',
    desc: '个股 PE(TTM) 历史区间 + 均值带 + 当前分位（真实 quantlab 日线）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/PeBand.vue'))),
  },
  profit_cash_compare: {
    title: '利润 vs 现金流对比',
    desc: '净利润与经营现金流逐年柱状对比 + 净现比（真实 quantlab 财务数据）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/ProfitCashCompare.vue'))),
  },
  moat_compare: {
    title: '护城河宽窄对比',
    desc: '两家公司 ROE/毛利率十年双线对比（真实 quantlab 财务数据）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/MoatCompare.vue'))),
  },
  dcf_components: {
    title: 'DCF 价值构成',
    desc: '显式期现值 vs 终值现值占比（教学示意，可调参数）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/DcfComponents.vue'))),
  },
  momentum: {
    title: '时序动量',
    desc: '过去 N 日涨则持有',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/Momentum.vue'))),
  },
  backtest_engine: {
    title: '朴素回测重放',
    desc: '逐日信号→持仓→净值',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/BacktestEngine.vue'))),
  },
  strategy_compare: {
    title: '五策略对比',
    desc: '同一窗口统一口径横向比较',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/StrategyCompare.vue'))),
  },
  performance_dashboard: {
    title: '绩效仪表盘',
    desc: '四类指标全表 + 指标对比条形图',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/PerformanceDashboard.vue'))),
  },
  strategy_correlation: {
    title: '策略相关性矩阵',
    desc: '三策略日收益相关 + 等权组合净值',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/StrategyCorrelation.vue'))),
  },
  multiple_testing: {
    title: '多重检验演示',
    desc: '试验越多，最优结果虚高越严重',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/MultipleTesting.vue'))),
  },
  cost_impact: {
    title: '交易成本敏感性',
    desc: '单边成本滑块，看收益侵蚀',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/CostImpact.vue'))),
  },
  lookahead: {
    title: '前视偏差演示',
    desc: '合规次日成交 vs 前视当日成交',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/Lookahead.vue'))),
  },
  parameter_landscape: {
    title: '参数热力图',
    desc: '快慢周期 × 年化收益',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/ParameterLandscape.vue'))),
  },
  random_walk: {
    title: '随机游走',
    desc: '几何布朗运动 vs 真实茅台（示意 + 真实锚点）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/RandomWalk.vue'))),
  },
  bs_price_slider: {
    title: 'BS 定价滑块',
    desc: 'S/K/σ/T/r 实时看涨看跌价格',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/BSPricing.vue'))),
  },
  binomial_tree: {
    title: '二叉树定价',
    desc: '步数滑块：二叉树收敛到 BS',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/BinomialTree.vue'))),
  },
  monte_carlo_pricing: {
    title: '蒙特卡洛定价',
    desc: '路径数滑块：MC 收敛 + 到期分布',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/MonteCarlo.vue'))),
  },
  var_simulator: {
    title: 'VaR 三种算法',
    desc: '真实茅台收益：参数/历史/MC 对比',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/VarSimulator.vue'))),
  },
  greeks_sensitivity: {
    title: 'Greeks 敏感度曲线',
    desc: 'Delta/Gamma/Vega/Theta/Rho 随 S 变化的形状',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/GreeksSensitivity.vue'))),
  },
  vol_smile: {
    title: '波动率微笑/偏斜',
    desc: 'IV vs 行权价曲线（教学示意）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/VolSmile.vue'))),
  },
  label_design: {
    title: '标签设计',
    desc: '前瞻收益 > 阈值 → 上涨标签（茅台真实收益 + 周期/阈值滑块）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/LabelDesign.vue'))),
  },
  overfit_demo: {
    title: '多项式过拟合',
    desc: '阶数滑块：训练误差↓ 验证误差先↓后↑（真实茅台净值）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/OverfitDemo.vue'))),
  },
  feature_importance: {
    title: '特征重要度',
    desc: '逻辑回归标准化权重 |w|：哪个特征在驱动预测（真实训练）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/FeatureImportance.vue'))),
  },
  ml_backtest: {
    title: 'ML 策略对比',
    desc: 'ML 逻辑回归 vs 传统双均线 vs 买入持有（walk-forward 回测）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/MlBacktest.vue'))),
  },
  gradient_vanishing: {
    title: '梯度消失演示',
    desc: 'tanh 导数连乘：RNN 梯度随步数指数衰减',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/GradientVanishing.vue'))),
  },
  rl_trading_loop: {
    title: 'RL 交易循环',
    desc: '状态→动作→奖励 三要素（真实茅台日线，示意策略）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/RlTradingLoop.vue'))),
  },
  pipeline_architecture: {
    title: '完整 pipeline 架构图',
    desc: '数据→因子→策略→组合→风控→实盘 六环节交互图',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/PipelineArchitecture.vue'))),
  },
  frontier: {
    title: '有效前沿拖拽',
    desc: '5 股真实收益：权重滑块 → 实时前沿',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/EfficientFrontier.vue'))),
  },
  risk_parity: {
    title: '风险平价',
    desc: '波动率平价 vs 等权 vs 倒数波动加权（真实 5 股）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/RiskParity.vue'))),
  },
  black_litterman: {
    title: 'Black-Litterman',
    desc: '观点 + 置信度 → 后验权重（真实协方差）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/BlackLitterman.vue'))),
  },
  pair_trading: {
    title: '配对交易',
    desc: '真实配对协整检验 + 价差 z-score 均值回归',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/PairTrading.vue'))),
  },
  portfolio_risk: {
    title: '组合风控仪表盘',
    desc: '压力测试 + 止损阈值（真实组合净值）',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/PortfolioRisk.vue'))),
  },
  code_sandbox: {
    title: '代码练习沙箱',
    desc: '提交 Python 代码，受限环境执行 + get_daily 只读真实行情',
    comp: markRaw(defineAsyncComponent(() => import('../simulators/CodeSandbox.vue'))),
  },
} satisfies Record<string, VizComponentDef>

/** 已注册的组件名（Markdown 中的 viz 组件名须落在其中） */
export type VizKey = keyof typeof registry
export const vizRegistry: Record<VizKey, VizComponentDef> = registry
