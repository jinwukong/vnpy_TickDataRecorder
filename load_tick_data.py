"""
功能概述：
    1. 指定 vt_symbol（如'IC2309.CFFEX'），并在初始化时指定要读取的文件夹路径。
    2. 从txt文件中一次性读取字符串形式的行情数据。
    3. 将每条数据转换为真正的 TickData 对象（vn.py 内置），用于后续分析或进一步处理。

使用前：
    - 请将 '存放所有tick的文件夹名' 替换为你在第一步中实际创建的文件夹路径，比如 "tick_data" 或 "tick_data_night"等。
    - txt文件名约定：与合约名类似，如 "IC2309.CFFEX.txt"。
"""

from pathlib import Path
from vnpy.trader.constant import Exchange
from datetime import datetime
from vnpy.trader.utility import extract_vt_symbol
from vnpy.trader.object import TickData
import sys


class TickFileLoader:
    """
    TickFileLoader：
        - 用于从指定txt文件中读取原始Tick数据字符串
        - 再将其转换为 vn.py 框架中的 TickData 对象，以便后续使用
    """
    def __init__(self, vt_symbol: str):
        """
        构造函数：
            - vt_symbol：例如 'IC2309.CFFEX'
            - floder_path：为存放txt文件的目录，需要手动修改为实际路径名
            - file_path：某个具体合约的txt文件路径
        """
        self.vt_symbol = vt_symbol
        # 此处请根据实际情况修改文件夹名称
        self.floder_path: Path = Path(__file__).parent / '存放所有tick的文件夹名'
        self.file_path: Path = self.floder_path / f"{self.vt_symbol}.txt"

    def read_data_txt(self) -> str:
        """
        读取txt文件中所有的行情数据（以字符串形式返回）
        """
        with open(file=self.file_path, mode='r', encoding='utf-8') as f:
            data = f.read()
        return data

    def process_total_data(self, data_str: str) -> None:
        """
        将完整的字符串拆分为多行数据后，逐行解析并转换成TickData对象。
        - data_str: 包含所有记录的字符串（内部带有换行符 \n）
        """
        # 以换行符分隔，得到每条tick对应的字符串
        tick_lines = data_str.split('\n')
        for line in tick_lines:
            # 跳过空行
            if not line.strip():
                continue
            self._parse_line_to_tick(line)

    def _parse_line_to_tick(self, line: str) -> None:
        """
        将形如"{'key': 'value', ...}"的字符串解析为字典，然后转换为TickData对象。
        - line: 单行文本，对应一条o_tick数据
        """
        # 先去除大括号及空引号等信息
        clean_str = (line.replace('{', '')
                         .replace('}', '')
                         .replace("''", ''))

        # 由于原始数据中键值对之间是用"， "（中文逗号+空格）分割，这里做相应处理
        key_value_list = clean_str.split('， ')

        tick_dict = {}
        for kv in key_value_list:
            # 再把 "key: value" 拆分为列表
            pairs = kv.split(': ')
            if len(pairs) == 2:
                tick_dict[pairs[0]] = pairs[1]

        # 将得到的字典数据传给处理函数，进一步转换成TickData
        self._dict_to_tick(tick_dict)

    def _dict_to_tick(self, data: dict) -> None:
        """
        将原始字典数据data转为TickData对象。
        这里仅示例如何转换，并未做后续存储或合并操作。
        """
        if not data.get("UpdateTime", None):
            return  # 没有时间戳则视为无效

        # 从 vt_symbol 中提取 symbol 和 exchange
        symbol, exchange = extract_vt_symbol(self.vt_symbol)

        # 大商所(DCE)夜盘时ActionDay会变成次日，或者ActionDay字段为空时，则以本地日期为准
        if not data.get("ActionDay") or exchange == Exchange.DCE:
            date_str = data['localtime'].split(' ')[0].replace('-', '')
        else:
            date_str = data["ActionDay"]

        # 组合交易日和更新时间，再加上毫秒
        timestamp_str = f"{date_str} {data['UpdateTime']}.{data['UpdateMillisec']}"
        dt = datetime.strptime(timestamp_str, "%Y%m%d %H:%M:%S.%f")

        # 转为 float 时，需要处理特殊值
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
            localtime=datetime.strptime(
                data['localtime'], '%Y-%m-%d %H:%M:%S'
            )
        )

        # 如果有五档数据，则补充
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

        # 在此可对tick做进一步处理或存储
        # print(tick)  # 测试输出，可根据需求进行后续逻辑

def _adjust_price(price: float) -> float:
    """
    将极端价格（sys.float_info.max）视为无效并置为0。
    部分交易所可能会把某些无效字段填成浮点数极限值。
    """
    if price == sys.float_info.max:
        return 0
    return price


if __name__ == '__main__':
    loader = TickFileLoader('IC2412.CFFEX')
    raw_data_str = loader.read_data_txt()
    loader.process_total_data(raw_data_str)
