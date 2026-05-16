# 🤖 Personal All-in-One Telegram Bot

A feature-rich Telegram bot that combines AI chat capabilities, project management, file handling, and administrative controls in one powerful package.

## ✨ Features

- **🤖 AI Chat** - Powered by DeepSeek for intelligent conversations
- **📁 Project Generation** - Create and push projects to GitHub automatically
- **📎 File Handling** - Process and manage various file types
- **🛡️ Admin Controls** - Comprehensive admin panel for bot management
- **⚡ Async/Await** - High performance with asynchronous operations
- **🔒 Type Safety** - Full type hints for better code reliability

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- GitHub Personal Access Token
- DeepSeek API Key

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/telegram-bot.git
cd telegram-bot
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your credentials:
# - TELEGRAM_BOT_TOKEN
# - DEEPSEEK_API_KEY
# - GITHUB_TOKEN
# - ADMIN_IDS (comma-separated)
```

5. **Initialize database**
```bash
python -m bot.database
```

6. **Run the bot**
```bash
python main.py
```

## 📋 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather | ✅ |
| `DEEPSEEK_API_KEY` | DeepSeek API key for AI chat | ✅ |
| `GITHUB_TOKEN` | GitHub personal access token | ✅ |
| `ADMIN_IDS` | Comma-separated Telegram user IDs | ✅ |
| `DATABASE_PATH` | SQLite database path (default: bot.db) | ❌ |
| `LOG_LEVEL` | Logging level (default: INFO) | ❌ |

### Admin Setup

1. Get your Telegram user ID from [@userinfobot](https://t.me/userinfobot)
2. Add it to `ADMIN_IDS` in `.env`
3. Restart the bot

## 🎮 Usage

### User Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and see welcome message |
| `/help` | Show available commands |
| `/chat <message>` | Chat with AI assistant |
| `/generate <description>` | Generate a project from description |
| `/push <repo_name>` | Push generated project to GitHub |
| `/file` | Upload and process files |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/admin` | Open admin panel |
| `/stats` | View bot statistics |
| `/broadcast <message>` | Send message to all users |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/logs` | View recent logs |

### AI Chat Examples

```
User: /chat What is Python?
Bot: Python is a high-level, interpreted programming language...

User: /chat Write a function to calculate fibonacci
Bot: Here's a Python function for fibonacci sequence...
```

### Project Generation

```
User: /generate Create a REST API with FastAPI
Bot: Generating project structure...
     - Created: main.py
     - Created: requirements.txt
     - Created: models.py
     - Created: routes.py
     
User: /push my-api-project
Bot: Pushing to GitHub...
     ✓ Repository created: my-api-project
     ✓ Code pushed successfully
```

## 🏗️ Project Structure

```
telegram-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Bot entry point
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── chat.py          # AI chat handlers
│   │   ├── project.py       # Project generation handlers
│   │   ├── file.py          # File handling handlers
│   │   └── admin.py         # Admin command handlers
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_service.py    # DeepSeek integration
│   │   ├── github_service.py # GitHub API integration
│   │   └── file_service.py  # File processing service
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py        # Database models
│   │   └── operations.py    # Database operations
│   └── utils/
│       ├── __init__.py
│       ├── decorators.py    # Custom decorators
│       └── helpers.py       # Utility functions
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration management
├── tests/
│   ├── __init__.py
│   ├── test_chat.py
│   ├── test_project.py
│   └── test_admin.py
├── .env.example             # Environment template
├── requirements.txt         # Python dependencies
├── main.py                  # Application entry point
└── README.md                # This file
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_chat.py

# Run with coverage
pytest --cov=bot tests/
```

## 📦 Dependencies

- **python-telegram-bot** - Telegram Bot API wrapper
- **openai** - DeepSeek API client
- **PyGithub** - GitHub API client
- **aiosqlite** - Async SQLite database
- **aiofiles** - Async file operations
- **Pillow** - Image processing
- **python-dotenv** - Environment management
- **pydantic** - Data validation
- **loguru** - Logging

## 🔒 Security

- All API keys stored in environment variables
- Admin-only commands protected by user ID verification
- Input sanitization for all user inputs
- Rate limiting on API calls
- Secure database with parameterized queries

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [DeepSeek](https://deepseek.com/) for AI capabilities
- [python-telegram-bot](https://python-telegram-bot.org/) for bot framework
- [GitHub](https://github.com/) for project hosting

## 📞 Support

For issues and feature requests, please [open an issue](https://github.com/yourusername/telegram-bot/issues).

---

**Made with ❤️ by [Your Name]**