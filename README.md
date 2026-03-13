# Stock Screener Bot

Discord bot that posts stock updates for a curated watchlist using Finnhub API.

## Stocks Tracked

- **AI**: BBAI, CRNC, DV, RXRX
- **Energy**: BLDP, CLNE, FCEL, GEVO, LAC, NRGV, OPAL
- **EVs**: ABAT, AIOT, ENVX, EVGO, NKLA, SES, SLDP, TE
- **Environmental**: NPWR
- **Semiconductors**: NVTS
- **Space**: RDW, SPIR
- **Fintech**: MQ
- **Healthcare**: ALT, ATAI, CGC, CMPS, CRON, GDRX, HELP, PACB, SANA, TDOC, TLRY
- **Education**: COUR, UDMY
- **Software**: PD

## Setup

### 1. Discord Bot Setup
1. Go to https://discord.com/developers/applications
2. Click "New Application" and name it (e.g., "Stock Screener")
3. Go to "Bot" tab → "Add Bot"
4. Copy the Bot Token
5. Enable "Message Content Intent" under Privileged Gateway Intents
6. Go to "OAuth2" → "URL Generator"
   - Scopes: `bot`
   - Permissions: `Send Messages`, `Read Messages/View Channels`
7. Copy the generated URL and open in browser to add bot to your server
8. In Discord: Enable Developer Mode (Settings → Advanced → Developer Mode)
9. Right-click your target channel → "Copy Channel ID"

### 2. Environment Setup
```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your keys:
# - FINNHUB_API_KEY (from finnhub.io)
# - DISCORD_BOT_TOKEN (from step 1)
# - DISCORD_CHANNEL_ID (from step 1)

# Install dependencies
pip install -r requirements.txt
```

### 3. Run
```bash
python screener_bot.py
```

## Deployment (Oracle Free Tier)

Can be deployed as a scheduled job on Oracle Cloud Always Free tier using cron:
```bash
# Run daily at 4pm EST (market close)
0 16 * * 1-5 cd /path/to/screener && /usr/bin/python3 screener_bot.py
```

## API Limits

- Finnhub free tier: 60 calls/min
- Bot makes ~40 calls per run with 1 second delay between requests
- Safe to run multiple times per day
