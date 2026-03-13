#!/usr/bin/env python3
"""Stock screener bot that posts updates to Discord."""
import os
import time
import discord
import finnhub
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Stock lists by category
STOCKS = {
    'AI': ['BBAI', 'CRNC', 'DV', 'RXRX'],
    'Energy': ['BLDP', 'CLNE', 'FCEL', 'GEVO', 'LAC', 'NRGV', 'OPAL'],
    'EVs': ['ABAT', 'AIOT', 'ENVX', 'EVGO', 'NKLA', 'SES', 'SLDP', 'TE'],
    'Environmental': ['NPWR'],
    'Semiconductors': ['NVTS'],
    'Space': ['RDW', 'SPIR'],
    'Fintech': ['MQ'],
    'Healthcare': ['ALT', 'ATAI', 'CGC', 'CMPS', 'CRON', 'GDRX', 'HELP', 'PACB', 'SANA', 'TDOC', 'TLRY'],
    'Education': ['COUR', 'UDMY'],
    'Software': ['PD']
}

class StockScreener:
    def __init__(self):
        finnhub_key = os.getenv('FINNHUB_API_KEY')
        if not finnhub_key:
            raise ValueError("FINNHUB_API_KEY not found")
        self.finnhub_client = finnhub.Client(api_key=finnhub_key)
    
    def get_stock_data(self, ticker: str) -> dict:
        """Fetch stock data from Finnhub."""
        try:
            # Get quote
            quote = self.finnhub_client.quote(ticker)
            if not quote or quote.get('c') == 0:
                return None
            
            # Get company profile
            try:
                profile = self.finnhub_client.company_profile2(symbol=ticker)
                name = profile.get('name', ticker)
                market_cap = profile.get('marketCapitalization', 0)
            except:
                name = ticker
                market_cap = 0
            
            # Get basic financials
            try:
                metrics = self.finnhub_client.company_basic_financials(ticker, 'all')
                metric_data = metrics.get('metric', {})
                pe_ratio = metric_data.get('peBasicExclExtraTTM')
                week52_high = metric_data.get('52WeekHigh')
                week52_low = metric_data.get('52WeekLow')
                week52_return = metric_data.get('52WeekPriceReturnDaily')
            except:
                pe_ratio = None
                week52_high = None
                week52_low = None
                week52_return = None
            
            return {
                'ticker': ticker,
                'name': name,
                'price': quote['c'],
                'change': quote['d'],
                'change_pct': quote['dp'],
                'high': quote['h'],
                'low': quote['l'],
                'open': quote['o'],
                'prev_close': quote['pc'],
                'market_cap': market_cap,
                'pe_ratio': pe_ratio,
                '52w_high': week52_high,
                '52w_low': week52_low,
                '52w_return': week52_return
            }
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            return None
    
    def fetch_all_stocks(self) -> dict:
        """Fetch data for all tracked stocks."""
        all_data = {}
        for category, tickers in STOCKS.items():
            all_data[category] = []
            for ticker in tickers:
                data = self.get_stock_data(ticker)
                if data:
                    all_data[category].append(data)
                time.sleep(1)  # Rate limiting: 1 call/sec
        return all_data
    
    def format_table(self, data: dict) -> str:
        """Format stock data as a table in a code block."""
        lines = []
        lines.append(f"📊 Stock Screener - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        # Flatten all stocks into a single list
        all_stocks = []
        for category, stocks in data.items():
            all_stocks.extend(stocks)
        
        if not all_stocks:
            return "```\nNo stock data available\n```"
        
        # Sort by ticker alphabetically
        all_stocks.sort(key=lambda x: x['ticker'])
        
        # Compact mobile-friendly format with key columns only
        lines.append("Ticker  Price   %Chg    MCap")
        lines.append("------  -----   -----   ----")
        
        for stock in all_stocks:
            ticker = stock['ticker']
            price = f"${stock['price']:.2f}" if stock['price'] else "N/A"
            change_pct = f"{stock['change_pct']:+.1f}%" if stock['change_pct'] is not None else "N/A"
            
            # Format market cap in billions or millions
            if stock['market_cap'] and stock['market_cap'] >= 1000:
                mcap = f"${stock['market_cap']/1000:.1f}B"
            elif stock['market_cap']:
                mcap = f"${stock['market_cap']:.0f}M"
            else:
                mcap = "N/A"
            
            line = f"{ticker:<6}  {price:<6}  {change_pct:>6}  {mcap:>6}"
            lines.append(line)
        
        return "```\n" + "\n".join(lines) + "\n```"


class DiscordBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.screener = StockScreener()
        self.channel_id = int(os.getenv('DISCORD_FEED_CHANNEL_ID'))
    
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        await self.send_screener_update()
    
    async def send_screener_update(self):
        """Fetch stock data and send to Discord channel."""
        channel = self.get_channel(self.channel_id)
        if not channel:
            print(f"Could not find channel {self.channel_id}")
            return
        
        print("Fetching stock data...")
        data = self.screener.fetch_all_stocks()
        
        print("Formatting message...")
        message = self.screener.format_table(data)
        
        # Discord has a 2000 char limit, so split if needed
        if len(message) > 2000:
            chunks = [message[i:i+2000] for i in range(0, len(message), 2000)]
            for chunk in chunks:
                await channel.send(chunk)
        else:
            await channel.send(message)
        
        print("Update sent!")
        await self.close()


def main():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN not found")
    
    bot = DiscordBot()
    bot.run(token)


if __name__ == '__main__':
    main()
