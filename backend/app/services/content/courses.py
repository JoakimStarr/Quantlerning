"""课程元数据（静态定义）。

课程内容将逐步迁移到 backend/app/content/phase*/ 的 Markdown 文件。
此处先提供各阶段与课程的结构化元数据，供课程地图渲染。
"""

COURSES = [
    {
        "phase": 0,
        "title": "数学与编程基础",
        "subtitle": "前置知识：微积分 / 线性代数 / 概率论 / 数理统计 / 计量 / Python",
        "status": "prereq",
        "weeks": "-",
        "lessons": [
            # 先微积分与线性代数（概率/统计要用到积分与矩阵），再概率论→数理统计→计量
            {"id": "p0-l4", "title": "微积分", "concepts": ["导数", "积分", "梯度"]},
            {"id": "p0-l3", "title": "线性代数", "concepts": ["矩阵", "特征值", "正定性"]},
            {"id": "p0-l1", "title": "概率论", "concepts": ["随机变量", "分布", "期望", "方差"]},
            {"id": "p0-l2", "title": "数理统计", "concepts": ["估计", "假设检验", "置信区间"]},
            {"id": "p0-l5", "title": "计量经济学", "concepts": ["回归", "OLS", "平稳性"]},
            {"id": "p0-l6", "title": "Python 与 Pandas", "concepts": ["Pandas", "滚动窗口", "重采样"]},
        ],
    },
    {
        "phase": 1,
        "title": "金融市场基础 + 金融学 + 数据获取",
        "subtitle": "金融学理论 / 市场指标 / 数据获取（11 课）",
        "status": "in_progress",
        "weeks": "3~4 周",
        "lessons": [
            # 数据获取：先明确主线数据从哪来、为什么用复权，后续课程都基于它
            {"id": "p1-l1", "title": "数据获取与处理", "concepts": ["Baostock", "Tushare", "Pandas", "复权"]},
            # 金融学基础（理论骨架）
            {"id": "p1-l2", "title": "货币时间价值与利率", "concepts": ["折现", "现值", "终值", "年金", "名义利率", "实际利率"]},
            {"id": "p1-l3", "title": "债券与久期", "concepts": ["YTM", "久期", "凸性", "收益率曲线"]},
            {"id": "p1-l4", "title": "股票估值模型", "concepts": ["DCF", "DDM", "可比估值"]},
            {"id": "p1-l5", "title": "CAPM 资本资产定价", "concepts": ["β", "市场风险溢价", "SML"]},
            {"id": "p1-l6", "title": "有效市场与投资流派", "concepts": ["EMH", "弱式/半强式/强式", "套利", "价值", "成长", "趋势", "量化"]},
            # 市场与指标
            {"id": "p1-l7", "title": "绩效指标体系", "concepts": ["收益率", "波动率", "夏普", "最大回撤"]},
            {"id": "p1-l8", "title": "宏观与利率", "concepts": ["利率", "CPI", "PPI", "GDP"]},
            {"id": "p1-l9", "title": "技术指标", "concepts": ["MACD", "RSI", "超买", "超卖"]},
            {"id": "p1-l10", "title": "基本面 PE/PB", "concepts": ["估值", "PIT", "杜邦分解"]},
            # 阶段产出
            {"id": "p1-l11", "title": "阶段产出：个股分析", "concepts": ["综合应用"]},
        ],
    },
    {
        "phase": 2,
        "title": "量化策略入门 + 回测",
        "subtitle": "趋势 / 均值回归 / 动量 / 回测引擎（10 课）",
        "status": "in_progress",
        "weeks": "3~4 周",
        "lessons": [
            {"id": "p2-l1", "title": "策略是什么", "concepts": ["信号", "持仓", "交易"]},
            {"id": "p2-l2", "title": "趋势跟踪", "concepts": ["均线交叉", "唐奇安通道"]},
            {"id": "p2-l3", "title": "均值回归", "concepts": ["布林带", "z-score"]},
            {"id": "p2-l4", "title": "动量策略", "concepts": ["横截面动量", "时序动量"]},
            {"id": "p2-l5", "title": "回测引擎", "concepts": ["Backtrader 入门"]},
            {"id": "p2-l6", "title": "绩效指标", "concepts": ["夏普", "回撤", "胜率", "换手"]},
            {"id": "p2-l7", "title": "回测陷阱", "concepts": ["前视偏差", "幸存者偏差"]},
            {"id": "p2-l8", "title": "交易成本", "concepts": ["佣金", "滑点", "冲击成本"]},
            {"id": "p2-l9", "title": "三策略对比", "concepts": ["横向比较"]},
            {"id": "p2-l10", "title": "阶段产出：独立回测", "concepts": ["完整回测报告"]},
        ],
    },
    {
        "phase": 3,
        "title": "因子投资与选股模型",
        "subtitle": "APT / 多因子 / 中性化 / IC-IR / Barra",
        "status": "in_progress",
        "weeks": "4~5 周",
        "lessons": [
            {"id": "p3-l1", "title": "因子与 APT 模型", "concepts": ["因子 vs 策略", "多因子收益来源"]},
            {"id": "p3-l2", "title": "三因子/五因子", "concepts": ["Fama-French"]},
            {"id": "p3-l3", "title": "单因子检验", "concepts": ["IC", "IR", "分层收益"]},
            {"id": "p3-l4", "title": "因子处理与多因子选股", "concepts": ["市值中性", "行业中性", "打分", "合成"]},
            {"id": "p3-l5", "title": "因子生命周期：挖掘与拥挤", "concepts": ["符号回归", "自动化", "拥挤度", "换手", "相关性"]},
            {"id": "p3-l6", "title": "Barra 风险模型", "concepts": ["风险暴露", "风险归因"]},
            {"id": "p3-l7", "title": "阶段产出：多因子框架", "concepts": ["年化超额"]},
        ],
    },
    {
        "phase": 4,
        "title": "衍生品定价与风险管理",
        "subtitle": "随机过程 / Black-Scholes / 蒙特卡洛 / Greeks / VaR",
        "status": "in_progress",
        "weeks": "4~6 周",
        "lessons": [
            {"id": "p4-l1", "title": "随机过程与伊藤引理", "concepts": ["布朗运动", "几何布朗运动", "引理推导"]},
            {"id": "p4-l2", "title": "Black-Scholes", "concepts": ["公式", "假设"]},
            {"id": "p4-l3", "title": "数值定价：二叉树与蒙特卡洛", "concepts": ["二叉树", "路径模拟"]},
            {"id": "p4-l4", "title": "Greeks 与 Delta 对冲", "concepts": ["Delta", "Gamma", "Vega", "动态对冲"]},
            {"id": "p4-l5", "title": "波动率微笑", "concepts": ["隐含波动率"]},
            {"id": "p4-l6", "title": "VaR", "concepts": ["参数法", "历史法", "MC"]},
            {"id": "p4-l7", "title": "阶段产出：期权定价器", "concepts": ["完整定价器"]},
        ],
    },
    {
        "phase": 5,
        "title": "机器学习量化",
        "subtitle": "特征工程 / XGBoost / LSTM / 过拟合 / 强化学习",
        "status": "in_progress",
        "weeks": "6~8 周",
        "lessons": [
            {"id": "p5-l1", "title": "ML 概览", "concepts": ["监督", "无监督", "强化"]},
            {"id": "p5-l2", "title": "特征工程", "concepts": ["因子构造", "标准化"]},
            {"id": "p5-l3", "title": "标签设计", "concepts": ["前瞻收益", "事件"]},
            {"id": "p5-l4", "title": "模型选择", "concepts": ["XGBoost", "LightGBM"]},
            {"id": "p5-l5", "title": "过拟合防范", "concepts": ["交叉验证", "正则"]},
            {"id": "p5-l6", "title": "深度与强化学习", "concepts": ["LSTM", "RL 框架"]},
            {"id": "p5-l7", "title": "模型评估与 Alpha 挖掘", "concepts": ["IC", "分类指标", "挖掘流程"]},
            {"id": "p5-l8", "title": "阶段产出：ML 策略对比", "concepts": ["ML vs 传统"]},
        ],
    },
    {
        "phase": 6,
        "title": "组合优化 + 实盘",
        "subtitle": "马科维茨 / 风险平价 / Black-Litterman / 统计套利 / 实盘",
        "status": "completed",
        "weeks": "持续",
        "lessons": [
            {"id": "p6-l1", "title": "组合优化：马科维茨、风险平价与 Black-Litterman", "concepts": ["有效前沿", "最小方差", "波动率平价", "观点融合"]},
            {"id": "p6-l2", "title": "统计套利", "concepts": ["配对交易", "协整"]},
            {"id": "p6-l3", "title": "组合风控", "concepts": ["止损", "压力测试"]},
            {"id": "p6-l4", "title": "模拟盘与实盘准备", "concepts": ["模拟交易", "券商 API", "风控"]},
            {"id": "p6-l5", "title": "市场微观结构与高频", "concepts": ["订单簿", "流动性", "延迟", "撮合"]},
            {"id": "p6-l6", "title": "阶段产出：完整 pipeline", "concepts": ["全流程"]},
        ],
    },
]
