# mario bench website

Next.js website for https://mario.nicholasg.com, using Geist, warm light/dark themes and a browser-local World 1-1 game.

```sh
npm ci
npm run dev
```

The two model replays and benchmark results are currently illustrative. Personal best scores and attempt counts are saved in the browser, with zero user cost. Controls: left/right arrows move, up jumps, either Shift key runs.

The build and dev scripts prepare the game asset from the pinned gym-super-mario-bros 9.1.0 package, verifying both package and asset SHA-256 checksums. Game data is generated under public/game and ignored by Git. See public/game/NOTICE.txt and THIRD_PARTY_NOTICES.md.

```sh
npm run build
npm run typecheck
node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON scripts/check-game.mjs
```

Vercel project settings: repository root directory `web`, Node.js 24, framework Next.js. The production domain is `mario.nicholasg.com`. No environment variables or model API keys are required by this website.
