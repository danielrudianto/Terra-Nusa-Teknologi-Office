# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Bun + Elysia.js financial and HR management system for Terra Nusa Teknologi (TNT). Core domains: purchases, payments, expenses, sales invoices, salary slips, employee records, attendance, and bank account management. Migrated from Python + FastAPI.

## Running the Application

```bash
bun install
bun run dev          # runs on port 7500 with --watch
bun run start        # production
```

**First-time setup** (requires MySQL, Meilisearch, and Redis running):
```bash
bunx prisma db pull         # sync schema from existing DB
bunx prisma generate        # regenerate TypeScript client
```

## Architecture

**MVC + Repository pattern:**
- `src/routes/` — Elysia route groups, one file per domain
- `src/controllers/` — business logic and orchestration
- `src/repository/` — Prisma-based data access (static async methods)
- `src/utils/` — database, auth, meilisearch, redis, logger, guard, pagination

**Entry point:** `src/index.ts` — Elysia app with CORS, startup hooks (Prisma, Meilisearch, Redis), all routes registered here.

**Auth guard:** `src/utils/guard.ts` — Elysia `derive` plugin that decodes the Bearer token and injects `user` into route context. Every protected route checks `if (!user) return set.status = 401`.

**External services** (all expected at localhost):
- MySQL — `DATABASE_URL` in `.env` (format: `mysql://user:pass@localhost/tnt`)
- Meilisearch on `:7700` — supplier full-text search
- Redis on `:6379` — bank account caching

## Key Patterns

**Soft delete everywhere:** All tables use `isDelete` (Boolean or TinyInt) and `deletedAt`/`deletedBy`. Always filter with `isDelete: false` (or `isDelete: 0` for TinyInt tables like `income`, `purchase_draft`, `payment_incoming`).

**TinyInt vs Boolean:** Some older tables store booleans as `Int @db.TinyInt` (0/1) instead of MySQL BOOLEAN. Check the Prisma schema for the actual type before querying.

**Auth flow:** JWT tokens — access token (12h), refresh token (7 days). Tokens use `SECRET_KEY` and `ALGORITHM` from `.env`. `decodeToken()` in `src/utils/auth.ts` returns `null` on invalid/expired tokens.

**Pagination:** All list endpoints accept `page`, `pageSize`, `sortBy`, `sortByDirection` query params. Use `paginationParams()` and `paginationMeta()` from `src/utils/pagination.ts`.

**Error responses:** Route handlers return `{ detail: "..." }` on error with `set.status` set. Controllers return `{ error: "...", status: N }` — routes unpack these into HTTP responses.

**Decimal fields:** Financial amounts in the DB are `Decimal` type (MySQL DECIMAL). Prisma returns them as `Prisma.Decimal` objects — convert to number with `.toNumber()` before returning in JSON if needed.

**Calendar route:** Uses `prisma.$queryRaw` with `Prisma.join()` for complex multi-table joins and the `mutation` MySQL view (balance tracking). The mutation view is NOT in the Prisma schema — access only via raw queries. If `mutation` view doesn't exist the balance query fails silently and returns 0.

**bankAccounts filter:** The `/calendar` endpoints accept `bankAccounts` as a comma-separated string (e.g. `?bankAccounts=1,2,3`). Empty/absent means no filter (all accounts).

## Route Modules

All prefixes registered in `src/index.ts`:
- `/auth` — login, refresh token
- `/clients`, `/suppliers` — client and supplier CRUD
- `/employees` — employee records
- `/banks` — bank accounts (with Redis caching)
- `/assets`, `/expense-opponents`, `/income`
- `/loans`, `/interpayments`
- `/purchases`, `/purchase-orders`, `/purchase-draft`
- `/expenses`, `/reimbursements`
- `/sales-invoices`
- `/outgoing-payments`, `/incoming-payments`
- `/salary-slips`
- `/taxes` — PPH/PPN reporting endpoints
- `/calendar` — Monthly summary, daily detail, and download/export; aggregates from payment_outgoing, payment_incoming, interpayments, and the `mutation` MySQL view
- `/attendance` — Employee attendance CRUD with month/date/employee filtering

## Database Schema

Schema in `prisma/schema.prisma` is generated from the actual DB via `bunx prisma db pull`. If you add a column via SQL migration, re-run `prisma db pull` then `prisma generate` to update TypeScript types.

**Audit trail** on most tables: `createdAt`, `createdBy`, `updatedAt`, `updatedBy`, `deletedAt`, `deletedBy`, `isDelete`.

## Indonesian Locale Specifics

- Employee tax categories: `TK/0`, `TK/1`, `TK/2`, `TK/3`, `K/0`, `K/1`, `K/2`, `K/3`
- Meilisearch has Indonesian location/equipment synonyms configured in `src/utils/meilisearch.ts`
- Currency is IDR — Decimal precision matters for financial calculations

## Environment

`.env` file (gitignored) — required variables:
```
DATABASE_URL=mysql://user:pass@localhost/tnt
SECRET_KEY=...
ALGORITHM=HS256
MEILISEARCH_MASTER_KEY=...
```

## Logging

Use `logInfo()`, `logWarning()`, `logError()` from `src/utils/logger.ts`. Color-coded console output.
