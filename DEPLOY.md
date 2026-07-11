# Deploying pranera_knit

Commits included in this package:
- `8ab7f6b` Initial commit: yarn consumption tracking, custom fields, and fixes
- `95050c7` Remove dev-only vite proxy config, rebuild production assets
- `9f2852c` Fix CSRF failures on /knit-app routes: exclude from SW navigateFallback
- `57177cc` Scope the navigateFallback fix, warm CSRF globally for all pages

## 1. On your machine — push to GitHub

```bash
cd pranera_knit/frontend
npm install          # regenerate node_modules (excluded from this zip)
cd ..
git push origin main
```

## 2. On the production server — pull and deploy

```bash
cd ~/frappe-bench                      # adjust to your actual bench path
git -C apps/pranera_knit pull

bench build --app pranera_knit         # rebuilds frontend/public/knit_app
bench --site erp.pranera.in migrate
bench restart
```

> The repo already ships with the rebuilt `pranera_knit/public/knit_app/`
> assets committed, so `bench build` just regenerates the same output —
> safe either way.

## 3. Clear the stale service worker (do this once, yourself, before testing)

The knit app is a PWA. A service worker installed *before* commit `9f2852c`
will keep serving a broken cached shell indefinitely unless cleared:

1. Open `erp.pranera.in/knit-app` in Chrome
2. DevTools → **Application** tab → **Service Workers** → **Unregister**
3. Same tab → **Storage** → **Clear site data**
4. Hard refresh: `Ctrl+Shift+R` (`Cmd+Shift+R` on Mac)

For floor operators on other devices: a normal hard refresh is usually
enough, since `main.js` auto-unregisters old service workers on load. If
anyone stays stuck on a broken version, walk them through steps 1–4 once.

## 4. Verify

Open `erp.pranera.in/knit-app/production-report`, type into the Work Order
filter, and confirm `knit_report_filter_options` calls return `200` (not
`400`) in DevTools → Network.
