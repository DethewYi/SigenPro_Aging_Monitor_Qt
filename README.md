# SigenPro Aging Monitor

储能产品老化监控系统 v1.2.0

基于 Python / PyQt6 的桌面应用，用于储能产品多通道老化测试的监控、告警、数据采集与报告生成。

## 功能特性

- **设备总览** — 多通道设备卡片实时状态展示，支持搜索、筛选、批量启停
- **设备详情** — 实时数据面板、测试控制、pyqtgraph 曲线图表
- **老化配方系统** — 按产品 PN 定义多阶段老化策略，每阶段独立配置电压/电流/功率/继电器动作
- **模板管理** — 测试模板 CRUD、JSON 导入导出
- **告警面板** — 实时告警记录，支持清除、按设备跳转
- **数据查询** — 历史数据查询，支持导出 CSV / PDF
- **8 套主题** — Dark / Light / Ocean / Forest / Sunset / Purple / Industrial / HighContrast
- **中英文切换** — 基于 Python 字典的 i18n，预留日语/韩语扩展位
- **仿真模式** — 内置模拟器，无需真实设备即可演示全部功能
- **多通信接口** — TCP / CAN / RS485，协议插件化架构
- **报告生成** — Excel / PDF 格式报告

## 技术栈

| 组件 | 技术 |
|------|------|
| 框架 | PyQt6 |
| 图表 | pyqtgraph |
| 数据库 | SQLite (本地) + MySQL/PostgreSQL (远程) |
| 通信 | TCP, CAN, RS485 |
| 报告 | openpyxl, fpdf2 |
| Python | >=3.10 |

## 项目结构

```
SigenPro_Aging_Monitor_Qt/
├── main.py                     # 入口
├── pyproject.toml
├── requirements.txt
├── resources/
│   ├── resources.qrc
│   └── themes/                 # 8 套 QSS 主题
├── src/
│   ├── app/                    # Application 单例、主题/语言/日志管理
│   ├── communication/          # TCP/CAN/RS485 通信桥接
│   ├── core/                   # 业务逻辑
│   │   ├── alarm_engine.py     # 告警引擎
│   │   ├── data_bus.py         # 数据总线 (事件分发)
│   │   ├── recipe_executor.py  # 配方执行引擎 (多阶段状态机)
│   │   ├── recipe_manager.py   # 配方 CRUD
│   │   ├── template_manager.py # 模板 CRUD
│   │   ├── test_engine.py      # 简单测试引擎
│   │   └── common/             # 数据模型 (dataclass)
│   ├── i18n/                   # 国际化
│   │   ├── zh_CN.py            # 简体中文
│   │   └── en_US.py            # 英文
│   ├── instrument/             # 仪器控制 (通道管理、扫码枪)
│   ├── protocol/               # 协议插件加载
│   ├── report/                 # Excel / PDF 报告生成
│   ├── simulation/             # 设备数据仿真器
│   ├── storage/                # 数据库管理 (本地+远程)
│   └── ui/                     # PyQt6 界面
│       ├── main_window.py      # 主窗口 (侧栏导航 + QStackedWidget)
│       ├── device_overview.py  # 设备总览
│       ├── device_detail.py    # 设备详情
│       ├── alarm_panel.py      # 告警面板
│       ├── data_query.py       # 数据查询
│       ├── template_config.py  # 模板管理
│       ├── recipe_config.py    # 配方管理
│       └── settings_page.py    # 系统设置
└── plugins/                    # 协议插件目录
```

## 快速开始

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动
python main.py
```

## 配方系统设计

配方 (Recipe) 是按产品 PN 绑定的多阶段老化策略：

```
AgingRecipe
├── product_pn (唯一)
├── max_total_minutes (总时间保护)
├── phases[] (有序阶段列表)
│   └── AgingPhase
│       ├── name, duration_minutes
│       ├── voltage, current, power_limit
│       └── phase_start_actions[], phase_end_actions[] (继电器动作)
└── event_actions (生命周期动作)
    ├── on_start[]   (启动时)
    ├── on_alarm[]   (报警时 → 紧急停止)
    └── on_complete[] (完成时)
```

- 报警时自动执行紧急停止：on_alarm 动作 → 电源归零 → 断开继电器
- 每阶段支持独立的继电器动作编排，动作间支持延时 (delay_ms)

## 扩展语言

在 `src/i18n/` 下新建翻译文件，例如 `ja_JP.py`：

```python
TRANSLATIONS = {
    "Settings": "設定",
    "Save": "保存",
    # ...
}
```

然后在 `src/app/language_manager.py` 的 `_languages` 列表中添加条目即可。

## 版本历史

- **v1.2.0** — i18n 中英文切换、配方管理 UI
- **v1.1.0** — 老化配方系统 (多阶段执行、电源控制、继电器动作编排)
- **v1.0.0** — Python/PyQt6 基础版本完成
