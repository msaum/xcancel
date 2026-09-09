# XCancel Slack bot

![XCancel logo](assets/icon.png)

This Slack app watches public and private channels where it has been invited. When a person posts a message containing an X or Twitter URL, the app replies in the message thread with an `xcancel.com` link for each distinct matching URL.

For example, a message containing `https://x.com/example/status/123` receives this thread reply:

```text
*X-Cancel Link:* https://xcancel.com/example/status/123
```

The app uses Slack Socket Mode, so it can run locally without a public HTTP endpoint. It serves one Slack workspace and processes new human messages, including messages posted in existing threads. Message edits, deletion events, bot messages, and messages without matching URLs are ignored.

## Requirements

- Python 3
- A Slack workspace where you can install apps
- The Slack CLI, if you want to install or run the app through the CLI

## Install

Create and activate a virtual environment, then install the pinned dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The dependencies include `slack-cli-hooks`, which lets the same app run through the Slack CLI.

## Create and install the Slack app

### Using the Slack CLI

Run these commands from the project directory after completing the virtual environment setup above. The CLI hook uses `.venv/bin/python`, so the environment must exist at that path and contain the installed dependencies.

Sign in to the workspace where you want to install the bot:

```sh
slack login
slack auth list
```

If you are already authenticated, use `slack auth list` to find your workspace's team ID. For AI Systems Guild, the workspace name is `buildaisystems` and the team ID is `T1YQ7DT88`.

Install the app using this project's `manifest.json`, then verify its status:

```sh
slack app install --team T1YQ7DT88 --environment deployed
slack app list --team T1YQ7DT88
```

Replace `T1YQ7DT88` with the team ID from `slack auth list` when installing in another workspace. Follow any installation prompts. The verification command should show the app ID and `Status: Installed`.

The `deployed` option selects the app's CLI environment. Installation creates the Slack app and grants its permissions; the Python process must also be running for the bot to respond. Follow **Run the app** below and invite the bot to each public or private channel it should monitor with `/invite @xcancel`.

If installation reports `runtime_not_found` or a missing `slack_cli_hooks` module, confirm that `.venv/bin/python` exists and reinstall the dependencies with `.venv/bin/python -m pip install -r requirements.txt`.

### Using the Slack website

1. Open [Create New Slack App](https://api.slack.com/apps/new), choose **From an app manifest**, and select the workspace.
2. Paste the contents of [`manifest.json`](./manifest.json), review the configuration, and create the app.
3. In **OAuth & Permissions**, install the app to the workspace and copy the **Bot User OAuth Token**.
4. In **Basic Information**, create an app-level token with the `connections:write` scope and copy it.
5. Invite the bot to each public or private channel it should monitor with `/invite @xcancel`.

The manifest requests these bot permissions and event subscriptions:

- `channels:history` to receive public-channel messages
- `groups:history` to receive messages in private channels where the bot is invited
- `chat:write` to post thread replies
- `message.channels` for new public-channel message events
- `message.groups` for new private-channel message events

If the app was previously installed with the sample configuration, reinstall it after updating the manifest so the old sample scopes, commands, and event subscriptions are removed.

Set the two tokens in the shell where you will run the app:

```zsh
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_APP_TOKEN="xapp-your-app-token"
```

Keep these values out of source control and logs.

### Update an existing installation for private channels

Apply the updated manifest and grant the new `groups:history` permission by reinstalling the existing app:

```sh
slack app install --team T1YQ7DT88 --app A0C0RN0FJD8
```

Restart the bot process with the updated code. In AI Systems Guild, `#mods` is a private channel suitable for this check once the bot is invited. Private-channel messages are available only where the bot is a member. Direct messages and group DMs are ignored.

## Run the app

From the project directory, with the environment variables set, use either entry point:

```sh
# Slack CLI
slack run

# Directly from the virtual environment
.venv/bin/python app.py
```

The Slack CLI option uses the repository's CLI hooks. Stop the process with `Ctrl-C`.

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
