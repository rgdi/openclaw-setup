#!/usr/bin/env python3
"""
OpenClaw CryptoTask Agent - Camfox browser + MiniMax + Telegram
Runs via cron every 4 hours to browse cryptotask.org and notify via Telegram.
Uses subprocess curl for HTTP (more reliable than urllib on Python 3.13).
"""
import subprocess, json, sys, os, time
from datetime import datetime

BOT = "8612653411:AAE_KvNbuxIBeBP_uocTWaN3xlOBpqiva3k"
CHAT = "6793940199"
KEY = "sk-cp-BcbH2nSRvdE2UIre4CjFNTMDDrn7K4NtFosQBfJ76HRy5RtC4ptsm_ehRR1G2YzhRIDu66aEEiI5RQoH_MMajgIqK_mwqMXChO-2eIa7EckxFvfk9UWoXdc"
BASE = "https://api.minimax.io/v1"
CAMFOX = "http://127.0.0.1:9377"

def curl(method, url, data=None, timeout=30):
    """Call HTTP endpoint via subprocess curl."""
    cmd = ["curl", "-s", "-X", method, url]
    if data:
        cmd += ["-d", json.dumps(data), "-H", "Content-Type: application/json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except Exception as e:
        pass
    return None

def send(msg):
    data = {"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"}
    r = curl("POST", f"https://api.telegram.org/bot{BOT}/sendMessage", data)
    return r.get("ok") if r else False

def ai(prompt, tokens=500):
    data = {
        "model": "MiniMax-M2.7",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": tokens
    }
    headers = ["-H", f"Authorization: Bearer {KEY}", "-H", "Content-Type: application/json"]
    cmd = ["curl", "-s", "-X", "POST", f"{BASE}/chat/completions", "-d", json.dumps(data)] + headers
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode == 0:
            resp = json.loads(result.stdout)
            return resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {e}"
    return "Error: no response"

def camfox_req(method, path, data=None):
    url = f"{CAMFOX}{path}"
    return curl(method, url, data, timeout=30)

def create_tab():
    r = camfox_req("POST", "/tabs", {"userId": "cryptotask-agent", "sessionKey": "job-scan"})
    return r.get("tabId") if r else None

def close_tab(tabId):
    if tabId:
        camfox_req("DELETE", f"/tabs/{tabId}?userId=cryptotask-agent")

def browse_and_snapshot(url, scroll=0):
    tabId = create_tab()
    if not tabId:
        return None, None, "Failed to create tab"
    
    r = camfox_req("POST", f"/tabs/{tabId}/navigate", {"userId": "cryptotask-agent", "url": url})
    if r and r.get("error"):
        close_tab(tabId)
        return None, None, r.get("error")
    
    time.sleep(4)
    if scroll:
        camfox_req("POST", f"/tabs/{tabId}/scroll", {"userId": "cryptotask-agent", "direction": "down", "amount": scroll})
        time.sleep(1)
    
    snap = camfox_req("GET", f"/tabs/{tabId}/snapshot?userId=cryptotask-agent")
    links_r = camfox_req("GET", f"/tabs/{tabId}/links?userId=cryptotask-agent&limit=30")
    links = links_r.get("links", []) if links_r else []
    close_tab(tabId)
    
    return snap.get("snapshot", "") if snap else "", links, None

def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    if action == "status":
        r = camfox_req("GET", "/")
        if r and r.get("ok"):
            send(f"OK Claude Agent Alive {ts}")
            send(f"Camfox: browser={r.get('browserRunning')} connected={r.get('browserConnected')}")
        else:
            send(f"Camfox error: {r}")
    
    elif action == "browse":
        send(f"Job scan started {ts}\nBrowsing cryptotask.org...")
        snapshot, links, err = browse_and_snapshot("https://cryptotask.org/en/tasks", scroll=800)
        
        if err or not snapshot:
            send(f"Scan failed: {err or 'no snapshot'}")
            return
        
        links_text = "\n".join([f"- {l.get('href','')} {l.get('text','')[:50]}" for l in links[:15] if l.get('href')])[:2000]
        
        prompt = f"""You are a job analyst for RGODIM LTD (software dev company). Analyze this page from cryptotask.org:

SNAPSHOT:
{snapshot[:8000]}

LINKS:
{links_text}

Identify the top 5 most relevant jobs. Focus: Blockchain, Backend, API, AI, DevOps, Data Engineering.
Exclude: Design, Marketing, Writing jobs.

Return markdown with: title, client, budget, skills, match reason, apply link. Max 5 jobs."""
        
        result = ai(prompt, 800)
        send(f"Top Jobs for RGODIM LTD:\n\n{result[:3500]}")
    
    elif action == "apply":
        if len(sys.argv) < 3:
            send("Usage: apply <job_link>"); sys.exit(1)
        link = sys.argv[2]
        send(f"Applying to: {link}\nBrowsing job...")
        snapshot, _, err = browse_and_snapshot(link)
        
        if err or not snapshot:
            send(f"Failed to load: {err or 'no content'}")
            return
        
        prompt = f"""Write a professional job proposal for RGODIM LTD (rom.godinho@gmail.com).

Job content:
{snapshot[:6000]}

Include: company intro, experience, proposed solution, pricing, timeline.
Return full proposal text."""
        
        result = ai(prompt, 1000)
        send(f"Proposal for {link}:\n\n{result[:3500]}")
    
    else:
        send(f"Unknown action: {action}")

if __name__ == "__main__": main()
