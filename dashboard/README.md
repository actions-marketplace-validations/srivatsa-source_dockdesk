# DockDesk Dashboard

Interactive React dashboard for visualizing DockDesk audit history, risk trends, and model usage.

## Quick Start

```bash
cd dashboard
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

## Using Real Data

1. Run audits with DockDesk in your project
2. Export data for the dashboard:
   ```bash
   python auditor_slm.py dashboard --export dashboard/public/dashboard_data.json
   ```
3. Refresh the dashboard

## Building for Production

```bash
npm run build
```

The static files will be in `dist/` - deploy to any static host.

## Deploying to Vercel

1. Push to GitHub
2. Connect repository to Vercel
3. Set build command: `npm run build`
4. Set output directory: `dist`
5. Deploy!

Or use Vercel CLI:
```bash
npm i -g vercel
vercel
```

## Features

- **Stats Cards**: Total audits, files, fixes, average duration
- **Audit Timeline**: Pass/fail/fix trends over time
- **Risk Distribution**: HIGH/MEDIUM/LOW pie chart
- **Model Usage**: Which models are used most
- **Recent Runs**: Latest audit details with git branch info
