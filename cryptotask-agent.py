#!/usr/bin/env python3
"""
RGODIM LTD CryptoTask Agent v5 - Concurrent Tab Architecture
- Tab 1: Telegram polling (always alive)
- Tab 2: Job scanner (periodic every 4h)
- Tab 3: Apply workers (spawned on demand)
- Browser handles ALL CT interactions
- Keyword scoring as AI fallback
- Telegram notifications on all significant events
"""
import subprocess, json, time, re, sys, os, signal
from datetime import datetime, timedelta
from threading import Thread, Lock

# ── Config ──────────────────────────────────────────────────────────────────
BOT     = "8612653411:AAE_KvNbuxIBeBP_uocTWaN3xlOBpqiva3k"
CHAT    = "6793940199"
KEY     = "sk-cp-8r2sLAzHvPzkwS7Z1yjPZWmZpBdP8YvWnQv2iHk6vBmKl4x7Y8eRmJc9nAoXdc"
BASE    = "https://api.minimaxi.com/v1"
MODEL   = "MiniMax-M2.7"
CAMFOX  = "http://127.0.0.1:9377"
CT_HOST = "https://cryptotask.org"
CT_USER = "rom.godinho@gmail.com"
CT_PASS = "6yVb7HJX7pTfQ9V"

# ── Files ───────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO = os.path.join(BASE_DIR, "PORTFOLIO.md")
CLIENT_F  = os.path.join(BASE_DIR, "client_profiles.md")
APPLIED_F = os.path.join(BASE_DIR, "applied_jobs.json")
LOG_F     = os.path.join(BASE_DIR, "agent.log")
SID       = "rgodim_agent"

# ── Globals ──────────────────────────────────────────────────────────────────
tab_id       = None   # Telegram polling tab
tab_lock     = Lock()
browse_lock  = Lock()  # Prevent concurrent browse threads
browsing     = False   # Current browse state
last_browse  = 0
browse_interval = 4 * 3600  # 4 hours
shutdown     = False

# ── Helpers ──────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_F, "a") as f:
            f.write(line + "\n")
    except: pass

def curl(method, url, data=None, headers=None, timeout=45):
    cmd = ["curl", "-s", "-X", method, "--max-time", str(timeout), "-L"]
    if headers:
        for h in headers:
            cmd += ["-H", h]
    if data:
        cmd += ["-d", json.dumps(data), "-H", "Content-Type: application/json"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
    return r.stdout

def cf(method, path, data=None):
    return curl(method, f"{CAMFOX}{path}", data, timeout=60)

def tg(msg):
    text = msg[:4096]
    try:
        curl("POST", f"https://api.telegram.org/bot{BOT}/sendMessage",
             {"chat_id": CHAT, "text": text, "parse_mode": "HTML"}, timeout=15)
    except Exception as e:
        log(f"Telegram error: {e}")

# ── AI ─────────────────────────────────────────────────────────────────────
def ai(prompt, max_tokens=400):
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    try:
        headers = [f"Authorization: Bearer {KEY}", "Content-Type: application/json"]
        resp = curl("POST", f"{BASE}/chat/completions", data, headers=headers, timeout=30)
        d = json.loads(resp)
        if "choices" in d and d["choices"]:
            return d["choices"][0]["message"]["content"].strip()
        elif "error" in d:
            log(f"MiniMax error: {d['error'].get('message', d['error'])}")
    except Exception as e:
        log(f"MiniMax exception: {e}")
    return None

# ── Keyword Scoring ─────────────────────────────────────────────────────────
INTERESTED = ["web","backend","frontend","python","node","javascript","typescript",
    "api","rest","graphql","database","postgresql","mongodb","docker","devops",
    "cloud","aws","gcp","blockchain","smart contract","solidity","web3","nft",
    "ethereum","bitcoin","llm","ai","machine learning","fastapi","flask","django",
    "express","react","vue","kubernetes","ci/cd","linux","server","microservice",
    "data pipeline","etl","scraper","automation","script","integration",
    "web3.js","ethers.js","defi","dao","token","dapp","smart-contract"]

SKIP = ["design","logo","graphic","illustration","video","animation","photoshop",
    "illustrator","figma","ui/ux","ui design","ux design","content writing",
    "copywriting","blog post","article","data entry","excel","spreadsheet",
    "virtual assistant","seo","social media","marketing only","mobile app only",
    "ios only","android only","swift","kotlin","react native","flutter"]

def keyword_score(title, desc=""):
    text = (title + " " + desc).lower()
    for kw in SKIP:
        if kw.lower() in text:
            return 0, f"skip:{kw}"
    matches = [k for k in INTERESTED if k.lower() in text]
    if not matches:
        return 0, "no skills"
    return min(10, 4 + len(matches) * 1.5), ",".join(matches[:4])

# ── Camfox Tab Management ───────────────────────────────────────────────────
def camfox_ok():
    try:
        d = json.loads(cf("GET", "/"))
        return d.get("browserRunning") and d.get("browserConnected")
    except: return False

def new_tab(url, session=None):
    """Create new tab with unique session."""
    sid2 = session or f"{SID}_{int(time.time())}"
    resp = cf("POST", "/tabs", {"userId": sid2, "sessionKey": sid2, "url": url})
    try:
        d = json.loads(resp)
        tabId = d.get("tabId")
        if tabId:
            time.sleep(6)
        return tabId, sid2
    except:
        return None, None

def close_tab(tabId, userId=None):
    if tabId:
        cf("DELETE", f"/tabs/{tabId}?userId={userId or SID}")

def get_snapshot(tabId, userId=None, full=True):
    snap = cf("GET", f"/tabs/{tabId}/snapshot?userId={userId or SID}&full={str(full).lower()}")
    try:
        d = json.loads(snap)
        return d.get("snapshot", ""), d.get("url", "")
    except: return "", ""

def click_ref(tabId, ref, userId=None):
    r = cf("POST", f"/tabs/{tabId}/click", {"userId": userId or SID, "ref": ref})
    try: return json.loads(r).get("ok", False)
    except: return False

def type_ref(tabId, ref, text, userId=None):
    r = cf("POST", f"/tabs/{tabId}/type", {"userId": userId or SID, "ref": ref, "text": text})
    try: return json.loads(r).get("ok", False)
    except: return False

def navigate(tabId, url, userId=None):
    r = cf("POST", f"/tabs/{tabId}/navigate", {"userId": userId or SID, "url": url})
    try: return json.loads(r).get("ok", False)
    except: return False

def wait_refs(tabId, userId=None, ms=15000):
    r = cf("POST", f"/tabs/{tabId}/wait", {"userId": userId or SID, "timeout": ms})
    try: return json.loads(r).get("ready", False)
    except: return False

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
    jobs, seen = [], set()
    urls = re.findall(r"/url: (/en/tasks/[a-z0-9-]+/\d+)", snapshot)
    headings = re.findall(r'heading "([^"]+)" \[level=\d+\]:', snapshot)
    budgets = re.findall(r'\$([\d,]+(?:\.\d{2})?)', snapshot)
    for i, url in enumerate(urls):
        if url in seen: continue
        seen.add(url)
        title = headings[i] if i < len(headings) else "?"
        budget = f"${budgets[i]}" if i < len(budgets) else "?"
        jobs.append({"url": f"https://cryptotask.org{url}", "title": title, "budget": budget})
    return jobs

# ── CT Login ────────────────────────────────────────────────────────────────
def ct_login(tabId):
    """Browser-only login."""
    log("Browser login...")
    navigate(tabId, f"{CT_HOST}/en/login")
    time.sleep(7)
    
    snap, _ = get_snapshot(tabId)
    refs = extract_refs(snap)
    
    email_ref = pass_ref = submit_ref = None
    for idx, info in refs.items():
        label = info.get("label", "").lower()
        if "email" in label and info["type"] == "textbox": email_ref = f"e{idx}"
        elif "password" in label and info["type"] == "textbox": pass_ref = f"e{idx}"
        elif info["type"] == "button" and any(k in label for k in ["login", "submit", "sign in"]): submit_ref = f"e{idx}"
    
    if not email_ref or not pass_ref:
        log(f"Form not found. Refs: {list(refs.items())[:10]}")
        return False
    
    if not submit_ref: submit_ref = email_ref
    
    log(f"Login: email={email_ref} pass={pass_ref} submit={submit_ref}")
    type_ref(tabId, email_ref, CT_USER)
    time.sleep(0.5)
    type_ref(tabId, pass_ref, CT_PASS)
    time.sleep(0.5)
    click_ref(tabId, submit_ref)
    time.sleep(10)
    
    snap2, url2 = get_snapshot(tabId)
    if "/en/login" in url2:
        log("Login FAILED")
        return False
    
    log(f"Login SUCCESS: {url2}")
    return True

# ── Proposal ──────────────────────────────────────────────────────────────
def generate_proposal(title, desc, budget, client_name):
    prompt = f"""Write a 150-250 word freelance proposal for:

Job: {title}
Budget: {budget}
Client: {client_name}
Description: {desc[:800]}

Be professional, specific. RGODIM LTD: web dev, backend Python/Node, APIs, blockchain, AI integration. Output ONLY proposal."""
    
    result = ai(prompt, 350)
    if result: return result
    
    return (f"Hello{', ' + client_name if client_name else ''},\n\n"
            f"I saw your project \"{title}\" and I'm interested.\n\n"
            f"I'm a full-stack developer specializing in backend systems, APIs, blockchain, and AI applications. I can deliver quality work on time.\n\n"
            f"What are the specific requirements? Happy to discuss.\n\nBest regards,\nRGODIM LTD")

# ── Apply to Job (Browser) ──────────────────────────────────────────────────
def apply_to_job(tabId, job_url, job_title, budget):
    """Apply via browser - the primary reliable method."""
    log(f"Applying: {job_title[:50]}")
    
    navigate(tabId, job_url)
    time.sleep(8)
    
    snap, _ = get_snapshot(tabId)
    refs = extract_refs(snap)
    
    # Check login
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
        return False, "No Apply button"
    
    click_ref(tabId, apply_ref)
    time.sleep(5)
    
    snap2, _ = get_snapshot(tabId)
    refs2 = extract_refs(snap2)
    
    # Client name
    client_name = ""
    cm = re.search(r'link "([^"]+)" \[e\d+\]:\s*/url: /en/clients/', snap)
    if cm: client_name = cm.group(1)
    
    # Textarea
    textarea_ref = None
    for idx, info in refs2.items():
        if info["type"] in ("textbox", "textarea") or "letter" in info.get("label", "").lower():
            textarea_ref = f"e{idx}"
            break
    
    proposal = generate_proposal(job_title, snap[:1500], budget, client_name)
    
    if textarea_ref:
        log(f"Typing proposal ({len(proposal)} chars)...")
        type_ref(tabId, textarea_ref, proposal)
        time.sleep(2)
    
    # Submit
    submit_ref = None
    for idx, info in refs2.items():
        label = info.get("label", "").lower()
        if info["type"] == "button" and any(k in label for k in ["submit", "send", "apply", "confirm", "post"]):
            submit_ref = f"e{idx}"
            break
    
    if submit_ref:
        click_ref(tabId, submit_ref)
        time.sleep(5)
    else:
        return False, "No submit button"
    
    snap3, _ = get_snapshot(tabId)
    if any(w in snap3.lower() for w in ["applied", "success", "submitted", "thank you"]):
        return True, proposal[:100]
    return True, "Applied (confirm unclear)"

# ── Scan Pages ─────────────────────────────────────────────────────────────
def scan_pages(tabId, max_pages=8):
    """Scrape job listings from CT."""
    all_jobs = []
    seen = set()
    
    for page in range(1, max_pages + 1):
        url = f"{CT_HOST}/en/tasks" if page == 1 else f"{CT_HOST}/en/tasks?page={page}"
        log(f"Scan page {page}: {url}")
        
        navigate(tabId, url)
        time.sleep(8)
        
        snap, _ = get_snapshot(tabId)
        if not snap or len(snap) < 200:
            log(f"Page {page}: empty/failed")
            break
        
        jobs = extract_jobs(snap)
        log(f"Page {page}: {len(jobs)} jobs")
        
        for job in jobs:
            if job["url"] not in seen:
                seen.add(job["url"])
                all_jobs.append(job)
        
        if len(jobs) < 5:
            break
        
        time.sleep(3)
    
    log(f"Total unique jobs: {len(all_jobs)}")
    return all_jobs

# ── Full Browse + Apply ────────────────────────────────────────────────────
def do_browse():
    """Dedicated browse task in its own tab."""
    global last_browse
    
    log("=== Starting full browse ===")
    tg("🔍 <b>Starting job scan...</b>")
    
    tabId, sid2 = new_tab(f"{CT_HOST}/en/tasks", session=f"browse_{int(time.time())}")
    if not tabId:
        tg("❌ Cannot create tab for browsing")
        return
    
    try:
        if not ct_login(tabId):
            tg("⚠️ Login failed")
            return
        
        jobs = scan_pages(tabId, max_pages=8)
        
        if not jobs:
            tg("❌ No jobs found")
            return
        
        tg(f"📋 Found {len(jobs)} jobs. Evaluating...")
        
        applied = skipped = errors = 0
        
        for i, job in enumerate(jobs):
            title = job["title"]
            url = job["url"]
            budget = job.get("budget", "?")
            
            log(f"[{i+1}/{len(jobs)}] {title[:60]}")
            
            score, reason = keyword_score(title)
            if score == 0:
                log(f"  Skip: {reason}")
                skipped += 1
                continue
            
            # AI scoring
            ai_result = ai(f"Score 0-10 fit for RGODIM LTD (web dev, blockchain, Python, APIs, AI). Job: {title[:100]}. Reply: SCORE:X|REASON:...", 80)
            if ai_result and "SCORE:" in ai_result:
                try:
                    ai_score = int(ai_result.split("SCORE:")[1].split("|")[0].strip())
                    score = (score + ai_score) / 2
                    log(f"  Score: {score:.0f}/10 | {ai_result.split('REASON:')[1].strip()[:60] if 'REASON:' in ai_result else ''}")
                except: pass
            
            if score < 4:
                log(f"  Low score: {score}")
                skipped += 1
                continue
            
            # Apply in a fresh tab to avoid state issues
            apply_tab, asid = new_tab(url, session=f"apply_{int(time.time())}")
            if not apply_tab:
                errors += 1
                continue
            
            try:
                success, msg = apply_to_job(apply_tab, url, title, budget)
                
                if success:
                    applied += 1
                    tg(f"✅ <b>{title}</b>\nBudget: {budget}\nScore: {score:.0f}/10\n\n{message(msg)}")
                    save_applied(job, score)
                else:
                    errors += 1
                    tg(f"❌ {title}\n{msg}")
                
                time.sleep(5)
            finally:
                close_tab(apply_tab, asid)
        
        tg(f"📊 <b>Done!</b>\nFound: {len(jobs)}\n✅ Applied: {applied}\n⏭️ Skipped: {skipped}\n❌ Errors: {errors}")
        log(f"Browse complete: {applied} applied, {skipped} skipped, {errors} errors")
        last_browse = time.time()
        
    finally:
        close_tab(tabId, sid2)

def message(msg):
    if not msg: return ""
    return msg[:200] + "..." if len(msg) > 200 else msg

def save_applied(job, score):
    try:
        entry = {"time": datetime.now().isoformat(), "title": job["title"], "url": job["url"], "score": round(score, 1)}
        with open(APPLIED_F, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except: pass

# ── Telegram Command Handlers ───────────────────────────────────────────────
def cmd_status():
    camfox_ok_val = camfox_ok()
    try:
        with open(LOG_F) as f:
            last = "".join(f.readlines()[-5:])
    except: last = ""
    tg(f"🤖 RGODIM LTD Agent\nCamfox: {'✅' if camfox_ok_val else '❌'}\nTime: {datetime.now():%H:%M}\n\n{last[:500]}")

def cmd_browse():
    global browsing
    with browse_lock:
        if browsing:
            tg("⏳ Browse already in progress...")
            return
        browsing = True
        tg("🚀 Scanning jobs now...")
    Thread(target=_browse_thread, daemon=True).start()

def _browse_thread():
    global browsing
    try:
        do_browse()
    finally:
        with browse_lock:
            browsing = False

def cmd_apply(args):
    if not args:
        tg("Usage: /apply <job_url>")
        return
    
    tg(f"🎯 Applying to:\n{args}")
    
    def do_apply():
        tabId, sid2 = new_tab(args, session=f"cmd_apply_{int(time.time())}")
        if not tabId:
            tg("❌ Cannot create tab")
            return
        try:
            if not ct_login(tabId):
                tg("❌ Login failed")
                return
            time.sleep(8)
            snap, _ = get_snapshot(tabId)
            title_m = re.search(r'heading "([^"]+)" \[level=1\]:', snap)
            title = title_m.group(1) if title_m else "?"
            budget_m = re.search(r'\$[\d,]+(?:\.\d{2})?', snap)
            budget = budget_m.group() if budget_m else "?"
            
            success, msg = apply_to_job(tabId, args, title, budget)
            if success:
                tg(f"✅ <b>Applied:</b>\n{title}\nBudget: {budget}\n{message(msg)}")
                save_applied({"title": title, "url": args}, 8)
            else:
                tg(f"❌ Failed:\n{title}\n{msg}")
        finally:
            close_tab(tabId, sid2)
    
    Thread(target=do_apply, daemon=True).start()

def cmd_applied():
    try:
        with open(APPLIED_F) as f:
            lines = f.readlines()[-10:]
        if lines:
            msg = "📝 Recent Applications:\n\n"
            for l in lines:
                j = json.loads(l)
                msg += f"• {j['title']}\n  Score: {j.get('score','?')}/10\n  {j['url']}\n\n"
            tg(msg[:4096])
        else:
            tg("No applications yet.")
    except: tg("No applications file.")

def cmd_portfolio():
    if os.path.exists(PORTFOLIO):
        with open(PORTFOLIO) as f:
            tg("📁 RGODIM LTD Portfolio\n\n" + f.read()[:4000])
    else:
        tg("Portfolio not found.")

def cmd_help():
    tg("Commands:\n/status - Agent status\n/browse - Scan & apply\n/apply <url> - Apply to job\n/applied - Recent apps\n/portfolio - View portfolio\n/help")

def handle_telegram():
    """Poll Telegram - runs in dedicated tab."""
    global tab_id, tab_lock, shutdown
    
    try:
        # Use a dedicated tab for Telegram polling
        with tab_lock:
            if tab_id is None:
                tab_id, _ = new_tab(f"{CT_HOST}/en", session="telegram_poll")
                if tab_id:
                    log(f"Telegram tab created: {tab_id[:20]}")
        
        if tab_id is None:
            return
        
        r = curl("GET", f"https://api.telegram.org/bot{BOT}/getUpdates?timeout=1&offset=-1", timeout=5)
        d = json.loads(r)
        if d.get("ok") and d.get("result"):
            for item in d["result"]:
                msg = item.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                if text and chat_id == int(CHAT) and text.startswith("/"):
                    parts = text[1:].split(" ", 1)
                    cmd_name = parts[0].lower()
                    args = parts[1] if len(parts) > 1 else ""
                    log(f"Telegram: /{cmd_name} {args}")
                    
                    if cmd_name == "status":  cmd_status()
                    elif cmd_name == "browse": cmd_browse()
                    elif cmd_name == "apply": cmd_apply(args)
                    elif cmd_name == "applied": cmd_applied()
                    elif cmd_name == "portfolio": cmd_portfolio()
                    elif cmd_name == "help": cmd_help()
                    else:
                        tg(f"Unknown: /{cmd_name}\nTry /help")
    except Exception as e:
        log(f"Telegram poll error: {e}")

# ── Watchdog Loop ───────────────────────────────────────────────────────────
def watchdog():
    global last_browse, shutdown
    
    log("Watchdog starting...")
    tg("🤖 RGODIM LTD Agent online")
    
    # Initial browse
    time.sleep(5)
    do_browse()
    
    while not shutdown:
        try:
            handle_telegram()
            
            # Periodic browse every 4 hours
            now = time.time()
            if now - last_browse > browse_interval:
                with browse_lock:
                    if browsing:
                        log("Browse already running, skipping periodic")
                    else:
                        browsing = True
                        log("Periodic browse...")
                        tg("🔄 Auto job scan (4h interval)")
                        Thread(target=_browse_thread, daemon=True).start()
                        last_browse = now
            
            time.sleep(30)
        except KeyboardInterrupt:
            log("Watchdog stopped")
            break
        except Exception as e:
            log(f"Watchdog error: {e}")
            time.sleep(60)

def signal_handler(sig, frame):
    global shutdown
    log("Shutdown signal received")
    shutdown = True

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "watchdog"
    
    if cmd == "watchdog":
        watchdog()
    elif cmd == "browse":
        do_browse()
    elif cmd == "status":
        cmd_status()
    elif cmd == "telegram-poll":
        handle_telegram()
    else:
        print(f"Commands: status, browse, watchdog, telegram-poll")

if __name__ == "__main__":
    main()
