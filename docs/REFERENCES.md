# 参考资源清单

本项目课程各章末尾的「参考文献」是权威出处；本清单按主题汇总可进一步参考的外部资源，供内容扩充与读者延伸阅读。

## 中文零基础路线（与课程 Phase 1/2 结构高度同构）

| 资源 | 说明 | 对应阶段 |
|---|---|---|
| [Datawhale quant-for-beginners](https://github.com/datawhalechina/quant-for-beginners) | 零基础中文量化 Notebook 路线，同样按「Phase 1/2」分章：双均线 → 回测 → 夏普/Beta → 最大回撤/仓位 → 多标的组合，每章一个可运行 Notebook | Phase 1/2 |
| [Datawhale whale-quant](https://datawhalechina.github.io/whale-quant/) | 量化开源课程：选股（MPT/CAPM/多因子）、择时（双均线/MACD/Granville）、调仓、回测 | Phase 2/3/6 |
| [XQuant 人人都是量化交易员](https://xingwudao.github.io/xquant-beginner/) | 先猜后验、做→看→疑 方法论；标的池、权重分配、再平衡/止损/止盈、四视角评估、防过拟合 | Phase 2 |

## 中文量化百科与词条索引

| 资源 | 说明 |
|---|---|
| [Quant-Wiki 量化百科](https://quant-wiki.com/)（[GitHub](https://github.com/llmquant/quant-wiki)） | 开源中文量化百科，OI Wiki 式协作架构，覆盖因子、151 个交易策略、统计套利、回测框架等，可作课程术语表/知识点索引 |
| [AKQuant 教材](https://akquant.akfamily.xyz/textbook/) | A 股专向（T+1、涨跌停、滑点建模），从回测到实盘全链路，工程实现细节参考 |

## 数学与组合（Phase 0/6）

| 资源 | 说明 |
|---|---|
| [MIT 18.S096 Topics in Mathematics with Applications in Finance](https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/) | 组合理论权威讲义（Lecture 14/16：马科维茨、风险平价、再平衡、MPT 局限） |
| [MIT 18.642 (F24) 讲义](https://ocw.mit.edu/courses/18-642-topics-in-mathematics-with-applications-in-finance-fall-2024/) | Jake Xia 2024 版组合管理讲义：再平衡、波动率并非风险、收益-损失比 |
| [Tidy Finance](https://www.tidy-finance.org/) | R+Python 双语实证金融全书，组合排序、Fama-French、约束组合优化，可复现性极强 |
| [Learn-Quant](https://meridianalgo.github.io/Learn-Quant/) | 134 个自包含模块（GARCH、Black-Litterman、RL），带单测，模块组织可参考 |

## 期权与衍生品（Phase 4）

| 资源 | 说明 |
|---|---|
| [QuantLib](https://www.quantlib.org/) | 业界标准开源定价库：BS、Greeks、二叉树、蒙特卡洛 |
| [Python for Finance (2nd ed.)](https://github.com/yhilpisch/py4fi2nd) | Yves Hilpisch，衍生品定价与蒙特卡洛的 Python 实践 |
| [Quantitative-Finance-Course](https://github.com/MarchesiQuant/Quantitative-Finance-Course) | 直觉导向的定价与随机微积分课程（BS、Heston、Hull-White） |

## 机器学习量化（Phase 5）

| 资源 | 说明 |
|---|---|
| [Microsoft Qlib](https://github.com/microsoft/qlib) | AI 量化平台，完整 ML pipeline（数据→因子→模型→回测→组合） |
| [Quant Guild Library](https://quantguild.com)（[GitHub](https://github.com/romanmichaelpaolucci/Quant-Guild-Library)） | ML 在量化中的 Notebook + 讲座视频（PCA、Black-Scholes ML、RL 等） |

## A 股实盘与回测工程（Phase 2/6 落地）

| 资源 | 说明 |
|---|---|
| [VeighNa (vnpy)](https://github.com/vnpy/vnpy) | 开源交易平台框架，对接 CTP/XTP 等真实接口，回测/模拟/实盘模块齐全 |
| [Backtrader](https://www.backtrader.com/) | Python 开源回测框架；中文笔记见 [learn_backtrader](https://github.com/jrothschild33/learn_backtrader) |
| [Quantaxis](https://github.com/yutiansut/QUANTAXIS) | 股票/期货/期权数据、回测、模拟、实盘一体化框架 |

## 进阶课程体系（完整 syllabus 参考）

| 资源 | 说明 |
|---|---|
| [open-MFE](https://github.com/ebrahimpichka/open-MFE) | 复刻顶尖 MFE 项目的开源课程地图（Berkeley/CMU/Baruch 等），含每门课的开源资源 |
| [The Open Quant Live Book](https://www.ebook.openquants.com/) | 开源量化参考书：金融数据分析、算法交易、组合选择、econophysics、金融 ML |

> 说明：XQuant 与 whale-quant 已直接引用在 Phase 2 各课参考文献中；本清单其余资源可按需补入对应课程的参考文献小节。
