#!/usr/bin/env python3
"""
OpenClaw CryptoTask Agent - Cron-driven freelance agent
Runs via cron to browse cryptotask.org and notify via Telegram.
Uses direct MiniMax API calls + Telegram bot.
"""

import subprocess
import json
import sys
from datetime import datetime

TELEGRAM_BOT_TOKEN = "8612653411:AAE_KvNbuxIBeBP_uocTWaN3xlOBpqiva3k"
TELEGRAM_CHAT_ID = "6793940199"
MINIMAX_API_KEY = "sk-cp-BcbH2nSRvdE2UIre4CjFNTMDDrn7K4NtFosQBfJ76HRy5RtC4ptsm_ehRR1G2YzhRIDu66aEEiI5RQoH_MMajgIqK_mwqMXChO-2eIa7EckxFvfk9UWoXdc"
MINIMAX_BASE_URL = "https://api.minimax.io/v1"

def send_telegram(msg: str) -> bool:
    """Send message via Telegram bot."""
    import urllib.request
    import urllib.parse
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    })
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=data.encode()
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def call_minimax(prompt: str, max_tokens: int = 500) -> str:
    """Call MiniMax API directly."""
    import urllib.request
    data = json.dumps({
        "model": "MiniMax-M2.7",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens
    }).encode()
    req = urllib.request.Request(
        f"{MINIMAX_BASE_URL}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {MINIMAX_API_KEY}",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            return resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {e}"

def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if len(sys.argv) < 2:
        print("Usage: cryptotask-agent.py [browse|status|apply]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "status":
        send_telegram(f"✅ *CryptoTask Agent Alive*\n\n{timestamp}\n\nOpenClaw + MiniMax + Telegram pipeline operational.")
        print("Status sent")
        
    elif action == "browse":
        send_telegram(f"🔍 *Job Scan Started*\n\n{timestamp}\n\nScanning cryptotask.org for relevant positions...")
        
        prompt = """You are an expert freelance job analyst. Browse these cryptotask.org job categories and identify the BEST opportunities for a software development company (RGODIM LTD).

Focus on jobs matching these skills:
- Blockchain / Smart Contract / Web3
- Backend / API Development
- AI / Machine Learning
- DevOps / System Administration
- Data Engineering

Return a JSON array of the top 5 most relevant jobs with:
- Job title
- Client name  
- Budget (monthly or hourly)
- Key skills required
- Why it's a good match for RGODIM LTD
- Apply link

Only include non-design jobs. Format as clean markdown."""
        
        result = call_minimax(prompt, max_tokens=800)
        
        if result.startswith("Error:"):
            send_telegram(f"❌ *Job Scan Failed*\n\n{result[:500]}")
        else:
            send_telegram(f"✅ *Job Scan Complete*\n\n{timestamp}\n\n{result[:3500]}")
        
    elif action == "apply":
        if len(sys.argv) < 3:
            send_telegram("Usage: apply <job_link>")
            sys.exit(1)
        job_link = sys.argv[2]
        send_telegram(f"📝 *Applying to Job*\n\n{job_link}\n\nPreparing proposal...")
        
        prompt = f"""You are a professional freelancer applying for jobs on behalf of RGODIM LTD (rom.godinho@gmail.com).

Go to {job_link} and:
1. Read the full job description
2. Write a professional, compelling proposal
3. Include: company introduction, relevant experience, proposed approach, pricing

Keep the proposal concise but impressive. Return the full proposal text."""
        
        result = call_minimax(prompt, max_tokens=1000)
        
        if result.startswith("Error:"):
            send_telegram(f"❌ *Apply Failed*\n\n{result[:500]}")
        else:
            send_telegram(f"📝 *Proposal Ready*\n\n{job_link}\n\n{result[:3500]}")
    
    else:
        send_telegram(f"Unknown action: {action}")

if __name__ == "__main__":
    main()
