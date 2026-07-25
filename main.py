name: Crypto Signal Bot

on:
  schedule:
    # Every 5 minutes. GitHub may delay this under load (sometimes 10-15 min) — that's a
    # platform limit of the free scheduler, not something we can fix from the workflow side.
    - cron: "*/5 * * * *"
  workflow_dispatch: {}   # lets you trigger a manual run/test from the GitHub app

permissions:
  contents: write   # needed so the workflow can commit updated state.json back to the repo

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run signal bot
        env:
          EMAIL_ADDRESS: ${{ secrets.EMAIL_ADDRESS }}
          EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
          CALLMEBOT_APIKEY: ${{ secrets.CALLMEBOT_APIKEY }}
          WHATSAPP_PHONE: ${{ secrets.WHATSAPP_PHONE }}
          BUY_ALERT_THRESHOLD: "70"
          SELL_ALERT_THRESHOLD: "70"
          COOLDOWN_MINUTES: "60"
          TOP_MOVERS_COUNT: "8"
        run: python main.py

      - name: Persist alert state and dashboard
        run: |
          git config user.name "crypto-signal-bot"
          git config user.email "actions@github.com"
          git add state.json docs/
          git diff --cached --quiet || git commit -m "chore: update alert state + dashboard [skip ci]"
          git push
