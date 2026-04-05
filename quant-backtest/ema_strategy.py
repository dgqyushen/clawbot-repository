import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

plt.style.use('seaborn-v0_8-whitegrid')


def get_data(ticker: str, start: str, end: str) -> pd.Series:
    df = yf.download(ticker, start=start, end=end, progress=False)
    if isinstance(df, pd.DataFrame) and len(df) > 0:
        if 'Close' in df.columns:
            if isinstance(df['Close'], pd.DataFrame):
                return df['Close'].iloc[:, 0]
            return df['Close']
    return pd.Series(dtype=float)


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    return prices.ewm(span=period, adjust=False).mean()


def calculate_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()


def calculate_cumulative_returns(returns: pd.Series) -> pd.Series:
    return (1 + returns).cumprod() - 1


def calculate_max_drawdown(cumulative_returns: pd.Series) -> float:
    wealth_index = 1 + cumulative_returns
    previous_peaks = wealth_index.cummax()
    drawdowns = (wealth_index - previous_peaks) / previous_peaks
    return drawdowns.min()


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess_returns = returns - risk_free_rate / 252
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()


def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess_returns = returns - risk_free_rate / 252
    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) == 0 or downside_returns.std() == 0:
        return np.inf
    return np.sqrt(252) * excess_returns.mean() / downside_returns.std()


def run_backtest():
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = '2020-01-01'

    print("=" * 60)
    print(" EMA Crossover Strategy Backtest")
    print("=" * 60)
    print(f"Period: {start_date} to {end_date}")
    print(f"Strategy: EMA20 > EMA200 -> Long QQQ, EMA20 < EMA200 -> Long PSQ")
    print("=" * 60)

    print("\n[1/4] Downloading data...")
    qqq_prices = get_data('QQQ', start_date, end_date)
    psq_prices = get_data('PSQ', start_date, end_date)
    print(f"  QQQ data: {len(qqq_prices)} trading days")
    print(f"  PSQ data: {len(psq_prices)} trading days")

    print("\n[2/4] Calculating EMAs and signals...")
    qqq_ema20 = calculate_ema(qqq_prices, 20)
    qqq_ema200 = calculate_ema(qqq_prices, 200)

    aligned_prices = pd.DataFrame({
        'QQQ': qqq_prices,
        'PSQ': psq_prices,
        'EMA20': qqq_ema20,
        'EMA200': qqq_ema200
    }).dropna()

    aligned_prices['Signal'] = np.where(
        aligned_prices['EMA20'] > aligned_prices['EMA200'],
        'QQQ',
        'PSQ'
    )
    aligned_prices['Position'] = aligned_prices['Signal'].shift(1).fillna('PSQ')

    aligned_prices['Strategy_Return'] = np.where(
        aligned_prices['Position'] == 'QQQ',
        aligned_prices['QQQ'].pct_change(),
        aligned_prices['PSQ'].pct_change()
    )

    aligned_prices['Benchmark_Return'] = aligned_prices['QQQ'].pct_change()

    aligned_prices['Strategy_CumRet'] = calculate_cumulative_returns(aligned_prices['Strategy_Return'])
    aligned_prices['Benchmark_CumRet'] = calculate_cumulative_returns(aligned_prices['Benchmark_Return'])

    print("\n[3/4] Calculating performance metrics...")

    strategy_returns = aligned_prices['Strategy_Return'].dropna()
    benchmark_returns = aligned_prices['Benchmark_Return'].dropna()

    strategy_total_ret = aligned_prices['Strategy_CumRet'].iloc[-1]
    benchmark_total_ret = aligned_prices['Benchmark_CumRet'].iloc[-1]

    n_years = len(aligned_prices) / 252
    strategy_annual_ret = (1 + strategy_total_ret) ** (1 / n_years) - 1
    benchmark_annual_ret = (1 + benchmark_total_ret) ** (1 / n_years) - 1

    strategy_max_dd = calculate_max_drawdown(aligned_prices['Strategy_CumRet'])
    benchmark_max_dd = calculate_max_drawdown(aligned_prices['Benchmark_CumRet'])

    strategy_sharpe = calculate_sharpe_ratio(strategy_returns)
    benchmark_sharpe = calculate_sharpe_ratio(benchmark_returns)

    strategy_sortino = calculate_sortino_ratio(strategy_returns)
    benchmark_sortino = calculate_sortino_ratio(benchmark_returns)

    print("\n" + "=" * 60)
    print(" PERFORMANCE COMPARISON")
    print("=" * 60)
    print(f"{'Metric':<25} {'EMA Strategy':>15} {'Buy & Hold':>15}")
    print("-" * 60)
    print(f"{'Total Return':<25} {strategy_total_ret*100:>14.2f}% {benchmark_total_ret*100:>14.2f}%")
    print(f"{'Annualized Return':<25} {strategy_annual_ret*100:>14.2f}% {benchmark_annual_ret*100:>14.2f}%")
    print(f"{'Max Drawdown':<25} {strategy_max_dd*100:>14.2f}% {benchmark_max_dd*100:>14.2f}%")
    print(f"{'Sharpe Ratio':<25} {strategy_sharpe:>15.2f} {benchmark_sharpe:>15.2f}")
    print(f"{'Sortino Ratio':<25} {strategy_sortino:>15.2f} {benchmark_sortino:>15.2f}")
    print("=" * 60)

    trade_count = (aligned_prices['Position'].shift(1) != aligned_prices['Position']).sum() - 1
    print(f"\nTotal Trades: {trade_count}")

    print("\n[4/4] Generating charts...")
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    fig.suptitle('EMA Crossover Strategy vs Buy & Hold (QQQ)', fontsize=16, fontweight='bold')

    ax1 = axes[0]
    ax1.plot(aligned_prices.index, aligned_prices['QQQ'], label='QQQ Price', color='blue', alpha=0.7)
    ax1.plot(aligned_prices.index, aligned_prices['EMA20'], label='EMA20', color='orange', linewidth=1.5)
    ax1.plot(aligned_prices.index, aligned_prices['EMA200'], label='EMA200', color='red', linewidth=1.5)
    ax1.set_title('QQQ Price with EMA20 & EMA200')
    ax1.set_ylabel('Price ($)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    ax2 = axes[1]
    ax2.fill_between(aligned_prices.index, 0, aligned_prices['Strategy_CumRet'] * 100,
                     label='EMA Strategy', color='green', alpha=0.5)
    ax2.fill_between(aligned_prices.index, 0, aligned_prices['Benchmark_CumRet'] * 100,
                     label='Buy & Hold', color='blue', alpha=0.3)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_title('Cumulative Returns Comparison')
    ax2.set_ylabel('Return (%)')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)

    ax3 = axes[2]
    colors = ['green' if pos == 'QQQ' else 'red' for pos in aligned_prices['Position']]
    ax3.fill_between(aligned_prices.index, 0, 1, where=(aligned_prices['Position'] == 'QQQ'),
                    color='green', alpha=0.3, label='Long QQQ')
    ax3.fill_between(aligned_prices.index, 0, 1, where=(aligned_prices['Position'] == 'PSQ'),
                    color='red', alpha=0.3, label='Long PSQ')
    ax3.set_title('Position Over Time (Green=QQQ, Red=PSQ)')
    ax3.set_ylabel('Position')
    ax3.set_yticks([])
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('backtest_results.png', dpi=150, bbox_inches='tight')
    print("  Chart saved: backtest_results.png")

    summary_df = pd.DataFrame({
        'Metric': ['Total Return', 'Annualized Return', 'Max Drawdown', 'Sharpe Ratio', 'Sortino Ratio'],
        'EMA Strategy': [f'{strategy_total_ret*100:.2f}%', f'{strategy_annual_ret*100:.2f}%',
                        f'{strategy_max_dd*100:.2f}%', f'{strategy_sharpe:.2f}', f'{strategy_sortino:.2f}'],
        'Buy & Hold': [f'{benchmark_total_ret*100:.2f}%', f'{benchmark_annual_ret*100:.2f}%',
                      f'{benchmark_max_dd*100:.2f}%', f'{benchmark_sharpe:.2f}', f'{benchmark_sortino:.2f}']
    })
    summary_df.to_csv('performance_summary.csv', index=False)
    print("  Summary saved: performance_summary.csv")

    print("\n✓ Backtest complete!")


if __name__ == '__main__':
    run_backtest()
