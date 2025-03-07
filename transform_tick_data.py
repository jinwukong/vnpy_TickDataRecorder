"""
功能概述：
    1. 读取本地txt文件中的原始Tick数据并转换为TickData。
    2. 使用BarGenerator对TickData进行合成，生成1分钟K线（BarData）。
    3. 将合成后的Bar数据存储在一个DataFrame中，最终保存为CSV文件。

依赖：
    - BarGenerator：需要在自定义模块bargenerator4record中提前定义好BarGenerator类。
    - TickData、BarData：来自vn.py的交易对象定义。
    - pandas：用于将最终结果写出CSV。

使用前：
    - 请先确认好读取txt文件的位置或文件夹名称（如 'tick_data_night' / 'tick_data_day'）。
    - 可以在合成逻辑内，根据需要合成1分钟、5分钟或者其他周期的Bar。
"""

from pathlib import Path
from vnpy.trader.constant import Exchange
from datetime import datetime
from vnpy.trader.utility import extract_vt_symbol
from vnpy.trader.object import TickData, BarData
import sys
import pandas as pd
from datetime import datetime
from bargenerator4record.BarGenerator import BarGenerator

# 定义导出CSV时的列名
COLUMNS = [
    'symbol', 'exchange', 'datetime', 'interval', 'volume', 'turnover',
    'open_interest', 'open_price', 'high_price', 'low_price', 'close_price'
]

class TickToBarConverter:
    """
    TickToBarConverter:
        - 读取txt文件中的字符串数据并解析为TickData
        - 使用BarGenerator合成1分钟Bar
        - 将结果保存到DataFrame并导出为csv
    """
    def __init__(self, vt_symbol: str):
        """
        构造函数：
            - vt_symbol 例如： 'IC2309.CFFEX'
            - 实例化一个BarGenerator并准备好DataFrame。
        """
        self.vt_symbol = vt_symbol

        # 创建BarGenerator实例，用于合成指定周期的K线
        self.bg = BarGenerator(self.on_bar)

        # 存放最终生成的Bar数据（DataFrame）
        self.df = pd.DataFrame(columns=COLUMNS)

    def on_bar(self, bar: BarData):
        """
        合成1分钟Bar后会调用该回调，将BarData信息追加到DataFrame中。
        """
        bar_dict = bar.__dict__.copy()

        # 将枚举类型转换为字符串存储
        bar_dict['exchange'] = bar_dict['exchange'].value
        bar_dict['interval'] = bar_dict['interval'].value
        
        # 有些字段在vn.py中默认存在或不一定需要，如gateway_name、extra等，根据需要剔除
        bar_dict.pop('gateway_name', None)
        bar_dict.pop('extra', None)  # 如果BarData没有extra字段，则不会报错

        # 追加到DataFrame
        self.df.loc[len(self.df)] = bar_dict

    def start(self):
        """
        主流程：
            1. 遍历可能的文件夹（如白天、夜盘）
            2. 将所有txt文件中的字符串转换为TickData并推送给BarGenerator
            3. 最终将合成的BarData写出到csv
        """
        home_path = Path(__file__).parent
        folder_list = ['tick_data_night', 'tick_data_day']

        for folder_name in folder_list:
            folder_path = home_path / folder_name
            file_path = folder_path / f"{self.vt_symbol}.txt"

            if not file_path.exists():
                continue

            with open(file_path, mode='r', encoding='utf-8') as f:
                data_str = f.read()
                if data_str:
                    self._process_tick_string(data_str)

        self._to_csv()

    def _process_tick_string(self, data_str: str):
        """
        将完整字符串分割为多行，每行解析为字典后再转换为TickData，并推送给BarGenerator。
        """
        lines = data_str.split('\n')
        for line in lines:
            if not line.strip():
                continue
            self._parse_line_to_tick(line)

    def _parse_line_to_tick(self, line: str) -> None:
        """
        将每一行的原始字符串转换为TickData，然后给BarGenerator更新。
        """
        clean_str = (line.replace('{', '')
                         .replace('}', '')
                         .replace("''", ''))

        # 使用中文逗号+空格做分割
        fields = clean_str.split('， ')

        tick_dict = {}
        for field in fields:
            kv = field.split(': ')
            if len(kv) == 2:
                tick_dict[kv[0]] = kv[1]

        self._generate_tick(tick_dict)

    def _generate_tick(self, data: dict):
        """
        将字典转换为TickData，并推送给BarGenerator进行合成。
        """
        if not data.get("UpdateTime", None):
            return

        symbol, exchange = extract_vt_symbol(self.vt_symbol)

        # 大商所及无ActionDay时，以本地日期为准
        if not data.get("ActionDay") or exchange == Exchange.DCE:
            date_str = data['localtime'].split(' ')[0].replace('-', '')
        else:
            date_str = data["ActionDay"]

        timestamp = f"{date_str} {data['UpdateTime']}.{data['UpdateMillisec']}"
        dt = datetime.strptime(timestamp, "%Y%m%d %H:%M:%S.%f")

        tick = TickData(
            symbol=symbol,
            exchange=exchange,
            datetime=dt,
            volume=float(data["Volume"]),
            turnover=float(data["Turnover"]),
            open_interest=float(data["OpenInterest"]),
            last_price=_adjust_price(float(data["LastPrice"])),
            limit_up=float(data["UpperLimitPrice"]),
            limit_down=float(data["LowerLimitPrice"]),
            open_price=_adjust_price(float(data["OpenPrice"])),
            high_price=_adjust_price(float(data["HighestPrice"])),
            low_price=_adjust_price(float(data["LowestPrice"])),
            pre_close=_adjust_price(float(data["PreClosePrice"])),
            bid_price_1=_adjust_price(float(data["BidPrice1"])),
            ask_price_1=_adjust_price(float(data["AskPrice1"])),
            bid_volume_1=float(data["BidVolume1"]),
            ask_volume_1=float(data["AskVolume1"]),
            gateway_name='local_gateway',
            localtime=datetime.strptime(data['localtime'], '%Y-%m-%d %H:%M:%S')
        )

        # 五档行情数据
        if data.get("BidVolume2") or data.get("AskVolume2"):
            tick.bid_price_2 = _adjust_price(float(data["BidPrice2"]))
            tick.bid_price_3 = _adjust_price(float(data["BidPrice3"]))
            tick.bid_price_4 = _adjust_price(float(data["BidPrice4"]))
            tick.bid_price_5 = _adjust_price(float(data["BidPrice5"]))

            tick.ask_price_2 = _adjust_price(float(data["AskPrice2"]))
            tick.ask_price_3 = _adjust_price(float(data["AskPrice3"]))
            tick.ask_price_4 = _adjust_price(float(data["AskPrice4"]))
            tick.ask_price_5 = _adjust_price(float(data["AskPrice5"]))

            tick.bid_volume_2 = float(data["BidVolume2"])
            tick.bid_volume_3 = float(data["BidVolume3"])
            tick.bid_volume_4 = float(data["BidVolume4"])
            tick.bid_volume_5 = float(data["BidVolume5"])

            tick.ask_volume_2 = float(data["AskVolume2"])
            tick.ask_volume_3 = float(data["AskVolume3"])
            tick.ask_volume_4 = float(data["AskVolume4"])
            tick.ask_volume_5 = float(data["AskVolume5"])

        # 将TickData推送给BarGenerator更新
        self.bg.update_tick(tick)

    def _to_csv(self):
        """
        将最终的DataFrame保存为CSV文件，文件名即vt_symbol.csv
        """
        csv_name = f"{self.vt_symbol}.csv"
        self.df.to_csv(csv_name, index=False)

def _adjust_price(price: float) -> float:
    """
    将极端价格（sys.float_info.max）视为无效置为0。
    """
    if price == sys.float_info.max:
        return 0
    return price


if __name__ == "__main__":
    converter = TickToBarConverter('IC2412.CFFEX')
    converter.start()
