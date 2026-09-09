# XCancel Slack bot

![XCancel logo](<assets/2026-09-09 - xcancel-readme-logo.png>)

This Slack app watches public and private channels where it has been invited. When a person posts a message containing an X or Twitter URL, the app replies in the message thread with an `xcancel.com` link for each distinct matching URL.

For example, a message containing `https://x.com/example/status/123` receives this thread reply:

```text
*X-Cancel Link:* https://xcancel.com/example/status/123
```

The app uses Slack Socket Mode, so it can run locally without a public HTTP endpoint. It serves one Slack workspace and processes new human messages, including messages posted in existing threads. Message edits, deletion events, bot messages, and messages without matching URLs are ignored.

## Bring the app up with the Slack CLI

The CLI obtains the bot and app-level tokens and passes them to the Python process when you run `slack run`. You do not need to copy tokens or export environment variables for this workflow.

The bot runs on the computer executing the command. Keep that computer awake, connected to the internet, and the process running while testing. Installing the app with `--environment deployed` records an installation in Slack; it does not host this Python app.

### 1. Prepare the project

Install Python 3 and the [Slack CLI](https://docs.slack.dev/tools/slack-cli/guides/installing-the-slack-cli-for-mac-and-linux/). You need permission to install apps in the target workspace.

For a fresh checkout:

```sh
git clone https://github.com/msaum/xcancel.git
cd xcancel
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

For an existing checkout, open a terminal in its project directory. All subsequent commands run there. The CLI hook in `.slack/hooks.json` explicitly uses `.venv/bin/python`, so keep that environment at the project root.

### 2. Authenticate the CLI

```sh
slack login
slack auth list
```

Complete the login prompts using the Slack account that can manage the app. If already signed in, `slack auth list` is enough to confirm the workspace and team ID.

Find your workspace's team ID in `slack auth list`. The examples below use `YOUR_TEAM_ID` and `YOUR_APP_ID` as placeholders. Replace them with your workspace's team ID and the app ID returned by installation.

### 3. Select or install the app

Check the project's saved installations:

```sh
slack app list --team YOUR_TEAM_ID
```

If the intended app is already installed and listed, continue to step 4. To create an installation, run the following with your workspace's team ID and note the returned app ID:

```sh
slack app install --team YOUR_TEAM_ID --environment deployed
```

The CLI reads `manifest.json` and uploads `assets/icon.png`. Follow any permission prompts. A successful installation reports `Status: Installed`.

### 4. Link the installed app for local execution

`slack run` needs a local app mapping. Link the existing installation so the CLI starts the same bot that is already in your channels:

```sh
slack app link --team YOUR_TEAM_ID --app YOUR_APP_ID --environment local
```

If this reports `app_found`, check `slack app list` and confirm that the intended app is `YOUR_APP_ID`. Then repeat with `--force` to update the saved mapping:

```sh
slack app link --team YOUR_TEAM_ID --app YOUR_APP_ID --environment local --force
```

This mapping is saved in the Git-ignored `.slack/apps.dev.json`. Repeat this step after a fresh clone or on another computer. The app ID stays the same; Slack labels the app `xcancel (local)` during the local run.

### 5. Start the bot

```sh
slack run --app YOUR_APP_ID --team YOUR_TEAM_ID --no-color
```

The CLI applies the manifest, installs the app as needed, supplies `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN`, and starts `app.py` through the Python hook. Wait for these log messages:

```text
Bolt app is running!
Starting to receive messages from a new connection
```

Leave the terminal running. Use one running process for this app. Stop it with `Ctrl-C`; run the same command again to restart. The local CLI run watches Python files for changes.

### 6. Invite and test

In Slack, open the intended channel and use its **Agents & apps** settings to add XCancel, or use `/invite` and select the XCancel app. It must be a member of each public or private channel it should monitor. Choose a channel where you have permission to test the app.

Post this test message yourself:

```text
XCancel test: https://x.com/example/status/123 https://twitter.com/example/status/456
```

Expect one thread reply containing two bold **X-Cancel Link:** labels and the corresponding `xcancel.com` URLs. These example post IDs test URL conversion; they do not need to identify real posts. Repeat a link to check deduplication, and post a link inside the thread to check thread replies. Editing the source message does not trigger another reply.

### Apply updates

Stop the running process with `Ctrl-C`, then update the checkout and dependencies:

```sh
git pull --ff-only
.venv/bin/python -m pip install -r requirements.txt
slack app install --team YOUR_TEAM_ID --app YOUR_APP_ID
slack run --app YOUR_APP_ID --team YOUR_TEAM_ID --no-color
```

Complete any permission prompts when scopes change. Private-channel support requires `groups:history` and `message.groups`; the manifest also includes `channels:history`, `message.channels`, and `chat:write`. Direct messages and group DMs are ignored.

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| `runtime_not_found` or missing `slack_cli_hooks` | Confirm `.venv/bin/python` exists and rerun `.venv/bin/python -m pip install -r requirements.txt`. |
| `app_not_found` from `slack run` | Complete step 4 for the same team and app IDs. A deployed mapping alone is insufficient for local execution. |
| CLI authentication fails | Run `slack login` again and confirm the workspace with `slack auth list`. |
| App appears installed but sends no replies | Check that the process is connected and the bot is a channel member. Confirm the message is new, human-authored, and contains an HTTP(S) X/Twitter URL. |
| Private-channel messages produce no reply | Apply the updated manifest and permissions, then restart the process. |

## Run Python directly with manually managed tokens

Use this path when starting `app.py` without the Slack CLI. Select your installation from [Your Apps](https://api.slack.com/apps).

1. In **OAuth & Permissions**, install or reinstall the app if needed and copy its **Bot User OAuth Token**, beginning with `xoxb-`.
2. In **Basic Information → App-Level Tokens**, generate a token with the `connections:write` scope. This token begins with `xapp-`. Socket Mode must be enabled, as configured in this project's manifest.

In zsh, these prompts keep token values out of shell history and hide them while you paste:

```zsh
read -rs 'SLACK_BOT_TOKEN?Paste bot token: '; printf '\n'
read -rs 'SLACK_APP_TOKEN?Paste app-level token: '; printf '\n'
export SLACK_BOT_TOKEN SLACK_APP_TOKEN
.venv/bin/python app.py
```

Token entry happens locally in your terminal. Keep tokens out of Git, screenshots, and shared logs. `app.py` reads environment variables directly; it does not automatically load a `.env` file. Stop with `Ctrl-C` and clear the shell variables when finished:

```sh
unset SLACK_BOT_TOKEN SLACK_APP_TOKEN
```

## Host with Docker

Use an always-on host with Docker installed and outbound HTTPS/WebSocket access to Slack. The container runs `app.py` directly. Configure tokens at runtime using the manual token steps above; the Slack CLI and its local credentials are not included in the image.

### Build the image

From the project root:

```sh
docker build --pull -t xcancel:latest .
```

The image uses Python 3.14, installs `requirements-runtime.txt`, and runs as an unprivileged user. The build context excludes credentials, Git data, and local caches.

### Supply the tokens

Create a private environment file on the Docker host. The following commands create `.env.docker` if needed without overwriting an existing file:

```sh
touch .env.docker
chmod 600 .env.docker
```

Edit it locally and replace the placeholders with the bot and app-level tokens from the same Slack app:

```dotenv
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
```

Use plain values without shell `export` statements or surrounding quotes. This file is excluded from Git and the Docker build context. Docker administrators can inspect container environment variables, so restrict access to the host.

### Start and verify

Stop any existing local `slack run` or Python process for this bot before starting the container. Keep one instance running.

```sh
docker run -d \
  --name xcancel \
  --restart unless-stopped \
  --env-file .env.docker \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  xcancel:latest

docker logs --tail 50 -f xcancel
```

Wait for `Bolt app is running!` and `Starting to receive messages from a new connection`, then post a test link in a channel where the bot has been invited. Press `Ctrl-C` to stop following logs; the detached container keeps running. Socket Mode uses outbound connections, so no port mapping or public endpoint is needed.

Configure Docker to start when the host boots. The `unless-stopped` policy restarts the container after failures or daemon restarts; an explicitly stopped container stays stopped until started again. See [Docker restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/).

### Stop, restart, and update

```sh
docker stop xcancel
docker start xcancel
```

To deploy code or dependency updates, build the new image before replacing the container:

```sh
git pull --ff-only
docker build --pull -t xcancel:latest .
docker stop xcancel
docker rm xcancel
```

Run the `docker run` command above again, then verify the connection logs and test a link. The bot keeps no persistent application data in the container; its duplicate-event cache resets on restart. The environment file remains on the host.

Token changes also require recreating the container with `--env-file`; `docker restart` retains its existing environment. Apply any changed Slack scopes or event subscriptions with `slack app install --team YOUR_TEAM_ID --app YOUR_APP_ID` from a CLI-authenticated checkout. Rebuilding the image alone does not update Slack's app configuration.

If the container exits or restarts repeatedly, inspect `docker logs --tail 100 xcancel` and check both tokens. A running container without a Slack connection is not ready to process messages.

## URL behavior

The app recognizes `http://` and `https://` URLs whose exact hostname is one of:

- `x.com`
- `www.x.com`
- `twitter.com`
- `www.twitter.com`

It changes only the hostname to `xcancel.com`, preserving the URL path, query string, and fragment. Surrounding punctuation is excluded, Slack-formatted links such as `<https://x.com/example/status/123|post>` are supported, and repeated URLs are listed once in their original order. Each link gets its own bold `X-Cancel Link:` label. Replies are posted in the source message's thread with link previews disabled.

Duplicate event delivery is guarded by a bounded, process-local cache keyed by Slack event ID. This is best-effort protection for one running process. The cache is cleared on restart, and an uncertain Slack API response can still result in a duplicate reply.

## Check the code

Run the unit tests and the same Ruff checks used for development:

```sh
.venv/bin/python -m pytest
.venv/bin/ruff check
.venv/bin/ruff format --check
```

## Manual acceptance check

1. Start the app and confirm Socket Mode connects successfully.
2. In a public or private channel where the bot is invited, post a message containing one X URL and one Twitter URL, optionally with surrounding text or punctuation.
3. Confirm that one thread reply appears with one bold `X-Cancel Link:` line per distinct URL, that each hostname is `xcancel.com`, and that no link preview is shown.
4. Post a reply in the thread and confirm it is handled in that thread. Edit a source message and confirm no new reply is created.
