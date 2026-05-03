# RGODIM LTD Freelance Agent - Documentation

## Overview
Autonomous freelance agent that browses cryptotask.org, analyzes jobs using MiniMax AI, applies to matching opportunities, and notifies via Telegram.

## Architecture
- **Browser**: Camfox (anti-detect browser) on rpi4-server port 9377
- **AI**: MiniMax API (MiniMax-M2.7 model) for job matching and proposal generation
- **Notifications**: Telegram bot @rgodim_freelancer_bot
- **Platform**: rpi4-server (100.67.51.113), Python 3.13

## Company Profile (RGODIM LTD)
- **Services**: Web Development, Backend (Python/Node.js), API Development, AI/LLM Integration, Blockchain/Smart Contracts, DevOps, Data Engineering
- **Interested in**: All web development, backend, API, blockchain, smart contract, AI integration, DevOps tasks
- **NOT interested**: Graphic design, video editing, content writing, data entry, mobile apps only, copywriting

## Skills & Capabilities
- Python, Node.js, JavaScript/TypeScript
- FastAPI, Flask, Express.js, Django
- PostgreSQL, MongoDB, Redis
- Docker, Kubernetes, CI/CD
- Smart Contracts (Solidity), Web3, Ethereum
- AI/LLM Integration (OpenAI, Anthropic, MiniMax)
- AWS, GCP, Azure
- REST APIs, GraphQL
- Git, Linux administration

## Safeguards
1. **Never apply to**: Graphic design, UI/UX design, logo design, video editing, content writing, copywriting, data entry, SEO-only, mobile-only apps without backend
2. **Never say**: Discriminatory, offensive, or inappropriate things to clients
3. **Never misrepresent**: Always be honest about capabilities and availability
4. **Proposal tone**: Professional, concise, confident but not arrogant
5. **Budget floor**: Skip jobs paying less than $100 total unless they're very quick
6. **Always confirm**: Key decisions with Telegram notification before acting irreversibly

## Telegram Commands
- `status` - Check agent and Camfox status
- `browse` - Trigger immediate job scan
- `apply <url>` - Apply to specific job
- `applied` - Show recent applications
- `portfolio` - View RGODIM LTD portfolio

## API Credentials
- MiniMax API: `https://api.minimaxi.com/v1/chat/completions`
- MiniMax Model: `MiniMax-M2.7`
- Telegram Bot: @rgodim_freelancer_bot
- CryptoTask: rom.godinho@gmail.com

## Files
- `cryptotask-agent.py` - Main agent script
- `PORTFOLIO.md` - Company portfolio and past work
- `CLIENT_PROFILES.md` - Client interaction history and preferences
- `README.md` - This file
