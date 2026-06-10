#!/usr/bin/env python3
"""
数据获取模块 (Data Fetcher Module)

负责从多个数据源获取股票/指数的历史K线数据
支持: baostock, tushare (akshare 需要 curl_cffi，如不可用会自动跳过)
按顺序尝试，任一成功即返回
"""

import pandas as pd
import numpy as np
import os
import sys
import warnings
from datetime import datetime

VENDOR_DIR = os.path.join(os.path.dirname(__file__), ".vendor")
if os.path.isdir(VENDOR_DIR) and VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

# 尝试导入 baostock
try:
    import baostock as bs
    BAOSTOCK_AVAILABLE = True
except ImportError:
    bs = None
    BAOSTOCK_AVAILABLE = False

# 尝试导入 akshare，如果失败则设为 None
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

# 尝试导入 tushare
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

# Tushare token must be supplied by the runtime environment.
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

warnings.filterwarnings('ignore')


class DataFetcher:
    """多数据源批量获取器
    
    按顺序尝试: baostock -> akshare -> tushare
    任一成功即返回数据
    
    属性:
        codes: 股票代码列表
        is_index: 是否为大盘指数
        df: 获取到的数据DataFrame
        source: 成功的数据源名称
    """
    
    def __init__(self, codes, is_index=False):
        """
        初始化数据获取器
        
        参数:
            codes: 股票代码列表或单个代码 (str 或 list)
            is_index: 是否为大盘指数 (bool)
        """
        self.codes = codes if isinstance(codes, list) else [codes]
        self.is_index = is_index
        self.df = pd.DataFrame()  # 存储获取的数据
        self.source = None  # 记录成功的数据源
    
    # ==================== baostock 数据源 ====================
    
    def _fetch_baostock(self):
        """baostock - 批量获取历史K线数据
        
        优点: 免费、稳定、返回数据格式规范
        注意事项:
            - 指数代码: 上证以sh.开头，深证以sz.开头
            - 个股代码: 6开头为上海(sh)，其他为深圳(sz)
            - 指数使用前复权(adjustflag=3)，个股使用后复权(adjustflag=2)
        
        返回:
            bool: 是否成功获取数据
        """
        if not BAOSTOCK_AVAILABLE:
            return False

        try:
            bs.login()
            all_data = []
            
            for code in self.codes:
                # 根据是否为指数确定市场前缀
                # 指数: 000001 -> sh.000001 (上证), 399006 -> sz.399006 (创业板)
                # 个股: 6开头为上海(sh)，其他为深圳(sz)
                if self.is_index:
                    if code.startswith('399'):
                        bs_code = f"sz.{code}"  # 深证指数
                    else:
                        bs_code = f"sh.{code}"  # 上证指数
                else:
                    bs_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
                
                # 设置日期范围: 过去365天
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
                
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,code,open,high,low,close,volume,amount",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="3" if self.is_index else "2"  # 指数用前复权，个股用后复权
                )
                
                # 遍历获取所有数据
                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())
                
                if data_list:
                    df = pd.DataFrame(
                        data_list, 
                        columns=['日期', '代码', '开盘', '最高', '最低', '收盘', '成交量', '成交额']
                    )
                    # 提取纯数字代码用于后续匹配 (如 sh.000001 -> 000001)
                    df['代码'] = df['代码'].str.replace('sh.', '').str.replace('sz.', '')
                    all_data.append(df)
            
            bs.logout()
            
            if all_data:
                self.df = pd.concat(all_data, ignore_index=True)
                # 转换数值类型
                for col in ['开盘', '最高', '最低', '收盘', '成交量']:
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                # 按代码和日期排序
                self.df = self.df.sort_values(['代码', '日期']).reset_index(drop=True)
                self.source = "baostock"
                return True
                
        except Exception as e:
            print(f"  ⚠️ baostock失败: {e}")
            try:
                bs.logout()
            except:
                pass
        return False
    
    # ==================== akshare 数据源 ====================
    
    def _fetch_akshare(self):
        """akshare - 批量获取历史K线数据
        
        优点: 数据源丰富，支持多种市场
        缺点: 需要 curl_cffi 依赖，如不可用会自动跳过
        
        返回:
            bool: 是否成功获取数据
        """
        # 检查 akshare 是否可用
        if not AKSHARE_AVAILABLE:
            print("  ⚠️ akshare 未安装，跳过")
            return False
        
        try:
            all_data = []
            for code in self.codes:
                if self.is_index:
                    # 指数数据
                    df = ak.index_zh_a_hist(
                        symbol=code, 
                        period="daily",
                        start_date=(datetime.now() - pd.Timedelta(days=365)).strftime("%Y%m%d"),
                        end_date=datetime.now().strftime("%Y%m%d")
                    )
                else:
                    # 个股数据
                    df = ak.stock_zh_a_hist(
                        symbol=code, 
                        period="daily",
                        start_date=(datetime.now() - pd.Timedelta(days=365)).strftime("%Y%m%d"),
                        end_date=datetime.now().strftime("%Y%m%d"), 
                        adjust="qfq"  # 前复权
                    )
                
                if not df.empty:
                    df = df.rename(columns={
                        "日期": "日期", "开盘": "开盘", "收盘": "收盘",
                        "最高": "最高", "最低": "最低", "成交量": "成交量"
                    })
                    df['代码'] = code
                    all_data.append(df[['日期', '代码', '开盘', '最高', '最低', '收盘', '成交量']])
            
            if all_data:
                self.df = pd.concat(all_data, ignore_index=True)
                self.source = "akshare"
                return True
        except Exception as e:
            print(f"  ⚠️ akshare失败: {e}")
        return False
    
    # ==================== tushare 数据源 ====================
    
    def _fetch_tushare(self):
        """tushare - 批量获取历史K线数据
        
        优点: 数据全面，接口稳定
        缺点: 需要token，有接口调用频率限制
        
        返回:
            bool: 是否成功获取数据
        """
        # 检查 tushare 是否可用
        if not TUSHARE_AVAILABLE:
            print("  ⚠️ tushare 未安装，跳过")
            return False
        
        if not TUSHARE_TOKEN:
            return False

        try:
            import tushare as ts
            ts.set_token(TUSHARE_TOKEN)
            pro = ts.pro_api()
            all_data = []
            for code in self.codes:
                # 转换代码格式: 600519 -> 600519.SH, 000001 -> 000001.SZ
                ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
                df = pro.daily(
                    ts_code=ts_code, 
                    start_date=(datetime.now() - pd.Timedelta(days=365)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d")
                )
                if not df.empty:
                    df = df.rename(columns={
                        "trade_date": "日期", "open": "开盘", "close": "收盘",
                        "high": "最高", "low": "最低", "vol": "成交量"
                    })
                    df['日期'] = pd.to_datetime(df['日期']).dt.strftime("%Y-%m-%d")
                    df['代码'] = code
                    all_data.append(df[['日期', '代码', '开盘', '最高', '最低', '收盘', '成交量']])
            
            if all_data:
                self.df = pd.concat(all_data, ignore_index=True)
                self.source = "tushare"
                return True
        except Exception as e:
            print(f"  ⚠️ tushare失败: {e}")
        return False
    
    # ==================== 主获取方法 ====================
    
    def fetch(self):
        """按顺序尝试各个数据源
        
        尝试顺序: baostock -> akshare -> tushare
        任一成功即返回 True
        
        返回:
            bool: 是否成功获取数据
        """
        print(f"  📡 尝试获取数据...")
        
        # 首选baostock - 最稳定
        if self._fetch_baostock():
            print(f"  ✅ 数据源: {self.source}")
            return True
        
        # 备选akshare
        if self._fetch_akshare():
            print(f"  ✅ 数据源: {self.source}")
            return True
        
        # 备选tushare
        if self._fetch_tushare():
            print(f"  ✅ 数据源: {self.source}")
            return True
        
        print(f"  ❌ 所有数据源都失败")
        return False


def fetch_stock_data(codes, is_index=False):
    """便捷函数: 获取单只股票/指数数据
    
    参数:
        codes: 股票代码 (str) 或代码列表 (list)
        is_index: 是否为大盘指数 (bool)
    
    返回:
        tuple: (DataFrame, 数据源名称) 或 (None, None)
    """
    fetcher = DataFetcher(codes, is_index)
    if fetcher.fetch():
        return fetcher.df, fetcher.source
    return None, None


if __name__ == "__main__":
    # 测试代码
    print("=== 测试数据获取 ===")
    
    # 测试个股
    print("\n--- 测试个股: 300750 ---")
    df, source = fetch_stock_data("300750", is_index=False)
    if df is not None:
        print(f"数据源: {source}")
        print(df.tail())
    
    # 测试指数
    print("\n--- 测试指数: 上证指数 ---")
    df, source = fetch_stock_data("000001", is_index=True)
    if df is not None:
        print(f"数据源: {source}")
        print(df.tail())
