#!/usr/bin/env python3
"""
OpenClaw CryptoTask Agent v4 - Full auto-bidding with learning + keyword fallback
Key changes:
- Keyword-based fallback when AI is unavailable
- Better login retry logic
- Telegram command handler
- Continuous watchdog loop
- Client learning memory
"""
import subprocess, json, time, re, sys, os
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
BOT   = "8612653411:AAE_KvNbuxIBeBP_uocTWaN3xlOBpqiva3k"
CHAT  = "6793940199"
KEY   = "sk-cp-8r2sLAzHvPzkwS7Z1yjPZWmZpBdP8YvWnQv2iHk6vBmKl4x7Y8eRmJc9nAoXdc"
BASE  = "https://api.minimaxi.com/v1"
MODEL = "MiniMax-M2.7"
CAMFOX = "http://127.0.0.1:9377"
CT_USER = "rom.godinho@gmail.com"
CT_PASS = "Mar!s0l2025"
AGENT_SID = "rgodim_agent"

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO = os.path.join(BASE_DIR, "PORTFOLIO.md")
CLIENT_PROFILES = os.path.join(BASE_DIR, "CLIENT_PROFILES.md")
APPLIED_FILE = os.path.join(BASE_DIR, "applied_jobs.json")
LOG_FILE = os.path.join(BASE_DIR, "agent.log")

# ── Helpers ────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass

def curl(method, url, data=None, timeout=45):
    cmd = ["curl", "-s", "-X", method, "--max-time", str(timeout)]
    if data:
        cmd += ["-d", json.dumps(data), "-H", "Content-Type: application/json"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    return r.stdout

def cf(method, path, data=None):
    return curl(method, f"{CAMFOX}{path}", data)

def tg(msg):
    text = msg[:4096]
    try:
        curl("POST", f"https://api.telegram.org/bot{BOT}/sendMessage",
             {"chat_id": CHAT, "text": text, "parse_mode": "HTML"}, timeout=15)
    except:
        log(f"Telegram send failed")

def ai(prompt, max_tokens=600):
    """Call MiniMax with fallback to keyword matching."""
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    try:
        resp = curl("POST", f"{BASE}/chat/completions", data, timeout=30)
        d = json.loads(resp)
        if "choices" in d and d["choices"]:
            return d["choices"][0]["message"]["content"].strip()
        elif "error" in d:
            log(f"MiniMax error: {d['error'].get('message', d['error'])}")
            return None
    except Exception as e:
        log(f"MiniMax exception: {e}")
    return None

# ── Keyword fallback matcher ────────────────────────────────────────────────
INTERESTED = [
    "web", "backend", "frontend", "python", "node", "javascript", "typescript",
    "api", "rest", "graphql", "database", "postgresql", "mongodb", "docker",
    "devops", "cloud", "aws", "gcp", "blockchain", "smart contract", "solidity",
    "web3", "nft", "ethereum", "bitcoin", "llm", "ai", "machine learning",
    "fastapi", "flask", "django", "express", "react", "vue", "kubernetes",
    "ci/cd", "linux", "server", "microservice", "data pipeline", "etl",
    "scraper", "automation", "script", "integration", "smart-contract",
    "solidity", "web3.js", "ethers.js", "defi", "dao", "token"
]

SKIP = [
    "design", "logo", "graphic", "illustration", "video", "animation",
    "photoshop", "illustrator", "figma", "ui/ux", "ui design", "ux design",
    "content writing", "copywriting", "blog post", "article writing",
    "data entry", "excel", "spreadsheet", "virtual assistant", "seo",
    "social media", "marketing only", "mobile app only", "ios only", "android only",
    "swift", "kotlin", "react native", "flutter"
]

def keyword_score(title, desc=""):
    """Score 0-10 based on keyword matching."""
    text = (title + " " + desc).lower()
    if any(kw in text for kw in SKIP):
        return 0, "skip: excluded category"
    matches = [kw for kw in INTERESTED if kw.lower() in text]
    if not matches:
        return 0, "no matching skills"
    score = min(10, 4 + len(matches) * 1.5)
    return score, f"keywords: {', '.join(matches[:4])}"

def generate_proposal_fallback(job_title, client_name=""):
    """Generate basic proposal without AI."""
    return f"""Hello{', ' + client_name if client_name else ''},

I noticed your project "{job_title}" and I'd love to help.

I'm a full-stack developer at RGODIM LTD specializing in backend systems, APIs, blockchain integration, and AI-powered applications. I've built similar projects before and can deliver quality work on time.

What specific requirements do you have? I'm happy to discuss the project in detail and provide a clear timeline.

Best regards,
RGODIM LTD
rom.godinho@gmail.com"""

# ── Camfox helpers ──────────────────────────────────────────────────────────
def camfox_ok():
    try:
        d = json.loads(cf("GET", "/"))
        return d.get("browserRunning") and d.get("browserConnected")
    except:
        return False

def ensure_tab(url="https://cryptotask.org/en/tasks", session=None):
    sid = session or AGENT_SID
    resp = cf("POST", "/tabs", {"userId": sid, "sessionKey": sid, "url": url})
    d = json.loads(resp)
    tabId = d.get("tabId")
    if tabId:
        time.sleep(6)
    return tabId, sid

def close_tab(tabId, userId=None):
    if tabId:
        cf("DELETE", f"/tabs/{tabId}?userId={userId or AGENT_SID}")

def get_snapshot(tabId, userId=None, full=True):
    snap = cf("GET", f"/tabs/{tabId}/snapshot?userId={userId or AGENT_SID}&full={str(full).lower()}")
    try:
        d = json.loads(snap)
        return d.get("snapshot", ""), d.get("url", "")
    except:
        return "", ""

def click_ref(tabId, ref, userId=None):
    r = cf("POST", f"/tabs/{tabId}/click", {"userId": userId or AGENT_SID, "ref": ref})
    try:
        return json.loads(r).get("ok", False)
    except:
        return False

def type_ref(tabId, ref, text, userId=None):
    r = cf("POST", f"/tabs/{tabId}/type", {"userId": userId or AGENT_SID, "ref": ref, "text": text})
    try:
        return json.loads(r).get("ok", False)
    except:
        return False

def navigate(tabId, url, userId=None):
    r = cf("POST", f"/tabs/{tabId}/navigate", {"userId": userId or AGENT_SID, "url": url})
    try:
        return json.loads(r).get("ok", False)
    except:
        return False

def extract_refs(snapshot):
    refs = {}
    for line in snapshot.split("\n"):
        m = re.search(r'\[e(\d+)\]', line)
        if m:
            idx = int(m.group(1))
            for t in ["textbox", "button", "link"]:
                lm = re.search(rf'{t} "([^"]+)"', line)
                if lm:
                    refs[idx] = {"type": t, "label": lm.group(1)}
                    break
            else:
                refs[idx] = {"type": "element", "label": ""}
    return refs

def extract_jobs(snapshot):
    jobs = []
    seen = set()
    urls = re.findall(r"/url: (/en/tasks/[a-z0-9-]+/\d+)", snapshot)
    headings = re.findall(r'heading "([^"]+)" \[level=\d+\]:', snapshot)
    for i, url in enumerate(urls):
        if url in seen:
            continue
        seen.add(url)
        title = headings[i] if i < len(headings) else "?"
        jobs.append({"url": f"https://cryptotask.org{url}", "title": title})
    return jobs

# ── CryptoTask Login ────────────────────────────────────────────────────────
def ct_login(tabId):
    """Login via browser form. Returns True if successful."""
    log("Attempting CryptoTask login...")
    navigate(tabId, "https://cryptotask.org/en/login")
    time.sleep(7)
    
    snap, url = get_snapshot(tabId)
    refs = extract_refs(snap)
    
    # Find form fields
    email_ref = pass_ref = submit_ref = None
    for idx, info in refs.items():
        label = info.get("label", "").lower()
        if "email" in label and info["type"] == "textbox":
            email_ref = f"e{idx}"
        elif "password" in label and info["type"] == "textbox":
            pass_ref = f"e{idx}"
        elif info["type"] == "button" and ("login" in label or "submit" in label or "sign in" in label):
            submit_ref = f"e{idx}"
    
    if not email_ref or not pass_ref:
        log(f"Cannot find login form. Available refs: {dict(list(refs.items())[:10])}")
        return False
    
    if not submit_ref:
        submit_ref = email_ref  # Try clicking email field as fallback
    
    log(f"Login fields: email={email_ref}, pass={pass_ref}, submit={submit_ref}")
    
    # Type credentials
    type_ref(tabId, email_ref, CT_USER)
    time.sleep(0.5)
    type_ref(tabId, pass_ref, CT_PASS)
    time.sleep(0.5)
    
    # Click submit
    click_ref(tabId, submit_ref)
    time.sleep(10)
    
    # Check result
    snap2, url2 = get_snapshot(tabId)
    if "/en/login" in url2:
        log("Login FAILED - still on login page")
        return False
    
    log(f"Login SUCCESS - now at: {url2}")
    return True

# ── Proposal generation ──────────────────────────────────────────────────────
def generate_proposal(job_title, job_desc, budget, client_name):
    """Generate proposal with AI, fallback to keyword template."""
    prompt = f"""You are RGODIM LTD writing a freelance proposal.

Job: {job_title}
Budget: {budget}
Client: {client_name}
Description: {job_desc[:800]}

Write a 150-250 word proposal. Be professional, specific, show relevant skills.
Output ONLY the proposal text."""
    
    result = ai(prompt, 350)
    if result:
        return result
    
    log("Using fallback proposal (AI unavailable)")
    return generate_proposal_fallback(job_title, client_name)

# ── Apply to job ────────────────────────────────────────────────────────────
def apply_to_job(tabId, job_url, job_title, budget):
    """Navigate to job and apply."""
    log(f"Applying to: {job_title}")
    
    navigate(tabId, job_url)
    time.sleep(8)
    
    snap, _ = get_snapshot(tabId)
    refs = extract_refs(snap)
    
    # Check if logged in
    if "/en/login" in snap.lower() and "apply" in snap.lower():
        if not ct_login(tabId):
            return False, "Login failed"
        snap, _ = get_snapshot(tabId)
        refs = extract_refs(snap)
    
    # Find Apply button
    apply_ref = None
    for idx, info in refs.items():
        if info["type"] in ("button", "link") and "apply" in info.get("label", "").lower():
            apply_ref = f"e{idx}"
            break
    
    if not apply_ref:
        return False, "No Apply button found"
    
    log(f"Clicking Apply: {apply_ref}")
    click_ref(tabId, apply_ref)
    time.sleep(5)
    
    snap2, _ = get_snapshot(tabId)
    refs2 = extract_refs(snap2)
    
    # Extract client name
    client_name = ""
    cm = re.search(r'link "([^"]+)" \[e\d+\]:\s*/url: /en/clients/', snap)
    if cm:
        client_name = cm.group(1)
    
    # Find textarea for proposal
    textarea_ref = None
    for idx, info in refs2.items():
        if info["type"] in ("textbox", "textarea") or "textbox" in info.get("label", "").lower():
            textarea_ref = f"e{idx}"
            break
    
    # Generate proposal
    proposal = generate_proposal(job_title, snap[:1500], budget, client_name)
    
    if textarea_ref:
        log(f"Typing proposal into {textarea_ref}")
        type_ref(tabId, textarea_ref, proposal)
        time.sleep(2)
    
    # Find submit button
    submit_ref = None
    for idx, info in refs2.items():
        label = info.get("label", "").lower()
        if info["type"] == "button" and any(k in label for k in ["submit", "send", "apply", "confirm", "post"]):
            submit_ref = f"e{idx}"
            break
    
    if submit_ref:
        log(f"Submitting: {submit_ref}")
        click_ref(tabId, submit_ref)
        time.sleep(5)
    else:
        log("No submit button found")
        return False, "No submit button"
    
    # Verify
    snap3, _ = get_snapshot(tabId)
    if any(w in snap3.lower() for w in ["applied", "success", "submitted", "thank you"]):
        return True, proposal[:100]
    
    return True, "Applied (confirmation unclear)"

# ── Scan jobs ───────────────────────────────────────────────────────────────
def scan_all_pages(tabId, max_pages=10):
    """Scan multiple pages."""
    all_jobs = []
    seen = set()
    
    tg("🔍 Scanning cryptotask.org jobs...")
    
    for page in range(1, max_pages + 1):
        url = "https://cryptotask.org/en/tasks" if page == 1 else f"https://cryptotask.org/en/tasks?page={page}"
        log(f"Page {page}: {url}")
        
        navigate(tabId, url)
        time.sleep(8)
        
        snap, _ = get_snapshot(tabId)
        if not snap or len(snap) < 200:
            log(f"Page {page}: empty")
            break
        
        jobs = extract_jobs(snap)
        log(f"Page {page}: {len(jobs)} jobs")
        
        new = 0
        for job in jobs:
            if job["url"] not in seen:
                seen.add(job["url"])
                all_jobs.append(job)
                new += 1
        
        if len(jobs) < 5:
            break
        
        time.sleep(3)
    
    log(f"Total unique jobs: {len(all_jobs)}")
    return all_jobs

# ── Process jobs ─────────────────────────────────────────────────────────────
def process_jobs(tabId, jobs):
    """Evaluate and apply to matching jobs."""
    total = len(jobs)
    applied = []
    skipped = []
    errors = []
    
    tg(f"📋 Processing {total} jobs...")
    
    for i, job in enumerate(jobs):
        idx = i + 1
        title = job["title"]
        url = job["url"]
        
        log(f"[{idx}/{total}] {title[:60]}")
        
        # Score with fallback
        score, reason = keyword_score(title)
        if score == 0:
            log(f"  SKIP: {reason}")
            skipped.append({"title": title, "url": url, "reason": reason})
            continue
        
        # AI scoring if available
        ai_score = None
        ai_reason = None
        
        # Try AI rating
        ai_result = ai(f"Score 0-10 fit for RGODIM LTD (web dev, backend, blockchain, Python, API, AI). Job: {title[:100]}. Reply SCORE:X|REASON:...", 60)
        if ai_result and "SCORE:" in ai_result:
            try:
                ai_score = int(ai_result.split("SCORE:")[1].split("|")[0].strip())
                ai_reason = ai_result.split("REASON:")[1].strip() if "REASON:" in ai_result else ""
                score = (score + ai_score) / 2
                reason = f"{reason} | AI: {ai_reason[:40]}"
                log(f"  Score: {score:.1f}/10 (AI: {ai_reason[:60]})")
            except:
                log(f"  Score: {score}/10 ({reason})")
        else:
            log(f"  Score: {score}/10 ({reason})")
        
        if score < 4:
            log(f"  SKIP (low score)")
            skipped.append({"title": title, "url": url, "reason": f"score {score}"})
            continue
        
        # Apply
        success, msg = apply_to_job(tabId, url, title, job.get("budget", "?"))
        
        if success:
            applied.append({"title": title, "url": url, "score": round(score, 1)})
            tg(f"✅ <b>Applied:</b> {title}\nScore: {score:.0f}/10\n\n{message_preview(msg)}")
            log(f"  APPLIED: {msg[:80]}")
            learn_client_interaction(title, "Applied", msg)
        else:
            errors.append({"title": title, "url": url, "reason": msg})
            tg(f"❌ <b>Error applying:</b> {title}\n{msg}")
            log(f"  ERROR: {msg}")
        
        # Save applied
        save_applied(job, score, msg)
        time.sleep(5)
    
    return applied, skipped, errors

def message_preview(msg):
    if not msg:
        return ""
    return msg[:200] + "..." if len(msg) > 200 else msg

def save_applied(job, score, proposal):
    """Save applied job to file."""
    try:
        entry = {"time": datetime.now().isoformat(), "title": job["title"], "url": job["url"], "score": score}
        with open(APPLIED_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except:
        pass

def learn_client_interaction(job_title, outcome, proposal_preview):
    """Save client interaction for learning."""
    try:
        entry = f"""
### {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Job**: {job_title}
**Outcome**: {outcome}
**Preview**: {proposal_preview[:200]}
"""
        with open(CLIENT_PROFILES, "a") as f:
            f.write(entry)
    except:
        pass

# ── Telegram command handler ─────────────────────────────────────────────────
def handle_command(cmd, args):
    """Handle Telegram bot commands."""
    if cmd == "status":
        camfox_ok_val = camfox_ok()
        try:
            with open(LOG_FILE) as f:
                last = f.readlines()[-5:]
            last_lines = "".join(last)
        except:
            last_lines = "No log"
        
        tg(f"🤖 RGODIM LTD Agent\n"
           f"Camfox: {'✅ Running' if camfox_ok_val else '❌ Down'}\n"
           f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
           f"Commands: /browse /apply <url> /applied /portfolio\n\n"
           f"Recent log:\n{last_lines[:500]}")
    
    elif cmd == "browse":
        tg("🚀 Starting job scan...")
        action_browse()
    
    elif cmd == "apply":
        if not args:
            tg("Usage: /apply <job_url>")
        else:
            tg(f"🎯 Applying to:\n{args}")
            action_apply(args)
    
    elif cmd == "applied":
        try:
            with open(APPLIED_FILE) as f:
                lines = f.readlines()[-10:]
            if lines:
                msg = "📝 <b>Recent Applications:</b>\n\n"
                for line in lines:
                    job = json.loads(line)
                    msg += f"• {job['title']}\n  Score: {job.get('score','?')}/10\n  {job['url']}\n\n"
                tg(msg[:4096])
            else:
                tg("No applications yet.")
        except:
            tg("No applications file yet.")
    
    elif cmd == "portfolio":
        if os.path.exists(PORTFOLIO):
            with open(PORTFOLIO) as f:
                tg("📁 <b>RGODIM LTD Portfolio</b>\n\n" + f.read()[:4000])
        else:
            tg("Portfolio file not found.")
    
    elif cmd == "help":
        tg("Commands:\n/status - Agent status\n/browse - Scan & apply to jobs\n/apply <url> - Apply to specific job\n/applied - Recent applications\n/portfolio - View portfolio")
    
    else:
        tg(f"Unknown command: {cmd}\nCommands: /status, /browse, /apply <url>, /applied, /portfolio, /help")

# ── Main actions ────────────────────────────────────────────────────────────
def action_browse():
    if not camfox_ok():
        tg("❌ Camfox is not running.")
        return
    
    tabId, sid = ensure_tab(session=f"browse_{int(time.time())}")
    if not tabId:
        tg("❌ Cannot create browser tab.")
        return
    
    try:
        # Try login (ignore failure if already logged in)
        ct_login(tabId)
        
        jobs = scan_all_pages(tabId, max_pages=10)
        if not jobs:
            tg("❌ No jobs found.")
            return
        
        applied, skipped, errors = process_jobs(tabId, jobs)
        
        summary = (f"📊 <b>Scan Complete</b>\n"
                   f"Found: {len(jobs)}\n"
                   f"Applied: {len(applied)}\n"
                   f"Skipped: {len(skipped)}\n"
                   f"Errors: {len(errors)}\n"
                   f"Time: {datetime.now().strftime('%H:%M')}")
        tg(summary)
        log(f"Browse complete: {len(applied)} applied, {len(skipped)} skipped, {len(errors)} errors")
    finally:
        close_tab(tabId)

def action_apply(job_url):
    if not camfox_ok():
        tg("❌ Camfox is not running.")
        return
    
    tabId, sid = ensure_tab(session=f"apply_{int(time.time())}", url=job_url)
    if not tabId:
        tg("❌ Cannot create browser tab.")
        return
    
    try:
        ct_login(tabId)
        time.sleep(8)
        snap, _ = get_snapshot(tabId)
        
        title_m = re.search(r'heading "([^"]+)" \[level=1\]:', snap)
        title = title_m.group(1) if title_m else "Unknown Job"
        
        budget_m = re.search(r'\$[\d,]+(?:\.\d{2})?', snap)
        budget = budget_m.group() if budget_m else "?"
        
        score, reason = keyword_score(title, snap[:1000])
        
        success, msg = apply_to_job(tabId, job_url, title, budget)
        
        if success:
            tg(f"✅ <b>Applied:</b> {title}\nBudget: {budget}\nScore: {score:.0f}/10\n\n{message_preview(msg)}")
            save_applied({"title": title, "url": job_url}, score, msg)
            learn_client_interaction(title, "Applied", msg)
        else:
            tg(f"❌ <b>Failed:</b> {title}\n{msg}")
    finally:
        close_tab(tabId)

def check_telegram_commands():
    """Poll Telegram for new commands."""
    try:
        updates = curl("GET", f"https://api.telegram.org/bot{BOT}/getUpdates?timeout=1&offset=-1", timeout=5)
        d = json.loads(updates)
        if d.get("ok") and d.get("result"):
            for item in d["result"]:
                msg = item.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                if text and chat_id == int(CHAT) and text.startswith("/"):
                    parts = text[1:].split(" ", 1)
                    cmd = parts[0].lower()
                    args = parts[1] if len(parts) > 1 else ""
                    log(f"Telegram command: {cmd} {args}")
                    handle_command(cmd, args)
    except:
        pass

# ── Watchdog loop ───────────────────────────────────────────────────────────
def watchdog_loop():
    """Continuous loop: check commands + keep system alive."""
    log("Watchdog loop starting...")
    tg("🤖 RGODIM LTD Agent watchdog started")
    
    last_browse = 0
    browse_interval = 4 * 3600  # 4 hours
    
    while True:
        try:
            # Check Telegram commands
            check_telegram_commands()
            
            # Periodic browse
            now = time.time()
            if now - last_browse > browse_interval:
                log("Triggering periodic browse...")
                tg("🔄 Periodic job scan triggered")
                action_browse()
                last_browse = now
            
            time.sleep(30)  # Check every 30 seconds
            
        except KeyboardInterrupt:
            log("Watchdog stopped by user")
            break
        except Exception as e:
            log(f"Watchdog error: {e}")
            time.sleep(60)

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    
    if cmd == "watchdog":
        watchdog_loop()
    elif cmd == "browse":
        action_browse()
    elif cmd == "apply":
        if not arg:
            print("Usage: apply <job_url>")
        else:
            action_apply(arg)
    elif cmd == "status":
        handle_command("status", "")
    elif cmd == "telegram-poll":
        check_telegram_commands()
    else:
        print(f"Commands: status, browse, apply <url>, watchdog, telegram-poll")

if __name__ == "__main__":
    main()
