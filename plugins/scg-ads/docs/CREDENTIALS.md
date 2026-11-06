# How to get every key and id (and where they go)

Everything is entered **in your own terminal** with `scripts/configure.py`. Nothing is typed into the chat, and the agent never reads `config.toml` or `adc.json`.

| What | Where you get it | Where it is stored |
|---|---|---|
| Manager (MCC) account id | Google Ads, top-right of the page (`123-456-7890`) | `config.toml` `[credentials].login_customer_id` |
| OAuth client JSON | Google Cloud Console > Credentials | only used once by `configure.py login`, then delete it |
| Refresh token | `configure.py login` (browser sign-in) | `~/.config/scg-ads/adc.json` (mode 600) |
| Account ids (10 digits) | you just type them: `configure.py use 123-456-7890` | not in the config - each gets a workspace folder (labels in `[[accounts]]` are optional) |
| Fork clone path | where you ran `git clone` | `config.toml` `[mcp].fork_dir` |

Files live in `~/.config/scg-ads/` (folder 700, files 600; override with `SCG_ADS_CONFIG`). The tool refuses to write secrets inside a git repository. Real environment variables (`GOOGLE_APPLICATION_CREDENTIALS`, ...) override the file.

## Step 1 - Manager (MCC) account
1. Create one at <https://ads.google.com/home/tools/manager-accounts/> (free) or use your existing one.
2. Link the client accounts you will manage: Accounts > Sub-account settings > link existing / create new. Clients must accept the invitation.
3. Copy the MCC id (top right, 10 digits).
Skipping the MCC is possible for a single account you own: use that account's own id as the login id.

## Step 2 - Google Cloud project and OAuth client
1. <https://console.cloud.google.com/> > create a project (any name).
2. APIs & Services > Library > **Google Ads API** > Enable.
3. APIs & Services > OAuth consent screen (or "Google Auth platform"): user type **External**; app name and your email; add the scope `https://www.googleapis.com/auth/adwords` if asked; add your Google account as a **test user**.
4. **Important:** while the app is in status *Testing*, refresh tokens expire after **7 days**. For long-term use click **Publish app** (status "In production"). For personal use you will see an "unverified app" warning when signing in; that is expected, continue.
5. Credentials > Create credentials > **OAuth client ID** > application type **Desktop app** > Create > **Download JSON** (`client_secret_....json`).

## Step 3 - Sign in once
```bash
./scg-ads-plugins-marketplace/plugins/scg-ads/scripts/configure.py login --client-secret ~/Downloads/client_secret_XXXX.json
```
A browser opens. Sign in with the Google user that has access to the Ads accounts (Admin > Access and security in the MCC), click Allow. The script writes `adc.json` (mode 600). Then **delete the downloaded client_secret file**.

## Step 4 - Run the wizard (or fill the file by hand)
```bash
./scg-ads-plugins-marketplace/plugins/scg-ads/scripts/configure.py init     # asks for each value, hidden prompt for the token
```
Prefer editing by hand? Copy `config.example.toml` to `~/.config/scg-ads/config.toml`, `chmod 600` it, fill it in.

## Step 5 - Pick the account you work on (10-digit id)
The config holds only keys and tokens. Accounts are just their 10-digit ids; there is no need to register them:
```bash
configure.py use 123-456-7890                     # starts working on this account; creates its folder
configure.py use 123-456-7890 --login 7000000001  # if it is reached through a manager (MCC) other than the default
configure.py list                                 # accounts you already have folders for (no secrets; this is what the agent reads)
configure.py accounts                             # optional: discover every reachable account from the API and save short labels
```
Several accounts are normal; switch any time with `use`. Each account gets its own folder under `[workspace].root` (default `~/ads-workspaces/<id or label>/`) with `account-brief.md`, `changelog.md`, `out/`, `campaigns/`, `creatives/` and a small `account.toml` (id, login id, name). Business data, no credentials; keep it out of git.
The login id is the manager you reach the account through, or the account's own id when you access it directly; if omitted, `[credentials].login_customer_id` is used.

## Step 6 - Verify
```bash
configure.py check --mcp         # modes 600, files exist, API read works, MCP server starts
```

## Optional ids (not stored anywhere by default)
Merchant Center id (for `account_links.py invite-merchant`), GA4 property (linking is done on the GA4 side: `account_links.py ga4-howto`).

## Troubleshooting
| Message | Meaning / fix |
|---|---|
| `... NOT_APPROVED` (Keyword Planner) | The API access level does not allow Keyword Planner. Use CSV / search terms meanwhile. |
| `USER_PERMISSION_DENIED` / "User doesn't have permission to access customer" | Wrong login id for that account. `configure.py list` shows which manager it is reached through; the Google user must have access to it. |
| `invalid_grant` / `Token has been expired or revoked` | Consent screen still in Testing (7-day tokens), or access revoked. Publish the app, run `login` again. |
| `PERMISSION_DENIED ... Google Ads API has not been used in project` | Enable the Google Ads API in the Cloud project of the OAuth client (step 2.2). |
| `config.toml is inside a git repository` | By design. Keep it in `~/.config/scg-ads/`. |
| `check` says mode is not private | `chmod 600 ~/.config/scg-ads/config.toml ~/.config/scg-ads/adc.json` |

## Security
- Never paste tokens, `adc.json` or `config.toml` into a chat, issue or commit. If you did, revoke at <https://myaccount.google.com/permissions> and create a new OAuth client.
- The repo's pre-commit scan (`tools/install-hooks.sh`) blocks token patterns, secret files and personal data.
