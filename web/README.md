# mario bench website

Next.js site for https://mario.nicholasg.com: 2 recorded model replays side by side, a playable World 1-1 and a sortable table of the published runs, in light and dark themes.

```sh
npm ci
npm run dev
```

## data

The page reads the 8 verified development examples in `../results/index.json` and plays their silent MP4 replays. These are selected runs with different prompts, cadence and image history, so the UI labels them as such and shows no averages, clear rates or costs. Failed runs have no clear time.

`npm run prepare-assets` (run automatically before `dev` and `build`) copies `../results/` into the ignored `public/benchmark-data/` folder and checks every replay, trace and profile hash. The page reads that copy at build time, so builds need the repository checkout but no Python or private experiment files. Every `*_href` in the index resolves under `/benchmark-data/`.

## human game

The browser game runs jsnes with sound disabled. Progress uses the calibrated World 1-1 mapping `(x - 40) / (3161 - 40)`, capped at 99.9% until the flag, and ignores positions from the death animation. Your best progress, attempts and clear time stay in `localStorage` (`mario-bench-human-v2`) and are kept apart from the model runs, since human play has no frame budget. Controls: left/right arrows move, up jumps, either Shift key runs; touch buttons appear on small or touch screens.

The game asset is prepared from the pinned gym-super-mario-bros 9.1.0 package, verifying package and asset SHA-256 checksums, and is ignored by Git. See `public/game/NOTICE.txt` and `THIRD_PARTY_NOTICES.md`.

## checks

```sh
npm run typecheck
npm run build
node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON scripts/check-game.mjs
BASE_URL=http://127.0.0.1:3112 npm run check:ui   # against a running dev or start server
```

`check:ui` drives headless, muted Chrome and writes screenshots to the ignored `screenshots/` folder.

Vercel project settings: root directory `web`, Node.js 24, framework Next.js. The root `.vercelignore` uploads only `web/` and `results/`. No environment variables or API keys are needed.
