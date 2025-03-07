"""
功能概述：
    1. 连接CTP接口并订阅合约行情（期货）。
    2. 获取原始Tick行情（通过自定义事件EVENT_ORIGINAL_TICK）。
    3. 将包含合约代码、交易所、时间等信息的Tick数据，以字符串形式一行行地保存到本地txt文件中。

依赖：
    - event4record：自定义事件引擎模块，需包含EventEngine、Event等基础类及常量EVENT_ORIGINAL_TICK。
    - ctpgateway4record：自定义CTP网关模块，需包含CtpGateway类。
    - vnpy/trader 相关类与方法：用于加载配置、订阅行情以及部分数据结构定义。
    
使用前：
    - 确保当前文件夹下存在 connect_ctp.json，该文件包含CTP经纪商、账户等连接信息。
    - 运行脚本后，会在当前工作目录下自动创建“tick_data”文件夹，并将实时的Tick数据写入对应的txt文件。
"""

from event4record import EventEngine, Event, EVENT_ORIGINAL_TICK
from ctpgateway4record import CtpGateway
from vnpy.trader.utility import load_json
from vnpy.trader.object import LogData, ContractData, SubscribeRequest
from vnpy.trader.event import EVENT_LOG, EVENT_CONTRACT
from vnpy.trader.constant import Product
from pathlib import Path
from datetime import datetime


class TickRecorder:
    """
    TickRecorder 类：
        - 负责连接CTP，并将原始Tick数据记录到本地txt文件中。
        - 通过事件引擎，监听日志事件、合约事件、原始Tick事件，分别执行不同的处理逻辑。
    """
    def __init__(self):
        """
        构造函数：
            1. 创建并启动事件引擎。
            2. 实例化CTPGateway。
            3. 准备存放合约的字典，以便订阅和检索对应信息。
            4. 注册事件处理函数。
            5. 创建文件夹用于存放记录的Tick数据txt文件。
        """
        # 1) 创建并启动事件引擎
        self.event_engine = EventEngine()
        self.event_engine.start()

        # 2) 创建CTP网关实例（用于连接CTP、订阅行情等）
        self.ctp_gateway = CtpGateway(
            event_engine=self.event_engine,
            gateway_name='CTP'  # 可自定义网关名称
        )

        # 3) 用于存放合约信息的字典，key为symbol(str)，value为ContractData对象
        self.contracts = {}

        # 4) 注册事件处理函数
        self.register_handlers()

        # 5) 创建数据保存目录（默认目录名为tick_data，可自行修改）
        self.data_directory: Path = Path.cwd() / 'tick_data'
        self.data_directory.mkdir(exist_ok=True)

    def register_handlers(self):
        """
        将对应事件注册到事件引擎进行监听和处理：
            - EVENT_LOG       -> self.log_handler
            - EVENT_CONTRACT  -> self.handle_contract_event
            - EVENT_ORIGINAL_TICK -> self.handle_original_tick
        """
        self.event_engine.register(EVENT_LOG, self.log_handler)
        self.event_engine.register(EVENT_CONTRACT, self.handle_contract_event)
        self.event_engine.register(EVENT_ORIGINAL_TICK, self.handle_original_tick)

    def connect_ctp(self) -> None:
        """
        连接CTP交易接口：
            - 从本地connect_ctp.json加载配置
            - 调用CTP网关进行连接
        """
        ctp_settings = load_json(filename="connect_ctp.json")
        self.ctp_gateway.connect(setting=ctp_settings)

    def log_handler(self, event: Event) -> None:
        """
        日志事件处理函数：
            - 用于接收框架内部产生的日志事件（EVENT_LOG）
            - 打印或记录日志信息
        """
        log: LogData = event.data
        print(f"[LOG] {log.msg}")

    def handle_contract_event(self, event: Event) -> None:
        """
        合约事件处理函数（EVENT_CONTRACT）：
            - 当框架加载合约信息后触发此事件。
            - 仅对期货类型合约进行订阅并记录到字典中，以后用于查询。
        """
        contract: ContractData = event.data
        if contract.product != Product.FUTURES:
            return

        # 缓存合约对象
        self.contracts[contract.symbol] = contract

        # 发送订阅请求
        subscribe_req = SubscribeRequest(
            symbol=contract.symbol, 
            exchange=contract.exchange
        )
        self.ctp_gateway.subscribe(req=subscribe_req)

    def handle_original_tick(self, event: Event) -> None:
        """
        原始Tick事件处理函数（EVENT_ORIGINAL_TICK）：
            - 获取底层发来的原始tick字典o_tick，并补充交易所和本地时间等信息后写入txt文件。
        """
        o_tick: dict = event.data
        symbol: str = o_tick.get('InstrumentID', None)
        contract: ContractData = self.contracts.get(symbol, None)

        # 如果在字典中找不到合约信息，则跳过（一般说明该合约不是期货或未正常订阅）
        if not contract:
            return

        # 为o_tick补充ExchangeID和本地时间
        o_tick['ExchangeID'] = contract.exchange.value
        o_tick['localtime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 将原始tick写入本地txt文件
        self.append_tick_to_file(o_tick=o_tick)

    def append_tick_to_file(self, o_tick: dict) -> None:
        """
        将原始tick（dict格式）追加写入txt文件，每个tick占一行。
        文件名示例： AP303.CZCE.txt
        """
        file_name = f"{o_tick['InstrumentID']}.{o_tick['ExchangeID']}.txt"
        file_path: Path = self.data_directory.joinpath(file_name)

        # 以追加(a+)模式打开txt文件，编码方式为utf-8
        with open(file_path, mode='a+', encoding='utf-8') as f:
            # 在每条tick前添加换行符\n，再将字典转为字符串写入
            f.write(f"\n{o_tick}")

# 如果需要直接运行该脚本来录制数据，可在此处执行
if __name__ == "__main__":
    recorder = TickRecorder()
    recorder.connect_ctp()
