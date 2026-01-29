# 🚀 Atalanta - MegaETH Trading Bot

**Atalanta** is a professional Telegram bot designed for ultra-fast trading on MegaETH, the real-time Layer 2 with 10ms block times and 100k+ TPS. Built for the February 9, 2026 MegaETH mainnet launch.

## ⚡ Core Features

### 🎯 Real-Time Token Sniping
- **Lightning-fast execution** on new token launches
- **AI-powered safety checks** (honeypot detection, liquidity analysis)
- **WebSocket monitoring** of Kumbaya factory contracts
- **Anti-rug protection** with configurable parameters

### 💱 Multi-DEX Arbitrage
- **Cross-DEX scanning** across Kumbaya, PrismFi, GTE, Valhalla, WarpExchange
- **Real-time opportunity detection** with profit calculations
- **Flash-swap execution** for maximum efficiency
- **Gas optimization** and automatic routing

### 🤖 AI Predictions
- **Token launch scoring** (0-100 scale with confidence)
- **Price movement prediction** using lightweight ML models
- **Pump signal detection** from trading patterns
- **Risk assessment** based on on-chain data

### 📊 Advanced Features
- **Perpetuals liquidation hunting** on Valhalla/GTE
- **KPI farming automation** with adaptive strategies
- **Gamification system** with points, badges, leaderboards
- **Referral program** (20% commission)
- **Premium subscription tier**

## 🔒 Security First

- **No private key storage** - ever
- **WalletConnect integration** for secure signing
- **EIP-712 typed data** for all transactions
- **Rate limiting** and DDoS protection
- **Comprehensive audit logging**

## 🏗️ Architecture

```
Atalanta/
├── main.py                 # Bot startup & Application builder
├── config.py               # Configuration & constants
├── database.py             # SQLite wrapper (aiosqlite)
├── dex/
│   ├── kumbaya.py          # Kumbaya DEX integration
│   ├── prismfi.py          # PrismFi DEX integration
│   └── multi_dex.py        # Arbitrage scanner
├── sniper/
│   ├── monitor.py          # WebSocket event monitoring
│   └── executor.py         # Trade execution logic
├── ai/
│   └── predictor.py        # ML scoring & predictions
├── handlers/
│   ├── commands.py         # Telegram command handlers
│   ├── callbacks.py        # Inline button handlers
│   └── wallet.py           # WalletConnect integration
├── utils/
│   ├── formatting.py       # Message formatting helpers
│   └── security.py         # Rate limiting & validation
└── .env.example            # Environment variables template
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Telegram Bot Token
- MegaETH RPC access
- WalletConnect Project ID (optional)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-repo/atalanta-bot.git
cd atalanta-bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Run the bot**
```bash
python main.py
```

## ⚙️ Configuration

### Environment Variables

```env
# Telegram Configuration
TELEGRAM_TOKEN=your_bot_token_here
BOT_USERNAME=AtalantaBot

# MegaETH Configuration
MEGAETH_RPC=https://rpc.megaeth.com
MEGAETH_WS=wss://ws.megaeth.com

# WalletConnect
WALLETCONNECT_PROJECT_ID=your_project_id

# Bot Settings
LOG_LEVEL=INFO
REQUESTS_PER_SECOND=10
REQUESTS_PER_MINUTE=100
```

### Contract Addresses

The bot is pre-configured for MegaETH mainnet:
- **Kumbaya Factory**: `0x53447989580f541bc138d29A0FcCf72AfbBE1355`
- **Kumbaya Router**: `0x8268DC930BA98759E916DEd4c9F367A844814023`

## 📱 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message & main menu |
| `/snipe <address> [amount] [slippage]` | Snipe new token launch |
| `/arb` | Show arbitrage opportunities |
| `/predict <address>` | Get AI token analysis |
| `/wallet` | Manage wallet connection |
| `/farm` | KPI farming features |
| `/stats` | Global leaderboard |
| `/help` | Show help message |

## 🔧 Advanced Usage

### Custom Sniping Parameters

```bash
# Snipe with 0.1 ETH and 2% max slippage
/snipe 0x1234...abcd 0.1 2

# Quick snipe with defaults (0.1 ETH, 2% slippage)
/snipe 0x1234...abcd
```

### AI Scoring Factors

The AI predictor analyzes:
- **Liquidity depth** (ETH locked)
- **Holder distribution**
- **Transaction volume & patterns**
- **Developer wallet behavior**
- **Social sentiment indicators**
- **Contract security features**

### Arbitrage Configuration

```python
# Minimum profit threshold
MIN_PROFIT_THRESHOLD = 0.005  # 0.5%

# Scan interval
SCAN_INTERVAL = 5  # seconds

# Maximum gas price
MAX_GAS_PRICE = int(5e10)  # 50 gwei
```

## 🛡️ Security Features

### Rate Limiting
- **Per-user limits**: 10 requests/second, 100/minute
- **Global protection**: DDoS mitigation
- **Custom limits** for premium users

### Input Validation
- **Address validation** with checksum verification
- **Amount range checking**
- **SQL injection prevention**
- **XSS protection**

### Transaction Security
- **EIP-712 typed data signing**
- **WalletConnect protocol**
- **Transaction simulation**
- **Gas estimation limits**

## 📊 Monitoring & Analytics

### Health Checks
```python
# Bot health status
GET /health

# Component status
- Database connectivity
- Web3 connection
- DEX availability
- Monitoring services
```

### Performance Metrics
- **Response times**
- **Success rates**
- **Error tracking**
- **User engagement**

## 🔄 Development

### Running Tests

```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/integration/

# Coverage report
pytest --cov=atalanta tests/
```

### Code Quality

```bash
# Code formatting
black .

# Linting
flake8 .

# Type checking
mypy .
```

### Database Schema

The bot uses SQLite with the following tables:
- **users** - User data & preferences
- **trades** - Trade history & results
- **arbitrage_opportunities** - Scanned opportunities
- **predictions** - AI prediction records
- **user_stats** - Performance statistics

## 🚀 Deployment

### Docker Deployment

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

### Production Setup

1. **Environment configuration**
2. **Database initialization**
3. **SSL/TLS setup**
4. **Monitoring integration**
5. **Backup procedures**

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

**IMPORTANT**: This bot is for educational and research purposes only. Cryptocurrency trading involves substantial risk of loss. Use at your own risk. The developers are not responsible for any financial losses.

- **Never invest more than you can afford to lose**
- **Always do your own research (DYOR)**
- **Understand the risks of DeFi trading**
- **Keep your private keys secure**

## 🆘 Support

- **Documentation**: [Wiki](https://github.com/your-repo/atalanta-bot/wiki)
- **Issues**: [GitHub Issues](https://github.com/your-repo/atalanta-bot/issues)
- **Discord**: [Community Server](https://discord.gg/atalanta)
- **Twitter**: [@AtalantaBot](https://twitter.com/AtalantaBot)

---

**Built with ❤️ for the MegaETH ecosystem**

*Become a MegaETH degen with Atalanta! 🎯*
