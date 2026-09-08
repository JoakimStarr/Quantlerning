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

/** 注册一个可视化条目：懒加载模拟器组件并合并 title/desc，收敛注册样板 */
function def<T extends Component>(
  title: string,
  desc: string,
  loader: () => Promise<{ default: T }>,
): VizComponentDef {
  return { title, desc, comp: markRaw(defineAsyncComponent(loader)) }
}

const registry = {
  asset_map: def('资产风险-收益地图', '四大资产的风险-收益散点 + 股债组合线，拖动比例看分散化', () => import('../simulators/AssetMap.vue')),
  discount_curve: def('折现曲线', '拖动利率 r / 期数 n，实时看现值 PV 变化', () => import('../simulators/DiscountCurve.vue')),
  bond_duration: def('债券久期', '价格-利率曲线 + 久期敏感度', () => import('../simulators/BondDuration.vue')),
  convexity_demo: def('债券凸性', '真实曲线 vs 久期切线 vs 凸性二阶修正', () => import('../simulators/ConvexityDemo.vue')),
  yield_curve: def('国债收益率曲线', '真实中债 2Y/5Y/10Y/30Y，日期滑块看曲线形态与利差', () => import('../simulators/YieldCurve.vue')),
  ddm_valuation: def('DDM 估值滑块', 'D/r/g 拖拽，看戈登模型估值', () => import('../simulators/DdmValuation.vue')),
  dcf_sensitivity: def('DCF 估值敏感度', '拖动 5 年增长 g、WACC、永续增长 g∞，看企业价值爆炸与终值占比', () => import('../simulators/DcfSensitivity.vue')),
  capm_sml: def('CAPM / SML', '拖动 β，看期望收益在 SML 上移动', () => import('../simulators/CapmSml.vue')),
  beta_regression: def('真实 β 回归', '茅台 vs 沪深300 日收益散点 + OLS 回归线', () => import('../simulators/BetaRegression.vue')),
  macro_series: def('CPI/PPI 真实序列', '月度 CPI/PPI 同比，双线对比', () => import('../simulators/MacroSeries.vue')),
  dupont_demo: def('杜邦分解', 'ROE = 净利率 × 周转率 × 权益乘数，拖动三因素', () => import('../simulators/DuPontDemo.vue')),
  real_vs_log: def('复权与收益口径', '真实茅台：复权 vs 未复权、算术 vs 对数', () => import('../simulators/RealVsLog.vue')),
  vol_cluster: def('波动聚集', '真实茅台：收益柱 + 滚动波动曲线', () => import('../simulators/VolCluster.vue')),
  pe_distribution: def('全市场 PE 分布', '全市场快照 + 中位数/90 分位', () => import('../simulators/PeDistribution.vue')),
  compound_growth: def('单利 vs 复利', '拖动年化收益，看 30 年增长差距', () => import('../simulators/CompoundGrowth.vue')),
  compounding_frequency: def('复利频率对比', '名义利率相同，年/月/日/连续复利终值差异', () => import('../simulators/CompoundingFrequency.vue')),
  npv_cashflows: def('净现值 NPV', '拖动折现率，看各期现金流现值与 IRR', () => import('../simulators/NpvCashflows.vue')),
  normal_dist: def('正态分布', '拖动 μ/σ，观察密度曲线与 ±1/2/3σ 区间（68-95-99.7）', () => import('../simulators/NormalDist.vue')),
  binomial_dist: def('二项分布', '拖动 n/p，看概率柱状图与正态逼近（中心极限定理雏形）', () => import('../simulators/BinomialDist.vue')),
  venn_diagram: def('文氏图', '拖动 P(A)/P(B)/P(A∩B)，观察各区域概率与互斥/独立', () => import('../simulators/VennDiagram.vue')),
  distribution_explorer: def('分布浏览器', '切换伯努利/二项/泊松/均匀/正态，看 PMF/PDF 与期望、方差', () => import('../simulators/DistributionExplorer.vue')),
  bayes_update: def('贝叶斯更新', '拖动先验与新增观察，看先验如何演化为后验', () => import('../simulators/BayesUpdate.vue')),
  law_of_large_numbers: def('大数法则', '抛硬币模拟，样本均值收敛到真实概率', () => import('../simulators/LawOfLargeNumbers.vue')),
  confidence_interval: def('置信区间', '重复抽样看约 95% 的区间覆盖真值', () => import('../simulators/ConfidenceInterval.vue')),
  sampling_dist: def('抽样分布与中心极限定理', '右偏总体下，样本均值分布随 n 趋近正态', () => import('../simulators/SamplingDist.vue')),
  mle_demo: def('极大似然估计', '似然函数曲线，最高点即 MLE', () => import('../simulators/MleDemo.vue')),
  p_value: def('p 值与拒绝域', '拖动检验统计量 z，看 p 值与拒绝结论', () => import('../simulators/PValueDemo.vue')),
  chi_square: def('卡方分布', '自由度 k 决定形状，均值= k、方差= 2k', () => import('../simulators/ChiSquareDist.vue')),
  feature_pipeline: def('特征工程流水线', '真实收益 → MAD 去极值 → z-score 标准化', () => import('../simulators/FeaturePipeline.vue')),
  ic_distribution: def('因子 IC 分布', '161 个真实因子的 IC 直方图', () => import('../simulators/IcDistribution.vue')),
  factor_ic: def('因子 IC 序列', 'PE 因子月度 Rank IC（真实数据）', () => import('../simulators/PeIcSeries.vue')),
  layer_returns: def('PE 分层收益热力图', '全市场按 PE 分 5 组的下月收益热力图（真实数据）', () => import('../simulators/LayerReturns.vue')),
  ic_scatter: def('PE 因子 IC 散点', '月末 PE 百分位 vs 下月收益散点 + 趋势线（真实数据）', () => import('../simulators/IcScatter.vue')),
  layer_nav: def('PE 分层累计净值', 'Q1~Q5 月度调仓净值曲线（真实数据）', () => import('../simulators/LayerNav.vue')),
  factor_ic_turnover: def('因子 IC × 换手散点', '161 个真实因子的 IC 与换手率散点', () => import('../simulators/FactorIcTurnover.vue')),
  factor_corr: def('因子相关性矩阵', '同类因子高相关、跨类低相关（教学示意）', () => import('../simulators/FactorCorr.vue')),
  barra_attribution: def('Barra 归因演示', '总收益拆解：行业/风格贡献 vs 选股 alpha（教学示意）', () => import('../simulators/BarraAttribution.vue')),
  industry_pe: def('行业 PE 中位数', '同一交易日不同行业的估值中枢（真实数据）', () => import('../simulators/IndustryPe.vue')),
  factor_backtest_dashboard: def('多因子回测仪表盘', '真实多因子回测净值对比', () => import('../simulators/FactorBacktestDashboard.vue')),
  derivative_tangent: def('导数与切线', '输入任意函数，拖动切点看导数与切线斜率', () => import('../simulators/DerivativeTangent.vue')),
  linear_approx: def('微分线性近似', 'Δy 真实变化 vs dy 线性近似，误差随 dx 缩小', () => import('../simulators/LinearApprox.vue')),
  concavity_demo: def('凹凸与拐点', 'f、f″ 同图，标凹向区间、极值与拐点（符号微分）', () => import('../simulators/ConcavityDemo.vue')),
  taylor_series: def('泰勒展开逼近', '泰勒多项式逐阶逼近 f(x)，看展开点附近越贴越紧', () => import('../simulators/TaylorSeries.vue')),
  gradient_field: def('梯度场', 'f(x,y) 高度图 + 梯度箭头，偏导与梯度下降直观演示', () => import('../simulators/GradientField.vue')),
  gradient_descent: def('梯度下降（经典 3D 曲面）', '碗状曲面 + 红色下降路径 + 底面投影，学习率可调', () => import('../simulators/GradientDescent.vue')),
  integral_area: def('定积分（分割求和取极限）', '近似形状 + 收敛曲线逼近真值，左/右/中点/梯形/辛普森', () => import('../simulators/IntegralArea.vue')),
  num_integration: def('数值积分方法对比', '中点/梯形/辛普森同 n 精度对比 + 对数收敛阶曲线', () => import('../simulators/NumIntegration.vue')),
  eigen_demo: def('特征值与特征向量', '矩阵作用在单位圆上，看特征方向与伸缩', () => import('../simulators/EigenDemo.vue')),
  matrix_transform: def('矩阵变换', '2×2 矩阵作用：单位方格→平行四边形，基向量像=矩阵列', () => import('../simulators/MatrixTransform.vue')),
  regression_fit: def('线性回归拟合', '拖动参数看 OLS 拟合与残差', () => import('../simulators/RegressionFit.vue')),
  sharpe_simulator: def('Sharpe 滑块模拟器', '拖 μ/σ/rf，实时看夏普变化', () => import('../simulators/SharpeSimulator.vue')),
  mdd_simulator: def('最大回撤', '真实净值 + 回撤阴影，回本滑块', () => import('../simulators/MddSimulator.vue')),
  macd_simulator: def('MACD 参数拖拽', '快慢线参数实时重算', () => import('../simulators/MacdSimulator.vue')),
  rsi_simulator: def('RSI 超买超卖', '周期可调，实时看超买超卖', () => import('../simulators/RsiSimulator.vue')),
  strategy_signal: def('策略解剖', '信号 → 持仓 → 交易三段式（真实茅台）', () => import('../simulators/StrategySignal.vue')),
  trend_follow: def('趋势跟踪', '均线交叉 / 唐奇安通道回测对比', () => import('../simulators/TrendFollow.vue')),
  donchian_channel: def('唐奇安通道', '通道带 + 通道宽度 + 净值对比（真实茅台）', () => import('../simulators/DonchianChannel.vue')),
  bollinger_bands: def('布林带', '中轨 + ±kσ，触轨回归信号', () => import('../simulators/BollingerBands.vue')),
  financial_trends: def('财务比率趋势', '营收/净利柱状 + 可切换比率指标（真实财务数据）', () => import('../simulators/FinancialTrends.vue')),
  dupont_compare: def('三公司杜邦对比', '净利率/周转/乘数/ROE 真实杜邦分解对比（茅台/五粮液/招行）', () => import('../simulators/DuPontCompare.vue')),
  pe_band: def('PE 历史分位带', '个股 PE(TTM) 历史区间 + 均值带 + 当前分位（真实日线）', () => import('../simulators/PeBand.vue')),
  profit_cash_compare: def('利润 vs 现金流对比', '净利润与经营现金流逐年柱状对比 + 净现比（真实财务数据）', () => import('../simulators/ProfitCashCompare.vue')),
  moat_compare: def('护城河宽窄对比', '两家公司 ROE/毛利率十年双线对比（真实财务数据）', () => import('../simulators/MoatCompare.vue')),
  dcf_components: def('DCF 价值构成', '显式期现值 vs 终值现值占比（教学示意，可调参数）', () => import('../simulators/DcfComponents.vue')),
  momentum: def('时序动量', '过去 N 日涨则持有', () => import('../simulators/Momentum.vue')),
  backtest_engine: def('朴素回测重放', '逐日信号→持仓→净值', () => import('../simulators/BacktestEngine.vue')),
  strategy_compare: def('五策略对比', '同一窗口统一口径横向比较', () => import('../simulators/StrategyCompare.vue')),
  performance_dashboard: def('绩效仪表盘', '四类指标全表 + 指标对比条形图', () => import('../simulators/PerformanceDashboard.vue')),
  strategy_correlation: def('策略相关性矩阵', '三策略日收益相关 + 等权组合净值', () => import('../simulators/StrategyCorrelation.vue')),
  multiple_testing: def('多重检验演示', '试验越多，最优结果虚高越严重', () => import('../simulators/MultipleTesting.vue')),
  cost_impact: def('交易成本敏感性', '单边成本滑块，看收益侵蚀', () => import('../simulators/CostImpact.vue')),
  lookahead: def('前视偏差演示', '合规次日成交 vs 前视当日成交', () => import('../simulators/Lookahead.vue')),
  parameter_landscape: def('参数热力图', '快慢周期 × 年化收益', () => import('../simulators/ParameterLandscape.vue')),
  sawtooth: def('参数扫描：锯齿现象', '快线参数扫描年化柱状图：样本内锯齿 + 最优邻域高亮，样本外对照验证', () => import('../simulators/Sawtooth.vue')),
  random_walk: def('随机游走', '几何布朗运动 vs 真实茅台（示意 + 真实锚点）', () => import('../simulators/RandomWalk.vue')),
  option_payoff: def('期权/期货到期损益', '期货多空 × 看涨看跌 × 买入卖出六头寸损益图，含权利金与盈亏平衡点', () => import('../simulators/OptionPayoff.vue')),
  bs_price_slider: def('BS 定价滑块', 'S/K/σ/T/r 实时看涨看跌价格', () => import('../simulators/BSPricing.vue')),
  binomial_tree: def('二叉树定价', '步数滑块：二叉树收敛到 BS', () => import('../simulators/BinomialTree.vue')),
  monte_carlo_pricing: def('蒙特卡洛定价', '路径数滑块：MC 收敛 + 到期分布', () => import('../simulators/MonteCarlo.vue')),
  var_simulator: def('VaR 三种算法', '真实茅台收益：参数/历史/MC 对比', () => import('../simulators/VarSimulator.vue')),
  portfolio_var: def('组合 VaR 分散化', '真实 5 股：配对与权重滑块看相关性与分散化收益', () => import('../simulators/PortfolioVar.vue')),
  greeks_sensitivity: def('Greeks 敏感度曲线', 'Delta/Gamma/Vega/Theta/Rho 随 S 变化的形状', () => import('../simulators/GreeksSensitivity.vue')),
  vol_smile: def('波动率微笑/偏斜', 'IV vs 行权价曲线（教学示意）', () => import('../simulators/VolSmile.vue')),
  label_design: def('标签设计', '前瞻收益 > 阈值 → 上涨标签（茅台真实收益 + 周期/阈值滑块）', () => import('../simulators/LabelDesign.vue')),
  overfit_demo: def('多项式过拟合', '阶数滑块：训练误差↓ 验证误差先↓后↑（真实茅台净值）', () => import('../simulators/OverfitDemo.vue')),
  feature_importance: def('特征重要度', '逻辑回归标准化权重 |w|：哪个特征在驱动预测（真实训练）', () => import('../simulators/FeatureImportance.vue')),
  ml_backtest: def('ML 策略对比', 'ML 逻辑回归 vs 传统双均线 vs 买入持有（walk-forward 回测）', () => import('../simulators/MlBacktest.vue')),
  gradient_vanishing: def('梯度消失演示', 'tanh 导数连乘：RNN 梯度随步数指数衰减', () => import('../simulators/GradientVanishing.vue')),
  rl_trading_loop: def('RL 交易循环', '状态→动作→奖励 三要素（真实茅台日线，示意策略）', () => import('../simulators/RlTradingLoop.vue')),
  pipeline_architecture: def('完整 pipeline 架构图', '数据→因子→策略→组合→风控→实盘 六环节交互图', () => import('../simulators/PipelineArchitecture.vue')),
  frontier: def('有效前沿拖拽', '5 股真实收益：权重滑块 → 实时前沿', () => import('../simulators/EfficientFrontier.vue')),
  risk_parity: def('风险平价', '波动率平价 vs 等权 vs 倒数波动加权（真实 5 股）', () => import('../simulators/RiskParity.vue')),
  black_litterman: def('Black-Litterman', '观点 + 置信度 → 后验权重（真实协方差）', () => import('../simulators/BlackLitterman.vue')),
  pair_trading: def('配对交易', '真实配对协整检验 + 价差 z-score 均值回归', () => import('../simulators/PairTrading.vue')),
  portfolio_risk: def('组合风控仪表盘', '压力测试 + 止损阈值（真实组合净值）', () => import('../simulators/PortfolioRisk.vue')),
  code_sandbox: def('代码练习沙箱', '提交 Python 代码，受限环境执行 + get_daily 只读真实行情', () => import('../simulators/CodeSandbox.vue')),
} satisfies Record<string, VizComponentDef>

/** 已注册的组件名（Markdown 中的 viz 组件名须落在其中） */
export type VizKey = keyof typeof registry
export const vizRegistry: Record<VizKey, VizComponentDef> = registry
