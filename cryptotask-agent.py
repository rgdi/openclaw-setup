#!/usr/bin/env python3
"""
RGODIM LTD CryptoTask Agent v6
- Answers client questions naturally (no portfolio spam)
- Tracks: jobs browsed, applied, responded, approved, prices quoted
- Affordable pricing: $15-50 range
- Client memory with conversation history
- Keyword scoring + AI when available
- Safeguards: professional, no BS, no incompetence shown
"""
import subprocess, json, time, re, sys, os, signal, random
from datetime import datetime, timedelta
from threading import Thread, Lock
from collections import defaultdict

# ── Config ──────────────────────────────────────────────────────────────────
BOT      = "8612653411:AAE_KvNbuxIBeBP_uocTWaN3xlOBpqiva3k"
CHAT     = "6793940199"
KEY      = "sk-cp-8r2sLAzHvPzkwS7Z1yjPZWmZpBdP8YvWnQv2iHk6vBmKl4x7Y8eRmJc9nAoXdc"
BASE     = "https://api.minimaxi.com/v1"
MODEL    = "MiniMax-M2.7"
CAMFOX   = "http://127.0.0.1:9377"
CT_HOST  = "https://cryptotask.org"
CT_USER  = "rom.godinho@gmail.com"
CT_PASS  = "6yVb7HJX7pTfQ9V"

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO = os.path.join(BASE_DIR, "PORTFOLIO.md")
CLIENT_F  = os.path.join(BASE_DIR, "client_profiles.md")
STATS_F   = os.path.join(BASE_DIR, "stats.json")
APPLIED_F = os.path.join(BASE_DIR, "applied_jobs.json")
LOG_F     = os.path.join(BASE_DIR, "agent.log")
SID       = "rgodim_agent"

# ── Globals ──────────────────────────────────────────────────────────────────
tab_id       = None
tab_lock     = Lock()
browse_lock  = Lock()
browsing     = False
last_browse  = 0
browse_interval = 4 * 3600
shutdown     = False
stats        = {"started": datetime.now().isoformat(), "jobs_browsed": 0, "applied": 0,
                "responded": 0, "approved": 0, "rejected": 0, "questions_answered": 0,
                "total_earned": 0.0, "prices_quoted": [], "last_activity": None}

# ── Pricing (affordable) ─────────────────────────────────────────────────────
PRICING = {
    "small":   {"range": "$15-25",  "desc": "Small task", "examples": "Bug fix, small API, script, config"},
    "medium":  {"range": "$25-75",  "desc": "Medium project", "examples": "Landing page, REST API, chatbot, scraper"},
    "large":   {"range": "$75-150", "desc": "Full project", "examples": "Web app, backend system, blockchain integration"},
    "enterprise": {"range": "$150-300", "desc": "Complex system", "examples": "Distributed system, AI integration, platform"},
}

def get_price_range(budget_text):
    """Parse budget and suggest affordable price."""
    try:
        nums = re.findall(r'\$?([\d,]+)', budget_text)
        if not nums: return PRICING["medium"]["range"]
        max_budget = max(int(n.replace(',','')) for n in nums)
        if max_budget <= 50: return PRICING["small"]["range"]
        elif max_budget <= 200: return PRICING["medium"]["range"]
        elif max_budget <= 500: return PRICING["large"]["range"]
        else: return PRICING["enterprise"]["range"]
    except: return PRICING["medium"]["range"]

# ── Helpers ──────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_F, "a") as f: f.write(line + "\n")
    except: pass

def curl(method, url, data=None, headers=None, timeout=45):
    cmd = ["curl", "-s", "-X", method, "--max-time", str(timeout), "-L"]
    if headers:
        for h in headers: cmd += ["-H", h]
    if data:
        cmd += ["-d", json.dumps(data), "-H", "Content-Type: application/json"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
    return r.stdout

def cf(method, path, data=None):
    return curl(method, f"{CAMFOX}{path}", data, timeout=60)

def tg(msg):
    text = str(msg)[:4096]
    try:
        curl("POST", f"https://api.telegram.org/bot{BOT}/sendMessage",
             {"chat_id": CHAT, "text": text, "parse_mode": "HTML"}, timeout=15)
    except Exception as e:
        log(f"Telegram error: {e}")

# ── Stats ────────────────────────────────────────────────────────────────────
def load_stats():
    global stats
    try:
        if os.path.exists(STATS_F):
            with open(STATS_F) as f:
                saved = json.loads(f.read())
                stats.update(saved)
    except: pass

def save_stats():
    try:
        with open(STATS_F, "w") as f:
            json.dump(stats, f, indent=2)
    except: pass

def inc_stat(key, val=1):
    global stats
    stats[key] = stats.get(key, 0) + val
    stats["last_activity"] = datetime.now().isoformat()
    save_stats()

# ── AI ─────────────────────────────────────────────────────────────────────
def ai(prompt, max_tokens=300):
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    headers = [f"Authorization: Bearer {KEY}", "Content-Type: application/json"]
    try:
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
    "web3.js","ethers.js","defi","dao","token","dapp","smart-contract","web3"]

SKIP = ["design","logo","graphic","illustration","video","animation","photoshop",
    "illustrator","figma","ui/ux","ui design","ux design","content writing",
    "copywriting","blog post","article","data entry","excel","spreadsheet",
    "virtual assistant","seo","social media","marketing only","mobile app only",
    "ios only","android only","swift","kotlin","react native","flutter",
    "artist","nft art","image training","image generation","illustration",
    "voice over","video edit","music production","podcast","audio",
    "3d model","3d design","blender","maya","zbrush","texturing","rigging",
    "unreal","unity","game dev","gameplay","level design","npc","character artist",
    "aircraft","mechanic","maintenance","repair technician","car","auto",
    "cannabis","marijuana","adult","nsfw","crypto trading advice","trading signal",
    "trading bot","signal provider","trading strategy only","webull","binance signal",
    "copy trade","trading competition","marketing manager","social media manager",
    "content creator","youtube","tiktok","instagram influencer","facebook ad",
    "logo design","brand design","flyer","poster","banner design","mockup"]

def keyword_score(title, desc=""):
    text = (title + " " + desc).lower()
    for kw in SKIP:
        if kw.lower() in text: return 0, f"skip:{kw}"
    matches = [k for k in INTERESTED if k.lower() in text]
    if not matches: return 0, "no skills"
    return min(10, 4 + len(matches) * 1.5), ",".join(matches[:4])

# ── Client Memory ───────────────────────────────────────────────────────────
def load_clients():
    clients = {}
    try:
        if os.path.exists(CLIENT_F):
            with open(CLIENT_F) as f:
                content = f.read()
                # Parse markdown sections
                sections = re.split(r'\n(?=## )', content)
                for sec in sections[1:]:
                    lines = sec.strip().split('\n')
                    if len(lines) >= 2:
                        name = lines[0].replace('## ', '').strip()
                        clients[name] = {'name': name, 'notes': '\n'.join(lines[1:])}
    except: pass
    return clients

def save_clients(clients):
    try:
        with open(CLIENT_F, "w") as f:
            f.write("# Client Profiles\n\n")
            for name, data in clients.items():
                f.write(f"## {name}\n{data.get('notes','')}\n\n")
    except: pass

def update_client(client_name, note):
    clients = load_clients()
    if client_name not in clients:
        clients[client_name] = {'name': client_name, 'notes': ''}
    clients[client_name]['notes'] += f"\n- [{datetime.now().strftime('%Y-%m-%d')}] {note}"
    save_clients(clients)

# ── Proposal Generation ──────────────────────────────────────────────────────
def generate_proposal(title, desc, budget, client_name, price_range):
    """Generate affordable, professional proposal."""
    inc_stat("prices_quoted", price_range)
    
    prompt = f"""Write a 150-200 word freelance proposal. Be specific, professional, and show you understand the project. RGODIM LTD specializes in: backend Python/Node.js, REST/GraphQL APIs, blockchain (Solidity/Web3), AI integration, Docker/Kubernetes, data pipelines.

Job: {title}
Budget: {budget}
Client: {client_name}
Our price range: {price_range}

Write ONLY the proposal text. Keep it concise and confident. No fluff."""

    result = ai(prompt, 300)
    if result: return result
    
    return (f"Hello{', ' + client_name if client_name else ''},\n\n"
            f"I can deliver this project for {price_range}. I specialize in backend systems, "
            f"APIs, blockchain, and AI integration.\n\n"
            f"Let me know your timeline and specific requirements.\n\n"
            f"Best regards,\nRGODIM LTD")

# ── Camfox Tab Management ───────────────────────────────────────────────────
def camfox_ok():
    try:
        d = json.loads(cf("GET", "/"))
        return d.get("browserRunning") and d.get("browserConnected")
    except: return False

def new_tab(url, session=None):
    sid2 = session or f"{SID}_{int(time.time())}"
    resp = cf("POST", "/tabs", {"userId": sid2, "sessionKey": sid2, "url": url})
    try:
        d = json.loads(resp)
        tabId = d.get("tabId")
        if tabId: time.sleep(5)
        return tabId, sid2
    except: return None, None

def close_tab(tabId, userId=None):
    if tabId: cf("DELETE", f"/tabs/{tabId}?userId={userId or SID}")

def get_snapshot(tabId, userId=None, full=True):
    snap = cf("GET", f"/tabs/{tabId}/snapshot?userId={userId or SID}&full={str(full).lower()}")
    try:
        d = json.loads(snap)
        return d.get("snapshot", ""), d.get("url", "")
    except: return "", ""

def click_ref(tabId, ref, userId=None):
    try:
        r = cf("POST", f"/tabs/{tabId}/click", {"userId": userId or SID, "ref": ref})
        return json.loads(r).get("ok", False)
    except: return False

def type_ref(tabId, ref, text, userId=None):
    try:
        r = cf("POST", f"/tabs/{tabId}/type", {"userId": userId or SID, "ref": ref, "text": text})
        return json.loads(r).get("ok", False)
    except: return False

def navigate(tabId, url, userId=None):
    try:
        r = cf("POST", f"/tabs/{tabId}/navigate", {"userId": userId or SID, "url": url})
        return json.loads(r).get("ok", False)
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

# ── Apply to Job ────────────────────────────────────────────────────────────
def apply_to_job(tabId, job_url, job_title, budget):
    log(f"Applying: {job_title[:50]}")
    navigate(tabId, job_url)
    time.sleep(8)
    
    snap, _ = get_snapshot(tabId)
    refs = extract_refs(snap)
    
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
    
    # Price range
    price_range = get_price_range(budget)
    
    # Textarea
    textarea_ref = None
    for idx, info in refs2.items():
        if info["type"] in ("textbox", "textarea") or "letter" in info.get("label", "").lower():
            textarea_ref = f"e{idx}"
            break
    
    proposal = generate_proposal(job_title, snap[:1500], budget, client_name, price_range)
    
    if textarea_ref:
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
        inc_stat("applied")
        return True, f"Applied ✓ ({price_range})"
    return True, f"Applied ✓ ({price_range}) - confirm unclear"

# ── Scan Pages ─────────────────────────────────────────────────────────────
def scan_pages(tabId, max_pages=8):
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
        inc_stat("jobs_browsed", len(jobs))
        
        for job in jobs:
            if job["url"] not in seen:
                seen.add(job["url"])
                all_jobs.append(job)
        
        if len(jobs) < 5: break
        time.sleep(3)
    
    log(f"Total unique jobs: {len(all_jobs)}")
    return all_jobs

# ── Full Browse + Apply ────────────────────────────────────────────────────
def do_browse():
    global last_browse
    
    log("=== Starting full browse ===")
    tg("🔍 <b>Scanning CryptoTask jobs...</b>")
    
    tabId, sid2 = new_tab(f"{CT_HOST}/en/tasks", session=f"browse_{int(time.time())}")
    if not tabId:
        tg("❌ Cannot create browser tab")
        return
    
    try:
        if not ct_login(tabId):
            tg("⚠️ Login failed")
            return
        
        jobs = scan_pages(tabId, max_pages=8)
        
        if not jobs:
            tg("❌ No jobs found")
            return
        
        tg(f"📋 Found <b>{len(jobs)}</b> jobs. Evaluating...")
        
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

            # Only apply to strong matches (score >= 5.5)
            if score < 5.5:
                log(f"  Low score ({score:.1f}), skipping")
                skipped += 1
                continue

            # Apply in fresh tab
            apply_tab, asid = new_tab(url, session=f"apply_{int(time.time())}")
            if not apply_tab:
                errors += 1
                continue
            
            try:
                success, msg = apply_to_job(apply_tab, url, title, budget)
                
                if success:
                    applied += 1
                    tg(f"✅ <b>{title[:60]}</b>\nBudget: {budget}\n{message(msg)}")
                    save_applied(job, score)
                else:
                    errors += 1
                    tg(f"❌ <b>{title[:60]}</b>\n{msg}")
                
                time.sleep(5)
            finally:
                close_tab(apply_tab, asid)
        
        # Final stats
        tg(f"📊 <b>Scan Complete!</b>\n\nScanned: {len(jobs)}\n✅ Applied: {applied}\n⏭️ Skipped: {skipped}\nErrors: {errors}")
        log(f"Browse complete: {applied} applied, {skipped} skipped, {errors} errors")
        last_browse = time.time()
        
    finally:
        close_tab(tabId, sid2)

def message(msg):
    if not msg: return ""
    return msg[:200] + "..." if len(msg) > 200 else msg

def save_applied(job, score):
    try:
        entry = {"time": datetime.now().isoformat(), "title": job["title"],
                 "url": job["url"], "score": round(score, 1)}
        with open(APPLIED_F, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except: pass

# ── Telegram Command Handlers ───────────────────────────────────────────────
def cmd_status():
    load_stats()
    camfox_ok_val = camfox_ok()
    price = PRICING["medium"]["range"]
    
    uptime = "unknown"
    try:
        started = datetime.fromisoformat(stats["started"])
        delta = datetime.now() - started
        hours = int(delta.total_seconds() / 3600)
        uptime = f"{hours}h"
    except: pass
    
    tg((f"🤖 <b>RGODIM LTD Agent</b>\n\n"
        f"Status: {'✅ Online' if camfox_ok_val else '❌ Camfox down'}\n"
        f"Uptime: {uptime}\n\n"
        f"📊 <b>Statistics:</b>\n"
        f"Jobs browsed: {stats.get('jobs_browsed', 0)}\n"
        f"Applications sent: {stats.get('applied', 0)}\n"
        f"Questions answered: {stats.get('questions_answered', 0)}\n"
        f"Prices quoted: {stats.get('prices_quoted', 0)}\n\n"
        f"💰 Pricing (affordable):\n"
        f"• Small tasks: {PRICING['small']['range']}\n"
        f"• Medium projects: {PRICING['medium']['range']}\n"
        f"• Full projects: {PRICING['large']['range']}\n\n"
        f"/browse /help"))

def cmd_browse():
    global browsing
    with browse_lock:
        if browsing:
            tg("⏳ Already scanning... please wait")
            return
        browsing = True
        tg("🚀 <b>Starting job scan!</b>\nI'll notify you when done.")
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
        tg("Usage: /apply <job_url>\nExample: /apply https://cryptotask.org/en/tasks/project/123")
        return
    
    tg(f"🎯 <b>Applying to:</b>\n{args[:200]}")
    
    def do():
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
                tg(f"✅ <b>Applied!</b>\n{title}\nBudget: {budget}\n{message(msg)}")
                save_applied({"title": title, "url": args}, 8)
            else:
                tg(f"❌ Failed\n{title}\n{msg}")
        finally:
            close_tab(tabId, sid2)
    
    Thread(target=do, daemon=True).start()

def cmd_applied():
    try:
        with open(APPLIED_F) as f:
            lines = f.readlines()[-10:]
        if lines:
            msg = "📝 <b>Recent Applications:</b>\n\n"
            for l in lines:
                j = json.loads(l)
                score = j.get('score', '?')
                title = j['title'][:50]
                msg += f"• <b>{title}</b>\n  Score: {score}/10\n  {j['url'][:80]}\n\n"
            tg(msg[:4096])
        else:
            tg("No applications yet. Use /browse to start!")
    except Exception as e:
        tg("No applications yet.")

def cmd_pricing():
    tg(("💰 <b>RGODIM LTD — Affordable Pricing</b>\n\n"
        f"🟢 <b>Small tasks ({PRICING['small']['range']})</b>\n"
        f"{PRICING['small']['examples']}\n\n"
        f"🟡 <b>Medium projects ({PRICING['medium']['range']})</b>\n"
        f"{PRICING['medium']['examples']}\n\n"
        f"🟠 <b>Full projects ({PRICING['large']['range']})</b>\n"
        f"{PRICING['large']['examples']}\n\n"
        f"🔴 <b>Complex systems ({PRICING['enterprise']['range']})</b>\n"
        f"{PRICING['enterprise']['examples']}\n\n"
        f"<i>Prices are negotiable based on project scope.</i>"))

def cmd_help():
    tg(("📋 <b>Commands:</b>\n\n"
        "/status — Agent dashboard\n"
        "/browse — Scan & apply to jobs\n"
        "/apply <url> — Apply to specific job\n"
        "/applied — View applications\n"
        "/pricing — View affordable pricing\n"
        "/portfolio — View our work\n"
        "/help — This message\n\n"
        "<i>Ask me anything about our services!</i>"))

def cmd_portfolio():
    """Only show portfolio when explicitly requested."""
    if os.path.exists(PORTFOLIO):
        with open(PORTFOLIO) as f:
            tg("📁 <b>RGODIM LTD Portfolio</b>\n\n" + f.read()[:4000])
    else:
        tg("Portfolio coming soon! In the meantime, /browse to see me in action.")

# ── Generic Question Handler ─────────────────────────────────────────────────
GREETINGS = ["hello", "hi", "hey", "ola", "oi", "bom dia", "good morning", "good afternoon", "good evening"]
THANKS = ["thanks", "thank you", "obrigado", "merci", "gracias"]
GOODBYE = ["bye", "goodbye", "see you", "ate logo", "tchau"]

SERVICES = {
    "web dev": "We build fast, secure web apps — frontend + backend. React/Vue/Django/FastAPI/Node.js. Prices from $15!",
    "api": "REST/GraphQL API development. Python FastAPI, Node Express, database integration. Starting at $25.",
    "backend": "Backend systems, microservices, databases (PostgreSQL/MongoDB), Docker/K8s deployment. From $25.",
    "blockchain": "Smart contracts (Solidity), Web3 integration, DeFi, NFTs, token development. Ethereum/Solidity specialist.",
    "scraper": "Web scraping and data extraction — Python, Selenium, BeautifulSoup. Fast and reliable.",
    "automation": "Task automation, scripts, CI/CD pipelines. Python/Bash. Save time and money.",
    "ai": "AI integration — LLM APIs, chatbots, automation. Python with OpenAI/Anthropic/MiniMax.",
    "chatbot": "AI-powered chatbots for websites and platforms. Conversational, smart, affordable.",
    "bot": "Telegram bots, Discord bots, automation bots. Fast and cheap.",
    "database": "Database design, optimization, migration. PostgreSQL, MongoDB, MySQL. From $15.",
    "docker": "Docker containers, Kubernetes clusters, DevOps. Fast deployment.",
    "blockchain developer": "Solidity, Web3.js, Ethers.js, DeFi protocols, smart contracts. Expert level.",
    "smart contract": "Solidity smart contracts, audits, deployment. Ethereum ecosystem specialist.",
    "python": "Python development — FastAPI, Flask, Django, data pipelines, automation. From $15.",
    "javascript": "JavaScript/TypeScript — Node.js, React, Vue, Next.js. Modern frontend and backend.",
    "node": "Node.js backend — Express, APIs, real-time apps, microservices.",
    "frontend": "React, Vue, Next.js, modern frontend. Fast, responsive, beautiful.",
    "full stack": "Full-stack development — frontend + backend + database. End-to-end solutions.",
    "website": "Professional websites and web apps. Modern tech, fast, affordable. From $25.",
    "web app": "Custom web applications. React/Vue frontend, Python/Node backend. Scalable and secure.",
}

REPLIES = {
    "available": "Yes, I'm available! I specialize in backend, APIs, blockchain, and automation. What do you need?",
    "experience": "RGODIM LTD has experience with Python, Node.js, React, blockchain, AI, databases, and DevOps. Check /portfolio or just tell me your project!",
    "price": "Our prices are affordable! From $15 for small tasks. Type /pricing for full breakdown.",
    "timeline": "Timelines depend on project size. Small tasks: 1-3 days. Medium: 3-7 days. Large: 1-4 weeks. Let's discuss!",
    "contact": "You can reach me here on CryptoTask! Or describe your project and I'll give you a quote.",
    "who": "I'm the RGODIM LTD agent — here to help with your projects!",
    "what": "I can help with: web dev, APIs, blockchain, AI, automation, bots, data pipelines, and more. What are you building?",
    "where": "I'm working remotely and can collaborate across timezones. What project do you have?",
    "when": "I'm available now! Tell me about your project and I'll get started.",
    "how": "Just describe your project here or on CryptoTask. I'll provide a quote and timeline. /pricing for reference.",
    "why": "I want to help you build something great! Affordable, professional, and I treat every project seriously.",
}

def handle_question(text):
    """Handle generic questions without spamming portfolio."""
    text_lower = text.lower()
    
    inc_stat("questions_answered")
    
    # Greetings
    for g in GREETINGS:
        if g in text_lower:
            replies = ["Hello! 👋 How can I help you today?", "Hi there! What are you working on?", "Hey! I'm here to help with your projects."]
            return random.choice(replies)
    
    # Thanks
    for t in THANKS:
        if t in text_lower:
            return "You're welcome! 😊 Let me know if you need anything else."
    
    # Goodbye
    for g in GOODBYE:
        if g in text_lower:
            return "Goodbye! Feel free to reach out anytime. Good luck with your project! 👍"
    
    # Service-specific
    for svc, reply in SERVICES.items():
        if svc in text_lower:
            return f"💼 {reply}"
    
    # Keyword-based replies
    for kw, reply in REPLIES.items():
        if kw in text_lower:
            return f"💡 {reply}"
    
    return None  # Don't know

def handle_telegram():
    """Poll Telegram for commands and questions."""
    global tab_id, tab_lock, shutdown
    
    try:
        with tab_lock:
            if tab_id is None:
                tab_id, _ = new_tab(f"{CT_HOST}/en", session="telegram_poll")
        
        if tab_id is None: return
        
        r = curl("GET", f"https://api.telegram.org/bot{BOT}/getUpdates?timeout=1&offset=-1", timeout=5)
        d = json.loads(r)
        if d.get("ok") and d.get("result"):
            for item in d["result"]:
                msg = item.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                
                if text and chat_id == int(CHAT):
                    log(f"Telegram: {text[:100]}")
                    
                    if text.startswith("/"):
                        parts = text[1:].split(" ", 1)
                        cmd_name = parts[0].lower()
                        args = parts[1] if len(parts) > 1 else ""
                        
                        if cmd_name == "status":   cmd_status()
                        elif cmd_name == "browse":  cmd_browse()
                        elif cmd_name == "apply":   cmd_apply(args)
                        elif cmd_name == "applied": cmd_applied()
                        elif cmd_name == "portfolio": cmd_portfolio()
                        elif cmd_name == "pricing": cmd_pricing()
                        elif cmd_name == "help":    cmd_help()
                        else:
                            tg(f"Unknown command. Type /help for available commands.")
                    
                    else:
                        # Generic question - don't show incompetence
                        reply = handle_question(text)
                        if reply:
                            tg(reply)
                        elif len(text) > 3:
                            # Smart fallback - show availability without admitting ignorance
                            tg("I'm here to help! For a quick quote, tell me your project details or type /pricing. To see available jobs, type /browse.")
    
    except Exception as e:
        log(f"Telegram poll error: {e}")

# ── Watchdog ───────────────────────────────────────────────────────────────
def watchdog():
    global last_browse, shutdown, stats
    
    log("Watchdog starting...")
    load_stats()
    tg("🤖 <b>RGODIM LTD Agent</b> — Online!\n\nType /help for commands. I'm here for your projects! 💼")
    
    # Initial browse
    time.sleep(5)
    
    # Only do initial browse if we haven't browsed recently
    if time.time() - last_browse > 3600:  # If > 1 hour since last browse
        tg("🔄 <b>Starting initial job scan...</b>")
        try:
            do_browse()
        except Exception as e:
            log(f"Initial browse error: {e}")
    
    while not shutdown:
        try:
            handle_telegram()
            
            now = time.time()
            if now - last_browse > browse_interval:
                with browse_lock:
                    if not browsing:
                        browsing = True
                        log("Periodic browse...")
                        tg("🔄 <b>Auto job scan (4h)</b>")
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
    log("Shutdown signal")
    shutdown = True

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "watchdog"
    
    if cmd == "watchdog":  watchdog()
    elif cmd == "browse":  do_browse()
    elif cmd == "status":  cmd_status()
    elif cmd == "telegram-poll": handle_telegram()
    else: print("Commands: status, browse, watchdog, telegram-poll")

if __name__ == "__main__":
    main()
