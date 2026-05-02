# TOOLS.md — ClawOps Available Tools

## Browser Tool (Primary)

Use the `browser` tool for all web interactions, especially CryptoTask.org.

### Browser Profile for CryptoTask
- Platform: cryptotask.org
- Always logged in as: rom.godinho@gmail.com (credentials in env)
- Headless: false (use visible browser for better stability)
- User agent: Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36

### Key CryptoTask URLs
- Job feed: https://www.cryptotask.org/en/tasks
- My applications: https://www.cryptotask.org/en/applications
- In-progress: https://www.cryptotask.org/en/in-progress
- Messages: https://www.cryptotask.org/en/messages
- Login: https://www.cryptotask.org/en/login

### Typical Flows

**Login flow:**
1. Navigate to /en/login
2. Fill email field
3. Fill password field
4. Click Login button
5. Verify success by checking for RGODIM LTD in header

**Browse jobs flow:**
1. Navigate to /en/tasks
2. Filter by relevant categories (IT & Networking, Software Dev, etc.)
3. Scroll through listings
4. Click job title to read full description
5. If fit: click "Apply for job" and submit proposal

**Apply flow:**
1. From job detail page, click "Apply for job"
2. Fill proposal text (personalized — reference job details)
3. Submit application

## Session Tools

- `sessions_list` — see current conversation threads
- `sessions_send` — send message in a specific session
- Use for managing client conversations

## Cron Tools

- Set up periodic CryptoTask job checks (every 4 hours)
- Use `cron job create` to schedule

## Telegram

- Send notifications to owner via Telegram channel
- Use `openclaw message send --channel telegram --target <chat_id> --message "..."`
