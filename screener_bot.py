#!/usr/bin/env python3
"""Stock screener bot that posts updates to Discord."""
import os
import json
import logging
import asyncio
import discord
import finnhub
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Global reference for Discord logging
discord_log_channel = None

class DiscordLogHandler(logging.Handler):
    """Custom logging handler that sends logs to Discord channel."""
    
    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id
        self.log_buffer = []
        
    def emit(self, record):
        """Buffer log records to send to Discord."""
        if record.levelno >= logging.WARNING:  # Only WARNING and ERROR
            self.log_buffer.append(self.format(record))
    
    async def send_logs(self, client):
        """Send buffered logs to Discord channel."""
        if not self.log_buffer:
            return
            
        channel = client.get_channel(self.channel_id)
        if not channel:
            print(f"Could not find logs channel {self.channel_id}")
            return
        
        # Combine all logs into one message
        log_message = "\n".join(self.log_buffer)
        
        # Send as code block, split if too long
        formatted = f"```\n{log_message}\n```"
        
        if len(formatted) > 2000:
            # Split into multiple messages if needed
            chunks = [self.log_buffer[i:i+10] for i in range(0, len(self.log_buffer), 10)]
            for chunk in chunks:
                chunk_msg = "```\n" + "\n".join(chunk) + "\n```"
                await channel.send(chunk_msg)
        else:
            await channel.send(formatted)
        
        # Clear buffer after sending
        self.log_buffer.clear()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_stocks():
    """Load stocks from JSON file."""
    try:
        with open('stocks.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("stocks.json not found!")
        return {}

# Load stocks on startup
STOCKS = load_stocks()

class StockScreener:
    def __init__(self):
        finnhub_key = os.getenv('FINNHUB_API_KEY')
        if not finnhub_key:
            raise ValueError("FINNHUB_API_KEY not found")
        self.finnhub_client = finnhub.Client(api_key=finnhub_key)
    
    async def fetch_finviz_ipos(self) -> list:
        """Scrape Finviz for recent IPOs under $5."""
        import re
        from urllib.request import Request, urlopen
        
        def extract_text(tag_content):
            """Extract text from HTML tag."""
            text = re.sub(r'<[^>]+>', '', tag_content)
            return text.replace('&amp;', '&').strip()
        
        def scrape_page(page_start):
            """Scrape one page of Finviz results."""
            url = f'https://finviz.com/screener.ashx?v=111&f=cap_small,ipodate_prev5yrs,sh_price_u5&r={page_start}'
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            html = urlopen(req).read().decode('utf-8')
            
            rows = re.findall(r'<tr class="styled-row[^>]*>(.*?)</tr>', html, re.DOTALL)
            stocks = []
            for row in rows:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                if len(cells) >= 11:
                    stock_data = [extract_text(cell) for cell in cells]
                    stocks.append({
                        'ticker': stock_data[1],
                        'company': stock_data[2],
                        'sector': stock_data[3],
                        'industry': stock_data[4],
                        'country': stock_data[5],
                        'market_cap': stock_data[6],
                        'pe': stock_data[7],
                        'price': stock_data[8],
                        'change': stock_data[9],
                        'volume': stock_data[10]
                    })
            return stocks
        
        try:
            logger.info("Scraping Finviz IPO screener...")
            all_stocks = []
            for page_start in [1, 21, 41]:
                stocks = scrape_page(page_start)
                all_stocks.extend(stocks)
                await asyncio.sleep(1)
            logger.info(f"Scraped {len(all_stocks)} IPO stocks from Finviz")
            return all_stocks
        except Exception as e:
            logger.error(f"Failed to scrape Finviz: {str(e)}")
            return []
    
    def format_ipo_table(self, data: list) -> str:
        """Format IPO data as a table in code block."""
        if not data:
            return "```\nNo IPO data available\n```"
        
        header = f"📈 **Recent IPOs (Small Cap, <$5)** - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        
        # Table content
        lines = []
        lines.append("Ticker  Price   Chg%    MCap     Sector")
        lines.append("------  -----   -----   -------  ------")
        
        for stock in data:
            ticker = stock['ticker'][:6]
            price = f"${stock['price']}"[:6]
            change = stock['change'][:6]
            mcap = stock['market_cap'][:7]
            sector = stock['sector'][:20]
            
            line = f"{ticker:<6}  {price:<6}  {change:>6}  {mcap:<7}  {sector}"
            lines.append(line)
        
        table = "```" + "\n".join(lines) + "\n```"
        link = "\nIPOs → https://finviz.com/screener.ashx?v=111&f=cap_small,ipodate_prev5yrs,sh_price_u5"
        return header + table + link
    
    async def get_stock_data(self, ticker: str) -> dict:
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
                    
            except Exception as e:
                logger.warning(f"Finnhub API error - Unable to fetch profile for {ticker}: {str(e)}")
                name = ticker
                market_cap = 0
            
            # Skip basic financials to reduce API calls
            
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
                'market_cap': market_cap
            }
        except Exception as e:
            logger.error(f"Critical error - Failed to fetch data for {ticker}: {str(e)}")
            return None
    
    async def fetch_all_stocks(self) -> dict:
        """Fetch data for all tracked stocks."""
        all_data = {}
        for category, tickers in STOCKS.items():
            logger.info(f"Fetching {category} stocks: {tickers}")
            all_data[category] = []
            for ticker in tickers:
                data = await self.get_stock_data(ticker)
                if data:
                    all_data[category].append(data)
                await asyncio.sleep(1.5)  # Rate limiting: 1.5s between calls
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
        self.ipos_channel_id = int(os.getenv('DISCORD_IPOS_CHANNEL_ID', 0))
        self.logs_channel_id = int(os.getenv('DISCORD_LOGS_CHANNEL_ID', 0))
        
        # Set up Discord log handler
        if self.logs_channel_id:
            self.discord_handler = DiscordLogHandler(self.logs_channel_id)
            self.discord_handler.setLevel(logging.WARNING)
            self.discord_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            logger.addHandler(self.discord_handler)
        else:
            self.discord_handler = None
    
    async def on_ready(self):
        logger.info(f'Logged in as {self.user}')
        await self.send_screener_update()
        await self.send_ipos_update()
        
        # Send any buffered logs to Discord logs channel
        if self.discord_handler:
            await self.discord_handler.send_logs(self)
        
        await self.close()
    
    async def send_ipos_update(self):
        """Fetch IPO data from Finviz and send to Discord IPOs channel."""
        if not self.ipos_channel_id:
            logger.info("IPOs channel not configured, skipping")
            return
            
        channel = self.get_channel(self.ipos_channel_id)
        if not channel:
            logger.error(f"Critical error - IPOs channel {self.ipos_channel_id} not found")
            return
        
        logger.info("Fetching Finviz IPO data...")
        data = await self.screener.fetch_finviz_ipos()
        
        logger.info("Formatting IPO message...")
        message = self.screener.format_ipo_table(data)
        
        # Discord has a 2000 char limit, so split if needed
        if len(message) > 2000:
            chunks = [message[i:i+2000] for i in range(0, len(message), 2000)]
            for chunk in chunks:
                await channel.send(chunk)
        else:
            await channel.send(message)
        
        logger.info("IPO update sent!")
    
    async def send_screener_update(self):
        """Fetch stock data and send to Discord channel."""
        channel = self.get_channel(self.channel_id)
        if not channel:
            logger.error(f"Critical error - Feed channel {self.channel_id} not found")
            if self.discord_handler:
                await self.discord_handler.send_logs(self)
            return
        
        logger.info("Fetching stock data...")
        data = await self.screener.fetch_all_stocks()
        
        logger.info("Formatting message...")
        message = self.screener.format_table(data)
        
        # Discord has a 2000 char limit, so split if needed
        if len(message) > 2000:
            chunks = [message[i:i+2000] for i in range(0, len(message), 2000)]
            for chunk in chunks:
                await channel.send(chunk)
        else:
            await channel.send(message)
        
        logger.info("Update sent!")


def main():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN not found")
    
    bot = DiscordBot()
    bot.run(token)


if __name__ == '__main__':
    main()
