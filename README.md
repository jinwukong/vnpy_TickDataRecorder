# vnpy_TickDataRecorder

一个基于 **vnpy** 框架的期货Tick数据采集与处理项目。利用 CTP 网关实时监听并录制期货合约的原始Tick行情，并提供从txt解析为 vnpy 标准 TickData、再进一步合成K线、与其他数据源对比等功能。  

---

## 功能列表

1. **实时采集CTP期货合约行情**  
   - 通过 vnpy 的事件引擎监听合约信息、原始行情数据（Tick），将其逐条写入文本文件。  
   - 录制策略可自定义，包括按合约区分文件、在写入前为Tick数据补充本地时间、处理ExchangeID等。

2. **离线解析 txt 文件中的Tick数据**  
   - 将已录制的原始行情（以字典形式存储在txt）转换为 vnpy 标准的 `TickData` 对象。  
   - 自动清洗和处理异常值（如浮点数极限值），保证数据质量。

3. **使用 BarGenerator 合成K线**  
   - 在解析TickData的过程中，推送给 BarGenerator 用于 1 分钟K线合成（或其他周期）。  
   - 最终结果以 DataFrame 形式保存到内存，并可导出 csv 文件。

4. **第三方数据对比**  
   - 演示使用 `datacompy` 将本地录制数据与其他数据源（如 RQData）对比，自动输出差异报告。

---

## 目录结构

- **record_tick.py**  
  连接CTP并订阅行情，实时将原始Tick数据写入 txt 文件。
- **load_tick_data.py**  
  读取 txt 文件中的原始字符串，拆分并还原为 vnpy 标准 `TickData`。
- **transform_tick_data.py**  
  合并与处理 TickData，使用 `BarGenerator` 合成 K 线，最终写出 csv。
- **compare_with_rqdata.py**  
  演示对比本地录制数据与第三方（如 RQData）数据的差异。

---

## 功能步骤详解

### 1. CTP 实时录制

- 在 `record_tick.py` 中，自定义了 `TickRecorder` 类，用于：
  - 启动 vnpy 的事件引擎。
  - 使用自定义 `CtpGateway` 连接并订阅期货合约行情。
  - 监听 EVENT_ORIGINAL_TICK 事件并将原始Tick写入txt文件（行级存储，字典格式）。
- 录制过程中会在每条Tick前插入换行符，并为 Tick 数据补全本地时间、交易所等字段。

### 2. 从 txt 转换为 TickData

- 在 `load_tick_data.py` 或 `transform_tick_data.py` 中，演示了如何从 txt 文件中读取原始字符串，并恢复为 vnpy 标准的 `TickData` 对象。
- 针对大商所（DCE）夜盘 ActionDay 变成次日的问题：  
  - 如果 `ActionDay` 为空，或者合约交易所是 DCE，则改用本地日期进行拼接。  
- 针对异常价格：  
  - 通过 `_adjust_price` 函数，将 `sys.float_info.max` 替换为0，避免影响后续计算。

### 3. 合成K线并输出 csv

- 项目中展示了 `BarGenerator` 的基础用法：  
  - 每读取到一条 TickData，就调用 `bg.update_tick(tick)` 进行 K 线合成。  
  - 在合成完成的回调 `on_bar` 中，使用 pandas DataFrame 记录 Bar 数据，并最终保存为 csv。
- 输出的 csv 格式与 vnpy 中常见的字段一致，包括 open_price、high_price、low_price、close_price、volume、turnover 等。

### 4. 对比第三方数据

- 在 `compare_with_rqdata.py` 中，使用 `datacompy.Compare` 来对比两份 csv（本地 vs 第三方数据）。  
- 如果想行号对应比对，可以以索引为依据；如果想以交易时间或其他字段为主键比对，也可以灵活修改代码。  
- 比对结果会显示相同、不一致、缺失等情况，帮助检验本地录制数据的完整性与正确性。

---

## 源码定制思路

1. **事件与网关**  
   - 整体架构基于 vnpy 的事件引擎和网关管理机制，我只需要定义好事件常量、回调处理，并在网关中触发原始深度行情事件即可。  
   - `event4record.py`、`ctpgateway4record.py` 等文件是对 vnpy CTP 接口的定制，用于直接获取原始 DepthMarketData 并抛出相应事件。

2. **数据存储格式**  
   - 选择将原始 Tick 存在 txt 中，使用字典 + 换行的方式。一方面不必固定列；另一方面后期解析较灵活，可以针对合约或字段做二次处理。  
   - 如果倾向于更好解析或查询，也可换成 CSV 或数据库，但在一些交易场景下，原始字典确有优势。

3. **K线合成**  
   - 我在 `transform_tick_data.py` 中演示了与 `BarGenerator` 的集成。  
   - 通过自行实现 `on_bar` 回调，把合成出来的 BarData 存到 DataFrame，再输出 csv。

4. **数据比对**  
   - 对于需要校验行情质量或比照其他供应商（例如 RQData、Wind、通联数据等），我提供了 `datacompy` 的示例用法；也可以使用 pandas 自带的合并/对比逻辑。

---

## 关于 vnpy 源码的准备

在本项目中，部分功能（如事件引擎、CTP 网关、数据结构定义等）依赖了 **vnpy** 框架。如果你的运行环境中已经安装了完整的 vnpy，可以直接通过 `pip install vnpy` 并在代码中 `import` 相应模块即可。

若你想将所有依赖的源码放在本项目同一文件夹中，便于管理或定制，你可以手动拷贝并迁移以下内容（示例）：

1. **事件引擎相关：**  
   - 将 `vnpy/event/` 目录下的 `event.py`、`event_engine.py` 等核心文件复制到本项目中，并按需改名，如 `event4record.py`。

2. **CTP 网关：**  
   - 将 `vnpy/gateway/ctp` 下的对应文件（如 `ctp_gateway.py`、`ctp_api.cpp` 等）复制到项目中，定制后的文件也可命名为 `ctpgateway4record.py`，以便在本项目中直接使用和修改。

3. **数据结构及常量：**  
   - 将 `vnpy/trader/constant.py`（或其中关键的枚举类型）与 `vnpy/trader/object.py`（如 `TickData`, `BarData`）复制到本项目目录下，确保可以直接 `import`。

4. **通用工具函数：**  
   - 如果在项目里需要 vnpy 提供的一些工具函数（如 `load_json`、`extract_vt_symbol` 等），可复制 `utility.py` 中的对应函数到项目同目录的 `utility.py` 中。

> **注意**：迁移源码后，需把项目内部的 `import` 路径适当修改，以免与原版 vnpy 冲突。因为vnpy更新会变动源码及其结构,因此需适时调整。

简而言之，如果你希望本项目的所有依赖都能在无外部环境下独立运行，可以将所需的 **vnpy** 源码文件拷贝并整合到本项目中，然后按需要修改文件名与内部引用路径。这样就能把项目与原版 vnpy 环境解耦，使用上更灵活方便。
