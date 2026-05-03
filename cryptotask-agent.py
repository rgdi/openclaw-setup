#!/usr/bin/env python3
"""
OpenClaw CryptoTask Agent v3 - Full auto-bidding with learning
Paginate all pages, visit each job, apply with personalized proposals.
Uses Camfox browser + MiniMax AI + Telegram.
"""
import subprocess, json, time, re, sys, os
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
BOT   = "8612653411:AAE_KvNbuxIBeBP_uocTWaN3xlOBpqiva3k"
CHAT  = "6793940199"
KEY   = "sk-cp-8r2sLAzHvPzkwS7Z1yjPZWmZpBdP8YvWnQv2iHk6vBmKl4x7Y8eRmJc9nAoXdc"
BASE  = "https://api.minimaxi.com/v1"   # CORRECT MiniMax endpoint
MODEL = "MiniMax-M2.7"
CAMFOX = "http://127.0.0.1:9377"
CT_USER = "rom.godinho@gmail.com"
CT_PASS = "Mar!s0l2025"
AGENT_SID = "rgodim_agent"

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO = os.path.join(BASE_DIR, "PORTFOLIO.md")
CLIENT_PROFILES = os.path.join(BASE_DIR, "CLIENT_PROFILES.md")
DOCS_DIR = BASE_DIR

# ── Helpers ────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def curl(method, url, data=None, timeout=45):
    cmd = ["curl", "-s", "-X", method, "--max-time", str(timeout)]
    if data:
        cmd += ["-d", json.dumps(data), "-H", "Content-Type: application/json"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    return r.stdout

def cf(method, path, data=None):
    """Camfox request."""
    return curl(method, f"{CAMFOX}{path}", data)

def tg(msg):
    """Send Telegram message."""
    text = msg[:4096]
    curl("POST", f"https://api.telegram.org/bot{BOT}/sendMessage",
         {"chat_id": CHAT, "text": text, "parse_mode": "HTML"})
    log(f"Telegram sent: {text[:80]}...")

def ai(prompt, max_tokens=600):
    """Call MiniMax chat API."""
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    resp = curl("POST", f"{BASE}/chat/completions", data)
    try:
        d = json.loads(resp)
        if "choices" in d and d["choices"]:
            return d["choices"][0]["message"]["content"].strip()
        elif "error" in d:
            log(f"AI error: {d['error']}")
            return f"AI_ERROR: {d['error'].get('message', d['error'])}"
        else:
            log(f"AI unexpected response: {str(d)[:200]}")
            return f"AI_ERROR: unknown"
    except:
        log(f"AI parse error: {resp[:200]}")
        return "AI_ERROR: parse failed"

# ── Camfox helpers ──────────────────────────────────────────────────────────
def camfox_status():
    try:
        r = cf("GET", "/")
        d = json.loads(r)
        return d.get("browserRunning") and d.get("browserConnected")
    except:
        return False

def ensure_tab(userId=None, url="https://cryptotask.org/en/tasks", session=None):
    """Create or reuse a tab for a session."""
    sid = session or AGENT_SID
    resp = cf("POST", "/tabs", {"userId": sid, "sessionKey": sid, "url": url})
    d = json.loads(resp)
    tabId = d.get("tabId")
    if not tabId:
        log(f"Tab creation failed: {resp}")
        return None, None
    time.sleep(6)
    return tabId, sid

def close_tab(tabId, userId=None):
    if tabId:
        sid = userId or AGENT_SID
        cf("DELETE", f"/tabs/{tabId}?userId={sid}")

def get_snapshot(tabId, userId=None, full=True):
    sid = userId or AGENT_SID
    snap = cf("GET", f"/tabs/{tabId}/snapshot?userId={sid}&full={str(full).lower()}")
    try:
        d = json.loads(snap)
        return d.get("snapshot", ""), d.get("url", "")
    except:
        return "", ""

def click_ref(tabId, ref, userId=None):
    sid = userId or AGENT_SID
    r = cf("POST", f"/tabs/{tabId}/click", {"userId": sid, "ref": ref})
    return json.loads(r).get("ok", False)

def type_ref(tabId, ref, text, userId=None):
    sid = userId or AGENT_SID
    r = cf("POST", f"/tabs/{tabId}/type", {"userId": sid, "ref": ref, "text": text})
    return json.loads(r).get("ok", False)

def navigate(tabId, url, userId=None):
    sid = userId or AGENT_SID
    r = cf("POST", f"/tabs/{tabId}/navigate", {"userId": sid, "url": url})
    try:
        d = json.loads(r)
        return d.get("ok", False)
    except:
        return False

def wait_page(tabId, userId=None, ms=15000):
    sid = userId or AGENT_SID
    r = cf("POST", f"/tabs/{tabId}/wait", {"userId": sid, "timeout": ms})
    try:
        return json.loads(r).get("ready", False)
    except:
        return False

# ── Extract refs from snapshot ──────────────────────────────────────────────
def extract_refs(snapshot):
    """Extract ref ID -> element type from snapshot."""
    refs = {}
    lines = snapshot.split("\n")
    for line in lines:
        m = re.search(r'\[e(\d+)\](?::\s*(\w+))?', line)
        txt_m = re.search(r'textbox "([^"]+)"', line)
        btn_m = re.search(r'button "([^"]+)"', line)
        link_m = re.search(r'link "([^"]+)"', line)
        if m:
            idx = int(m.group(1))
            etype = "textbox" if txt_m else "button" if btn_m else "link" if link_m else "element"
            refs[idx] = {"type": etype}
            if txt_m: refs[idx]["label"] = txt_m.group(1)
            if btn_m: refs[idx]["label"] = btn_m.group(1)
            if link_m: refs[idx]["label"] = link_m.group(1)
    return refs

def find_refs(snapshot, pattern, types=None):
    """Find refs matching pattern in label."""
    refs = extract_refs(snapshot)
    results = {}
    for idx, info in refs.items():
        label = info.get("label", "").lower()
        if pattern.lower() in label:
            if types is None or info["type"] in types:
                results[idx] = info
    return results

# ── Job extraction ──────────────────────────────────────────────────────────
def extract_jobs(snapshot):
    """Extract job URLs and titles from snapshot."""
    jobs = []
    urls = re.findall(r"/url: (/en/tasks/[a-z0-9-]+/\d+)", snapshot)
    headings = re.findall(r'heading "([^"]+)" \[level=\d+\]:', snapshot)
    budgets = re.findall(r'\$([\d,]+(?:\.\d{2})?)', snapshot)
    seen = set()
    for i, url in enumerate(urls):
        if url in seen:
            continue
        seen.add(url)
        title = headings[i] if i < len(headings) else "?"
        budget = f"${budgets[i]}" if i < len(budgets) else "?"
        jobs.append({"url": f"https://cryptotask.org{url}", "title": title, "budget": budget})
    return jobs

# ── Login to CryptoTask ─────────────────────────────────────────────────────
def ct_login(tabId):
    """Login to CryptoTask using typed credentials."""
    log("Logging into CryptoTask...")
    navigate(tabId, "https://cryptotask.org/en/login")
    time.sleep(6)
    
    snap, _ = get_snapshot(tabId)
    refs = extract_refs(snap)
    
    # Find email and password refs
    email_ref = pass_ref = submit_ref = None
    for idx, info in refs.items():
        label = info.get("label", "").lower()
        if "email" in label and info["type"] == "textbox":
            email_ref = f"e{idx}"
        elif "password" in label and info["type"] == "textbox":
            pass_ref = f"e{idx}"
        elif info["type"] == "button" and ("login" in label or "submit" in label):
            submit_ref = f"e{idx}"
    
    if not email_ref or not pass_ref:
        log(f"Could not find form fields. Refs: {refs}")
        return False
    
    if submit_ref:
        type_ref(tabId, email_ref, CT_USER)
        time.sleep(1)
        type_ref(tabId, pass_ref, CT_PASS)
        time.sleep(1)
        click_ref(tabId, submit_ref)
    else:
        type_ref(tabId, email_ref, CT_USER)
        time.sleep(0.5)
        click_ref(tabId, email_ref)  # Move to next field
        time.sleep(0.5)
        type_ref(tabId, pass_ref, CT_PASS)
        time.sleep(0.5)
        # Try pressing Enter
        cf("POST", f"/tabs/{tabId}/press", {"userId": AGENT_SID, "key": "Enter"})
    
    time.sleep(8)
    
    # Check if logged in
    snap2, url2 = get_snapshot(tabId)
    if "/en/login" in url2 or ("email" in snap2.lower() and "password" in snap2.lower() and "login" in snap2.lower()):
        log("Login FAILED - still on login page")
        return False
    
    log("Login SUCCESS!")
    return True

# ── Proposal generation ──────────────────────────────────────────────────────
def generate_proposal(job_title, job_desc, budget, client_name, tone="professional"):
    """Generate a personalized proposal using AI."""
    
    # Load portfolio for context
    portfolio = ""
    if os.path.exists(PORTFOLIO):
        with open(PORTFOLIO) as f:
            portfolio = f.read()[:2000]
    
    tone_guidance = {
        "professional": "Be professional and concise. 3-4 short paragraphs max.",
        "startup": "Be direct, outcome-focused. Mention speed and MVP approach.",
        "web3": "Casual-technical, show blockchain fluency. Use crypto-native language.",
        "enterprise": "Formal, structured, milestone-based approach. Use professional tone.",
        "friendly": "Warm, approachable, show genuine interest. Be conversational."
    }
    
    guidance = tone_guidance.get(tone, tone_guidance["professional"])
    
    prompt = f"""You are a developer at RGODIM LTD writing a proposal for a freelance job.

COMPANY PROFILE:
{portfolio}

JOB:
Title: {job_title}
Budget: {budget}
Client: {client_name}
Description excerpt: {job_desc[:1500]}

TASK:
Write a compelling proposal message (150-300 words) to apply for this job.

TONE: {guidance}

REQUIREMENTS:
- Start with genuine greeting addressing client's needs
- Mention relevant skills/experience from portfolio
- Be specific about what you'll deliver
- Show understanding of their project
- End with clear next step
- NEVER be arrogant, never lie about experience
- NEVER use placeholders like "I can start immediately" without saying when
- NEVER promise things you can't deliver

Output ONLY the proposal text, no intro or explanation."""
    
    result = ai(prompt, 400)
    if result.startswith("AI_ERROR:"):
        # Fallback proposal
        return f"""Hello,

I noticed your project and believe I can deliver exactly what you need.

I have extensive experience in similar projects and can start immediately.

Please share more details so we can discuss specifics.

Best regards,
RGODIM LTD"""
    return result

# ── Job application ──────────────────────────────────────────────────────────
def apply_to_job(tabId, job_url, job_title, budget):
    """Navigate to job and apply."""
    log(f"Applying to: {job_title}")
    
    # Navigate to job
    navigate(tabId, job_url)
    time.sleep(8)
    
    snap, _ = get_snapshot(tabId)
    refs = extract_refs(snap)
    
    # Check if logged in
    if "/en/login" in snap.lower() and "apply" in snap.lower():
        log("Not logged in - attempting login...")
        if not ct_login(tabId):
            return False, "Login failed"
        snap, _ = get_snapshot(tabId)
        refs = extract_refs(snap)
    
    # Find Apply button
    apply_ref = None
    for idx, info in refs.items():
        label = info.get("label", "").lower()
        if "apply" in label and info["type"] == "button":
            apply_ref = f"e{idx}"
            break
    
    if not apply_ref:
        # Try to find it as a link
        for idx, info in refs.items():
            label = info.get("label", "").lower()
            if "apply" in label and info["type"] == "link":
                apply_ref = f"e{idx}"
                break
    
    if not apply_ref:
        # Try clicking any visible apply text
        clickable = find_refs(snap, "apply", types=["button", "link"])
        if clickable:
            apply_ref = f"e{list(clickable.keys())[0]}"
    
    if not apply_ref:
        return False, "No Apply button found"
    
    log(f"Clicking apply button: {apply_ref}")
    click_ref(tabId, apply_ref)
    time.sleep(5)
    
    snap2, _ = get_snapshot(tabId)
    
    # Look for proposal text area
    textareas = find_refs(snap2, "", types=["textbox", "textarea"])
    submit_ref = None
    
    # Find submit button
    for idx, info in refs.items():
        label = info.get("label", "").lower()
        if info["type"] == "button" and ("submit" in label or "send" in label or "apply" in label or "confirm" in label):
            submit_ref = f"e{idx}"
            break
    
    # Extract client name from job page
    client_m = re.search(r'link "([^"]+)" \[e\d+\]:\s*/url: /en/clients/', snap)
    client_name = client_m.group(1) if client_m else "there"
    
    # Extract job description
    desc_start = snap.find("Job details")
    job_desc = snap[desc_start:desc_start+2000] if desc_start > 0 else snap[:2000]
    
    # Generate proposal
    proposal = generate_proposal(job_title, job_desc, budget, client_name)
    
    # Type proposal if textarea found
    if textareas:
        textarea_ref = f"e{list(textareas.keys())[0]}"
        log(f"Typing proposal into {textarea_ref} ({len(proposal)} chars)")
        type_ref(tabId, textarea_ref, proposal)
        time.sleep(2)
    
    # Click submit
    if submit_ref:
        log(f"Submitting with {submit_ref}")
        click_ref(tabId, submit_ref)
        time.sleep(5)
    else:
        log("No submit button found - may have submitted already or need more steps")
        return False, "No submit button found"
    
    # Check result
    snap3, _ = get_snapshot(tabId)
    if "applied" in snap3.lower() or "success" in snap3.lower() or "submitted" in snap3.lower():
        return True, proposal[:100]
    
    return True, "Applied (confirmation unclear)"

# ── Job matching ─────────────────────────────────────────────────────────────
SERVICE_KEYWORDS = [
    "web", "backend", "frontend", "python", "node", "javascript", "typescript",
    "api", "rest", "graphql", "database", "postgresql", "mongodb", "docker",
    "devops", "cloud", "aws", "gcp", "blockchain", "smart contract", "solidity",
    "web3", "nft", "ethereum", "bitcoin", "llm", "ai", "machine learning",
    "fastapi", "flask", "django", "express", "react", "vue", "kubernetes",
    "ci/cd", "linux", "server", "microservice", "data pipeline", "etl",
    "scraper", "automation", "script", "integration"
]

SKIP_KEYWORDS = [
    "design", "logo", "graphic", "illustration", "video", "animation",
    "photoshop", "illustrator", "figma", "ui/ux", "ui design", "ux design",
    "content writing", "copywriting", "blog post", "article writing",
    "data entry", "excel", "spreadsheet", "virtual assistant",
    "seo specialist", "social media", "marketing only", "mobile app only",
    "ios only", "android only", "swift", "kotlin"
]

def is_interested(title, desc=""):
    """Check if job matches our services."""
    text = (title + " " + desc).lower()
    
    # Explicit skips
    for kw in SKIP_KEYWORDS:
        if kw.lower() in text:
            return False, f"Explicit skip: contains '{kw}'"
    
    # Check for interested keywords
    matches = [kw for kw in SERVICE_KEYWORDS if kw.lower() in text]
    if matches:
        return True, f"Match: {', '.join(matches[:3])}"
    
    # Default: interested if it could be dev-related
    if any(w in text for w in ["develop", "build", "project", "app", "platform", "system"]):
        return True, "Potential dev project"
    
    return False, "No relevant skills found"

def rate_job_ai(title, desc, budget):
    """Rate job fit 0-10 using AI with learned client preferences."""
    prompt = f"""Rate this freelance job fit for RGODIM LTD.

Company: RGODIM LTD - Web Development, Backend (Python/Node), API Development, AI/LLM Integration, Blockchain, DevOps

Job Title: {title}
Budget: {budget}
Description: {desc[:800]}

Score 0-10 and give one line reason.
Format: SCORE: X/10 | REASON: ...
Only output the score line."""
    
    result = ai(prompt, 80)
    try:
        if "SCORE:" in result:
            score_line = result.split("SCORE:")[1].split("|")[0].strip()
            score = int(score_line.split("/")[0])
            reason = result.split("REASON:")[1].strip() if "REASON:" in result else result[:80]
            return score, reason
        return 5, result[:80]
    except:
        return 5, result[:80] if result else "parse error"

# ── Scan all pages ──────────────────────────────────────────────────────────
def scan_all_pages(tabId, max_pages=10):
    """Scan multiple pages, collect all job links."""
    all_jobs = []
    seen = set()
    page = 1
    
    tg(f"🔍 Starting full job scan...\nScanning up to {max_pages} pages")
    log(f"Starting scan, max_pages={max_pages}")
    
    while page <= max_pages:
        url = "https://cryptotask.org/en/tasks" if page == 1 else f"https://cryptotask.org/en/tasks?page={page}"
        log(f"=== Page {page}: {url} ===")
        
        navigate(tabId, url)
        time.sleep(8)
        
        snap, _ = get_snapshot(tabId)
        if not snap or len(snap) < 200:
            log(f"Page {page}: empty/failed")
            break
        
        jobs = extract_jobs(snap)
        log(f"Page {page}: {len(jobs)} jobs, {len(snap)} chars snapshot")
        
        new = 0
        for job in jobs:
            if job["url"] not in seen:
                seen.add(job["url"])
                job["page"] = page
                all_jobs.append(job)
                new += 1
        
        log(f"Page {page}: {new} new jobs")
        
        if not jobs or len(jobs) < 5:
            break
        
        page += 1
        time.sleep(3)
    
    log(f"Total unique jobs: {len(all_jobs)}")
    return all_jobs

# ── Process jobs ─────────────────────────────────────────────────────────────
def process_jobs(tabId, jobs):
    """Visit each job, apply to matches."""
    total = len(jobs)
    applied = []
    skipped = []
    errors = []
    
    tg(f"📋 Processing {total} jobs...")
    
    for i, job in enumerate(jobs):
        idx = i + 1
        title = job["title"]
        url = job["url"]
        budget = job.get("budget", "?")
        
        log(f"[{idx}/{total}] {title[:60]}")
        
        # Quick title check
        interested, reason = is_interested(title)
        if not interested:
            log(f"  SKIP (title): {reason}")
            skipped.append({"title": title, "url": url, "reason": reason})
            continue
        
        # Navigate to job page
        navigate(tabId, url)
        time.sleep(8)
        snap, _ = get_snapshot(tabId)
        
        if not snap or len(snap) < 200:
            log(f"  ERROR: Could not load job page")
            errors.append({"title": title, "url": url, "reason": "load failed"})
            continue
        
        # Check if job is still accepting applications
        if "accepting applications" not in snap.lower() and "open" not in snap.lower():
            if "filled" in snap.lower() or "closed" in snap.lower():
                log(f"  SKIP: Job filled/closed")
                skipped.append({"title": title, "url": url, "reason": "filled/closed"})
                continue
        
        # AI rating
        score, ai_reason = rate_job_ai(title, snap[:2000], budget)
        log(f"  Score: {score}/10 - {ai_reason[:60]}")
        
        if score < 4:
            log(f"  SKIP (score {score})")
            skipped.append({"title": title, "url": url, "reason": f"score {score} - {ai_reason}"})
            continue
        
        # Apply!
        success, msg = apply_to_job(tabId, url, title, budget)
        
        if success:
            log(f"  ✅ APPLIED: {msg[:80]}")
            applied.append({"title": title, "url": url, "budget": budget, "score": score})
            tg(f"✅ <b>Applied to:</b>\n{title}\nBudget: {budget}\nScore: {score}/10\n\nProposal:\n{msg[:300]}...")
        else:
            log(f"  ❌ Could not apply: {msg}")
            errors.append({"title": title, "url": url, "reason": msg})
            tg(f"❌ <b>Could not apply:</b>\n{title}\n{msg}")
        
        time.sleep(5)
    
    return applied, skipped, errors

# ── Learn from interaction ───────────────────────────────────────────────────
def learn_from_client(client_name, job_title, outcome, proposal_preview):
    """Save client interaction to memory for future tone adjustment."""
    entry = f"""
### {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Client**: {client_name}
**Job**: {job_title}
**Outcome**: {outcome}
**Proposal Preview**: {proposal_preview[:200]}
"""
    
    try:
        with open(CLIENT_PROFILES, "a") as f:
            f.write(entry)
        log(f"Learned from client interaction: {client_name}")
    except Exception as e:
        log(f"Could not save client profile: {e}")

# ── Main actions ──────────────────────────────────────────────────────────────
def action_status():
    log("Status check...")
    camfox_ok = camfox_status()
    tg(f"🤖 RGODIM LTD Agent Status\n"
       f"Camfox: {'✅ Running' if camfox_ok else '❌ Down'}\n"
       f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
       f"Mode: Autonomous Job Scanner")
    log(f"Status: Camfox={'OK' if camfox_ok else 'FAIL'}")

def action_browse():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    log(f"=== FULL JOB SCAN STARTED {ts} ===")
    
    camfox_ok = camfox_status()
    if not camfox_ok:
        tg("❌ Camfox browser is down. Cannot scan.")
        log("Camfox not running")
        return
    
    # Create dedicated tab for scanning
    tabId, sid = ensure_tab(session=f"scan_{int(time.time())}")
    if not tabId:
        tg("❌ Could not create browser tab.")
        return
    
    try:
        # Login first
        if not ct_login(tabId):
            tg("⚠️ Login failed. Trying to scan anyway...")
        
        # Scan all pages
        jobs = scan_all_pages(tabId, max_pages=10)
        
        if not jobs:
            tg("❌ No jobs found.")
            return
        
        tg(f"📦 Found {len(jobs)} jobs. Processing...")
        
        # Process each job
        applied, skipped, errors = process_jobs(tabId, jobs)
        
        # Summary
        summary = f"""
📊 <b>Scan Complete!</b>

Jobs found: {len(jobs)}
✅ Applied: {len(applied)}
⏭️ Skipped: {len(skipped)}
❌ Errors: {len(errors)}

Time: {datetime.now().strftime('%H:%M:%S')}
"""
        tg(summary)
        log(f"=== SCAN COMPLETE: {len(applied)} applied, {len(skipped)} skipped, {len(errors)} errors ===")
        
        # Save applied jobs
        if applied:
            try:
                with open(os.path.join(DOCS_DIR, "applied_jobs.json"), "a") as f:
                    for a in applied:
                        f.write(json.dumps({"time": ts, **a}) + "\n")
            except:
                pass
        
    finally:
        close_tab(tabId)

def action_apply(job_url):
    """Apply to a specific job URL."""
    log(f"Apply to specific job: {job_url}")
    tg(f"🎯 Applying to:\n{job_url}")
    
    camfox_ok = camfox_status()
    if not camfox_ok:
        tg("❌ Camfox browser is down.")
        return
    
    tabId, sid = ensure_tab(session=f"apply_{int(time.time())}", url=job_url)
    if not tabId:
        tg("❌ Could not create browser tab.")
        return
    
    try:
        if not ct_login(tabId):
            tg("⚠️ Login failed.")
        
        # Get job title
        time.sleep(8)
        snap, _ = get_snapshot(tabId)
        title_m = re.search(r'heading "([^"]+)" \[level=1\]:', snap)
        title = title_m.group(1) if title_m else "Unknown Job"
        
        budget_m = re.search(r'\$[\d,]+(?:\.\d{2})?\s*(?:per month|per hour|per project)?', snap)
        budget = budget_m.group() if budget_m else "?"
        
        success, msg = apply_to_job(tabId, job_url, title, budget)
        
        if success:
            tg(f"✅ <b>Applied to:</b>\n{title}\nBudget: {budget}\n\nProposal:\n{msg[:400]}...")
            learn_from_client("Direct Apply", title, "Applied", msg)
        else:
            tg(f"❌ Could not apply:\n{title}\n{msg}")
        
    finally:
        close_tab(tabId)

def action_portfolio():
    """Send portfolio via Telegram."""
    if os.path.exists(PORTFOLIO):
        with open(PORTFOLIO) as f:
            content = f.read()
        tg(f"📁 <b>RGODIM LTD Portfolio</b>\n\n{content[:4000]}")
    else:
        tg("Portfolio file not found.")

def action_applied():
    """Show recent applications."""
    applied_file = os.path.join(DOCS_DIR, "applied_jobs.json")
    if os.path.exists(applied_file):
        with open(applied_file) as f:
            lines = f.readlines()[-10:]
        if lines:
            msg = "📝 <b>Recent Applications:</b>\n\n"
            for line in lines:
                try:
                    job = json.loads(line)
                    msg += f"• {job['title']}\n  Budget: {job.get('budget','?')} Score: {job.get('score','?')}/10\n  {job['url']}\n\n"
                except:
                    pass
            tg(msg[:4096])
        else:
            tg("No applications yet.")
    else:
        tg("No applications file yet.")

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    
    log(f"Action: {action} {arg}")
    
    if action == "status":
        action_status()
    elif action == "browse":
        action_browse()
    elif action == "apply":
        if not arg:
            tg("Usage: apply <job_url>")
        else:
            action_apply(arg)
    elif action == "portfolio":
        action_portfolio()
    elif action == "applied":
        action_applied()
    else:
        tg(f"Unknown action: {action}\nCommands: status, browse, apply <url>, portfolio, applied")

if __name__ == "__main__":
    main()
