import asyncio
import logging
from binance import AsyncClient
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)

async def calculate_total_equity(client: AsyncClient, open_trades: dict, initial_balance: float) -> float:
    '''
    Calculates the total equity (realized + unrealized PnL).
    '''
    try:
        total_equity = initial_balance

        if not open_trades:
            return total_equity

        # Get all tickers at once
        symbols = list(open_trades.keys())
        ticker_stats = await client.get_ticker(symbols=symbols)
        prices = {item['symbol']: float(item['lastPrice']) for item in ticker_stats}

        # Add unrealized PnL from open trades
        for symbol, trade_details in open_trades.items():
            current_price = prices.get(symbol, 0)
            unrealized_pnl = (current_price - trade_details['avg_price']) * trade_details['quantity']
            total_equity += unrealized_pnl

        return total_equity

    except BinanceAPIException as e:
        logger.error(f"Error calculating total equity: {e}")
        return 0.0