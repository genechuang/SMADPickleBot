# Claude Code Project Instructions

## Environment

- **Operating System**: Windows 11
- **Shell**: PowerShell (NOT bash/sh)
- **Timezone**: America/Los_Angeles (PST/PDT)

## Important Rules

1. **Scripts**: Always create PowerShell scripts (`.ps1`), never bash scripts (`.sh`)
2. **Commands**: Use PowerShell syntax, not bash/Linux commands
3. **Git commits**: Always ask for permission before running `git commit` and `git push`
4. **Timestamps**: Use PST timezone, never UTC

## Project Overview

SMAD PickleBot - Automation for SMAD Pickleball group:
- Court booking automation (Athenaeum)
- WhatsApp poll creation and vote tracking
- Payment reminders via WhatsApp
- Google Sheets integration for player management

## Key Technologies

- Python 3.11
- Google Cloud Platform (project: smad-pickleball, region: us-west1)
- GitHub Actions for CI/CD
- Google Cloud Scheduler for reliable cron jobs
- GREEN-API for WhatsApp messaging
- Google Sheets API
