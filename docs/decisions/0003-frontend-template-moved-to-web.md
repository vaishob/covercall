# Decision 0003: Move the AI Studio React template under `web/`

- **Date:** 2026-10-18
- **PDF section:** §13.1 (repository layout), §11.1 (frontend stack)

## Context
The previous agent (Google AI Studio, React project template) left frontend files at the
repository root: `src/`, `index.html`, `package.json`, `tsconfig.json`, `vite.config.ts`,
`metadata.json` and `.env.example`. §13.1 puts the React app in `web/`. KICKSTART §2 says
`web/` stays empty until Slice 3, but a second agent (AI Studio) may continue the frontend.

## Decision
Move every template file under `web/` with `git mv` (history preserved). Nothing was deleted.
`.env.example` moved to `web/.env.example` because it only documents the AI Studio
runtime variables (`GEMINI_API_KEY`, `APP_URL`) with placeholder values.

## Alternatives
- Delete the template: `src/App.tsx` renders an empty `<div>`, so it is pure boilerplate.
  Rejected because the frontend agent may expect the AI Studio template config
  (`vite.config.ts` HMR switch, `metadata.json`), and a move is reversible.

## Note for the frontend agent
The template's `.env.example` holds a server-side `GEMINI_API_KEY`. §7.2 forbids any API key
reaching the browser; voice MUST use ephemeral tokens minted by `api`.
