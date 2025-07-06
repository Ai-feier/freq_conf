def calculate_return(risk_reward_ratio, win_rate, num_trades):
    # 盈亏比 (risk_reward_ratio)，胜率 (win_rate)，交易笔数 (num_trades)
    win_trades = win_rate * num_trades
    loss_trades = num_trades - win_trades
    
    # 计算每个交易的收益（盈亏比）
    total_profit = win_trades * risk_reward_ratio  # 盈利的总收益
    total_loss = loss_trades  # 亏损的总损失（盈亏比为1）

    # 计算总收益
    total_return = total_profit - total_loss

    return total_return

# 示例：盈亏比1.5，胜率0.6，交易笔数100
risk_reward_ratio = 1.5
win_rate = 0.5
num_trades = 100

result = calculate_return(risk_reward_ratio, win_rate, num_trades)
print(f"预计的收益率为: {result:.2f}")
