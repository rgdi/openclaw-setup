#!/usr/bin/env python3
"""
RGODIM LTD CryptoTask Agent v6c — Lean Version
- MAX 2 concurrent browser tabs (1 browse, 1 apply)
- Reuses tabs instead of creating new ones
- Stricter memory management
- Only 3 pages per scan (not 8)
- Affordable pricing + stats + question handler
"""
import subprocess, json, time, re, sys, os, signal, random
from datetime import datetime
from threading import Thread, Lock

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
browse_tab   = None  # Single shared browse tab
apply_tab    = None  # Single shared apply tab
browse_lock  = Lock()
apply_lock   = Lock()
browsing     = False
applying     = False
last_browse  = 0
browse_interval = 4 * 3600
shutdown      = False

stats = {"started": datetime.now().isoformat(), "jobs_browsed": 0, "applied": 0,
         "questions_answered": 0, "prices_quoted": 0, "last_activity": None}

PRICING = {
    "small": {"range": "$15-25", "desc": "Small task", "examples": "Bug fix, script, config"},
    "medium": {"range": "$25-75", "desc": "Medium project", "examples": "REST API, scraper, chatbot"},
    "large": {"range": "$75-150", "desc": "Full project", "examples": "Web app, backend, blockchain"},
}

def get_price_range(budget_text):
    try:
        nums = re.findall(r'\$?([\d,]+)', budget_text)
        if not nums: return PRICING["medium"]["range"]
        max_budget = max(int(n.replace(',','')) for n in nums)
        if max_budget <= 50: return PRICING["small"]["range"]
        elif max_budget <= 200: return PRICING["medium"]["range"]
        else: return PRICING["large"]["range"]
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
    data = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": 0.7}
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
    "web3.js","ethers.js","defi","dao","token","dapp","smart-contract","web3",
    "full stack","full-stack","fullstack","backend developer","frontend developer",
    "web developer","software engineer","devops engineer","site reliability"]

SKIP = ["design","logo","graphic","illustration","video","animation","photoshop",
    "illustrator","figma","ui/ux","ui design","ux design","content writing",
    "copywriting","blog post","article","data entry","excel","spreadsheet",
    "virtual assistant","seo","social media","marketing only","mobile app only",
    "ios only","android only","swift","kotlin","react native","flutter",
    "artist","nft art","image training","image generation","voice over",
    "video edit","music production","podcast","audio","3d model","3d design",
    "blender","maya","zbrush","unreal","unity","game dev","gameplay","character artist",
    "aircraft","mechanic","maintenance","repair","car","auto mechanic",
    "cannabis","marijuana","adult","nsfw","crypto trading advice","trading signal",
    "trading bot","signal provider","webull","binance signal","copy trade",
    "trading competition","marketing manager","social media manager",
    "content creator","youtube","tiktok","instagram","facebook ad","brand design",
    "logo design","flyer","poster","banner","mockup","t-shirt","merch",
    "podcast edit","voice actor","musician","singer","songwriter","dj",
    "real estate","property","house","apartment","carpenter","plumber","electrician",
    "legal","lawyer","attorney","court","law firm","contract law",
    "academic","essay","thesis","dissertation","research paper","university",
    "translate","translation","interpret","localization","proofread","editing"]

def keyword_score(title, desc=""):
    text = (title + " " + desc).lower()
    for kw in SKIP:
        if kw.lower() in text: return 0, f"skip:{kw}"
    matches = [k for k in INTERESTED if k.lower() in text]
    if not matches: return 0, "no skills"
    return min(10, 4 + len(matches) * 1.5), ",".join(matches[:4])

# ── Proposal ────────────────────────────────────────────────────────────────
def generate_proposal(title, budget, client_name, price_range):
    prompt = f"""Write 150-200 word freelance proposal. RGODIM LTD: backend Python/Node.js, REST/GraphQL APIs, blockchain (Solidity/Web3), AI integration, Docker/K8s.

Job: {title}
Budget: {budget}
Client: {client_name}
Our price: {price_range}

ONLY proposal text. Specific, professional. No fluff."""

    result = ai(prompt, 300)
    if result: return result

    return (f"Hello{', ' + client_name if client_name else ''},\n\n"
            f"I can deliver for {price_range}. I specialize in backend, APIs, blockchain, and AI.\n\n"
            f"Tell me your timeline and requirements.\n\nBest regards,\nRGODIM LTD")

# ── Camfox Helpers (minimal tabs) ──────────────────────────────────────────
def camfox_ok():
    try:
        d = json.loads(cf("GET", "/"))
        return d.get("browserRunning") and d.get("browserConnected")
    except: return False

def get_shared_tab(tab_type):
    """Get or create a single shared tab for browse or apply."""
    global browse_tab, apply_tab

    if tab_type == "browse":
        if browse_tab:
            # Test if tab is still alive
            try:
                snap = cf("GET", f"/tabs/{browse_tab}/snapshot?userId={SID}&full=false")
                d = json.loads(snap)
                if d.get("snapshot"):
                    return browse_tab
            except: pass
        # Create new browse tab
        try:
            resp = cf("POST", "/tabs", {"userId": SID, "sessionKey": f"browse_{SID}", "url": f"{CT_HOST}/en"})
            d = json.loads(resp)
            browse_tab = d.get("tabId")
            if browse_tab:
                time.sleep(5)
                return browse_tab
        except: pass
        return None

    elif tab_type == "apply":
        if apply_tab:
            try:
                snap = cf("GET", f"/tabs/{apply_tab}/snapshot?userId={SID}&full=false")
                d = json.loads(snap)
                if d.get("snapshot"):
                    return apply_tab
            except: pass
        try:
            resp = cf("POST", "/tabs", {"userId": SID, "sessionKey": f"apply_{SID}", "url": f"{CT_HOST}/en"})
            d = json.loads(resp)
            apply_tab = d.get("tabId")
            if apply_tab:
                time.sleep(5)
                return apply_tab
        except: pass
        return None

def close_shared_tab(tab_type):
    global browse_tab, apply_tab
    tab = browse_tab if tab_type == "browse" else apply_tab
    if tab:
        try:
            cf("DELETE", f"/tabs/{tab}?userId={SID}")
        except: pass
    if tab_type == "browse": browse_tab = None
    else: apply_tab = None

def get_snapshot(tabId, full=True):
    snap = cf("GET", f"/tabs/{tabId}/snapshot?userId={SID}&full={str(full).lower()}")
    try:
        d = json.loads(snap)
        return d.get("snapshot", ""), d.get("url", "")
    except: return "", ""

def click_ref(tabId, ref):
    try:
        r = cf("POST", f"/tabs/{tabId}/click", {"userId": SID, "ref": ref})
        return json.loads(r).get("ok", False)
    except: return False

def type_ref(tabId, ref, text):
    try:
        r = cf("POST", f"/tabs/{tabId}/type", {"userId": SID, "ref": ref, "text": text})
        return json.loads(r).get("ok", False)
    except: return False

def navigate(tabId, url):
    try:
        r = cf("POST", f"/tabs/{tabId}/navigate", {"userId": SID, "url": url})
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
        log(f"Login form not found. Refs: {list(refs.items())[:10]}")
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

# ── Apply ────────────────────────────────────────────────────────────────────
def apply_to_job(job_url, job_title, budget):
    global apply_tab, applying

    with apply_lock:
        if applying:
            log("Apply already in progress, skipping")
            return False, "Apply in progress"
        applying = True

    try:
        tabId = get_shared_tab("apply")
        if not tabId:
            return False, "Cannot get apply tab"

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

        price_range = get_price_range(budget)

        # Textarea
        textarea_ref = None
        for idx, info in refs2.items():
            if info["type"] in ("textbox", "textarea") or "letter" in info.get("label", "").lower():
                textarea_ref = f"e{idx}"
                break

        proposal = generate_proposal(job_title, budget, client_name, price_range)

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
        return True, f"Applied ✓ ({price_range})"

    finally:
        with apply_lock:
            applying = False

# ── Browse + Apply (single-threaded) ───────────────────────────────────────
def do_browse():
    global last_browse, browsing

    with browse_lock:
        if browsing:
            log("Browse already in progress")
            return
        browsing = True

    log("=== Starting browse ===")
    tg("🔍 <b>Scanning CryptoTask...</b>")

    tabId = get_shared_tab("browse")
    if not tabId:
        tg("❌ Cannot get browse tab")
        with browse_lock: browsing = False
        return

    try:
        if not ct_login(tabId):
            tg("⚠️ Login failed")
            with browse_lock: browsing = False
            return

        # Scan only 3 pages (lean)
        all_jobs = []
        seen = set()
        for page in range(1, 4):
            url = f"{CT_HOST}/en/tasks" if page == 1 else f"{CT_HOST}/en/tasks?page={page}"
            log(f"Scan page {page}: {url}")
            navigate(tabId, url)
            time.sleep(8)

            snap, _ = get_snapshot(tabId)
            if not snap or len(snap) < 200:
                log(f"Page {page}: empty")
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

        if not all_jobs:
            tg("❌ No jobs found")
            return

        tg(f"📋 Found <b>{len(all_jobs)}</b> jobs. Applying to matches...")

        applied = skipped = errors = 0
        for i, job in enumerate(all_jobs):
            title = job["title"]
            url = job["url"]
            budget = job.get("budget", "?")

            log(f"[{i+1}/{len(all_jobs)}] {title[:60]}")

            score, reason = keyword_score(title)
            if score == 0:
                log(f"  Skip: {reason}")
                skipped += 1
                continue

            if score < 6.0:  # Higher threshold for lean version
                log(f"  Low score ({score:.1f}), skipping")
                skipped += 1
                continue

            success, msg = apply_to_job(url, title, budget)

            if success:
                applied += 1
                tg(f"✅ <b>{title[:50]}</b>\nBudget: {budget}\n{msg}")
                save_applied(job, score)
            else:
                errors += 1
                tg(f"❌ <b>{title[:50]}</b>\n{msg}")

            time.sleep(8)  # Longer delay between applies

        tg(f"📊 <b>Done!</b>\nScanned: {len(all_jobs)}\n✅ Applied: {applied}\n⏭️ Skipped: {skipped}\n❌ Errors: {errors}")
        log(f"Browse complete: {applied} applied, {skipped} skipped, {errors} errors")
        last_browse = time.time()

    finally:
        with browse_lock: browsing = False

def save_applied(job, score):
    try:
        entry = {"time": datetime.now().isoformat(), "title": job["title"],
                 "url": job["url"], "score": round(score, 1)}
        with open(APPLIED_F, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except: pass

# ── Telegram Commands ───────────────────────────────────────────────────────
GREETINGS = ["hello", "hi", "hey", "ola", "oi", "bom dia", "good morning", "good afternoon", "good evening"]
THANKS = ["thanks", "thank you", "obrigado", "merci", "gracias"]
GOODBYE = ["bye", "goodbye", "see you"]

SERVICES = {
    "web dev": "We build web apps — React/Django/FastAPI/Node. Prices from $15!",
    "api": "REST/GraphQL APIs with Python or Node.js. From $25.",
    "backend": "Backend systems, microservices, databases. From $25.",
    "blockchain": "Solidity/Web3 smart contracts, DeFi, NFTs. Expert level.",
    "scraper": "Web scraping — Python, fast and reliable. From $15.",
    "automation": "Scripts, CI/CD, task automation. Save time and money.",
    "ai": "AI integration — LLM APIs, chatbots, automation.",
    "bot": "Telegram/Discord bots. Fast and affordable.",
    "python": "Python development — FastAPI, Flask, data pipelines. From $15.",
    "javascript": "JS/TS — Node.js, React, Vue. Modern frontend/backend.",
    "full stack": "Full-stack development. Frontend + backend + DB. From $25.",
    "smart contract": "Solidity smart contracts, audits, deployment.",
}

def handle_question(text):
    text_lower = text.lower()
    inc_stat("questions_answered")

    for g in GREETINGS:
        if g in text_lower:
            return random.choice(["Hello! 👋 How can I help?", "Hi! What are you working on?", "Hey! Project to discuss?"])

    for t in THANKS:
        if t in text_lower:
            return "You're welcome! 😊 What's next?"

    for g in GOODBYE:
        if g in text_lower:
            return "Good luck with your project! 💪"

    for svc, reply in SERVICES.items():
        if svc in text_lower:
            return f"💼 {reply}"

    return None

def cmd_status():
    load_stats()
    camfox_ok_val = camfox_ok()
    try:
        started = datetime.fromisoformat(stats["started"])
        hours = int((datetime.now() - started).total_seconds() / 3600)
        uptime = f"{hours}h"
    except: uptime = "?"
    tg((f"🤖 <b>RGODIM LTD Agent</b>\n\n"
        f"Status: {'✅ Online' if camfox_ok_val else '❌ Camfox down'}\nUptime: {uptime}\n\n"
        f"📊 Stats:\nJobs scanned: {stats.get('jobs_browsed',0)}\nApplied: {stats.get('applied',0)}\nQuestions: {stats.get('questions_answered',0)}\n\n"
        f"💰 Pricing: $15-300\n/browse /help"))

def cmd_browse():
    global browsing
    with browse_lock:
        if browsing:
            tg("⏳ Already scanning...")
            return
        browsing = True
    tg("🚀 <b>Starting scan!</b> (3 pages)")
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
    tg(f"🎯 Applying: {args[:100]}")
    def do():
        success, msg = apply_to_job(args, args.split("/")[-1], "?")
        if success:
            tg(f"✅ Applied!\n{msg}")
        else:
            tg(f"❌ {msg}")
    Thread(target=do, daemon=True).start()

def cmd_applied():
    try:
        with open(APPLIED_F) as f:
            lines = f.readlines()[-10:]
        if lines:
            msg = "📝 <b>Recent:</b>\n\n"
            for l in lines:
                j = json.loads(l)
                msg += f"• {j['title'][:50]}\n  {j['url'][:70]}\n\n"
            tg(msg[:4096])
        else:
            tg("No applications yet. /browse to start!")
    except: tg("No applications yet.")

def cmd_pricing():
    tg(("💰 <b>Pricing:</b>\n\n"
        "🟢 Small ($15-25): Bug fix, script, config\n"
        "🟡 Medium ($25-75): REST API, scraper, chatbot\n"
        "🟠 Large ($75-150): Web app, backend, blockchain\n"
        "🔴 Enterprise ($150-300): Complex systems\n\n"
        "<i>Negotiable based on scope.</i>"))

def cmd_help():
    tg(("📋 <b>Commands:</b>\n\n"
        "/status — Dashboard\n"
        "/browse — Scan & apply (3 pages)\n"
        "/apply <url> — Apply to job\n"
        "/applied — Recent apps\n"
        "/pricing — Prices\n"
        "/portfolio — Our work\n"
        "/help — This\n\n"
        "Ask me anything!"))

def cmd_portfolio():
    if os.path.exists(PORTFOLIO):
        with open(PORTFOLIO) as f:
            tg("📁 <b>Portfolio:</b>\n\n" + f.read()[:4000])
    else:
        tg("Portfolio coming soon! /browse to see me in action 🚀")

def handle_telegram():
    try:
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
                        else: tg("Unknown command. /help for list.")
                    else:
                        reply = handle_question(text)
                        if reply:
                            tg(reply)
                        elif len(text) > 3:
                            tg("I'm here to help! Type /browse to find jobs or /pricing for our rates.")
    except Exception as e:
        log(f"Telegram error: {e}")

# ── Watchdog ───────────────────────────────────────────────────────────────
def watchdog():
    global last_browse, shutdown
    log("Watchdog starting...")
    load_stats()
    tg("🤖 <b>RGODIM LTD Agent</b> — Online! /help for commands 💼")

    time.sleep(5)

    if time.time() - last_browse > 3600:
        tg("🔄 Initial scan...")
        try: do_browse()
        except Exception as e: log(f"Initial browse error: {e}")

    while not shutdown:
        try:
            handle_telegram()

            now = time.time()
            if now - last_browse > 4 * 3600:
                with browse_lock:
                    if not browsing:
                        browsing = True
                        tg("🔄 <b>Auto scan (4h)</b>")
                        Thread(target=_browse_thread, daemon=True).start()
                        last_browse = now

            time.sleep(30)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"Watchdog error: {e}")
            time.sleep(60)

def signal_handler(sig, frame):
    global shutdown
    shutdown = True

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "watchdog"
    if cmd == "watchdog": watchdog()
    elif cmd == "browse": do_browse()
    elif cmd == "status": cmd_status()
    elif cmd == "telegram-poll": handle_telegram()

if __name__ == "__main__":
    main()
