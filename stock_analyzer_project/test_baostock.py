import baostock as bs
import pandas as pd

bs.login()
rs = bs.query_history_k_data_plus(
    'sh.000001', 
    'date,code,open,high,low,close,volume',
    start_date='2024-03-01',
    end_date='2025-03-19',
    frequency='d',
    adjustflag='3'
)

data = []
while rs.error_code == '0' and rs.next():
    data.append(rs.get_row_data())

bs.logout()

print("总数据行数:", len(data))
if data:
    df = pd.DataFrame(data, columns=['日期','代码','开盘','最高','最低','收盘','成交量'])
    print("DataFrame shape:", df.shape)
    print("代码列唯一值:", df['代码'].unique())
    print(df.head(3))
