# Enxoval — lista de presentes compartilhável

One gift registry (*enxoval*), served at the site root. Visitors don't make accounts: they
open the site, fill in their name and e-mail at the top, pick an item, and the owner gets an
e-mail and reaches out to work out the details.

**The whole interface is in Brazilian Portuguese.** Code, API paths and this file stay in
English so they're maintainable; everything a person reads — pages, validation messages,
notification e-mails, the Django admin — is Portuguese.

## How it works

- **Visitors** go to `/`. There is one list and no link to guess.
- **They fill in** *Nome*, *Sobrenome* and *E-mail* in the "Seus dados" card at the top.
  Until all three are filled in with a valid e-mail, "Vou comprar este" does nothing but
  scroll back up, flag the empty fields and focus the first one. The server enforces the
  same rule, so the check can't be skipped by calling the API directly.
- **Their details are remembered** in the browser, so claiming a second item takes one click.
- **You** sign in at `/gestao-enxoval` — a separate address that the public page never links
  to — and manage everything at `/gestao-enxoval/painel`.
- **You get an e-mail** for every reservation, and it shows up under "Quem vai comprar" with
  a status you move along: *Aguardando contato → Contato feito → Recebido*.
- Items needing more than one can be reserved by several people until the count is filled.

### Changing the owner's address

It's one line — [`frontend/src/config.js`](frontend/src/config.js):

```js
export const ADMIN_PATH = '/gestao-enxoval'
```

Change it, rebuild the frontend, and both the sign-in page and the panel move with it. It
keeps the login out of a visitor's way; it is not a security boundary — the password is.

## Running it locally

One-time setup:

```bash
cd enxoval
python3 -m venv .venv
./.venv/bin/pip install -r backend/requirements.txt
./.venv/bin/python backend/manage.py migrate
./.venv/bin/python backend/manage.py seed_demo     # demo account + sample enxoval
cd frontend && npm install && cd ..
```

Then every time:

```bash
./dev.sh          # Django on :8000, React on :5173
```

- **http://localhost:5173** — the public page, what everyone sees.
- **http://localhost:5173/gestao-enxoval** — sign in as `owner` / `registry123`.

Reservation e-mails print to the terminal running `dev.sh` unless SMTP is configured.

To make your own account instead of the demo one:

```bash
./.venv/bin/python backend/manage.py createsuperuser
```

The first account to open the panel gets the enxoval; it's created automatically, so a fresh
account is never an error page. If more than one account exists, the public page always shows
the enxoval that was created first — unchecking "Página no ar" takes the site down rather than
promoting someone else's list to the root.

### Running the tests

```bash
./.venv/bin/python backend/manage.py test registry
```

The suite covers the boundary between the two audiences: what a visitor can do, what they must
supply before they can reserve anything, what they must never see, and what one account can
reach of another's.

### Running it the way production runs it

The React app can also be built into static files that Django serves, so the whole thing is
one process on one port:

```bash
cd frontend && npm run build && cd ..
./.venv/bin/python backend/manage.py runserver 8000   # everything on :8000
```

## Deploying

Pushing to `main` runs the tests, builds a Docker image, pushes it to GitHub Container
Registry, and releases it on the VM. A release that does not come up healthy rolls itself back.

```
push to main
  └─ Deploy workflow
       ├─ CI ............ tests, lint, migration check, --deploy check, image build
       ├─ build ......... push ghcr.io/<you>/enxoval:<sha> and :latest
       └─ deploy ........ ssh VM → /opt/enxoval/release.sh <sha>
                            ├─ pg_dump first
                            ├─ pull, migrate, start
                            ├─ wait for /healthz
                            └─ unhealthy? → roll back to the previous tag
```

### What lives where

| File | Runs |
| --- | --- |
| `.github/workflows/ci.yml` | On pull requests, and called by Deploy |
| `.github/workflows/deploy.yml` | On push to `main`, or manually for a rollback |
| `deploy/docker-compose.prod.yml` | On the VM: Caddy + gunicorn + Postgres |
| `deploy/Caddyfile` | On the VM: TLS and reverse proxy |
| `deploy/release.sh` | On the VM, by the deploy job |
| `deploy/backup.sh` | On the VM, by `release.sh` and a nightly cron |
| `deploy/bootstrap-vm.sh` | Once, by hand, on a fresh VM |

### Setting up the Google Cloud VM

An `e2-small` (2 GB) running Debian 12 is plenty — the VM only runs the image, it never
builds it. `e2-micro` also works but leaves little headroom for Postgres.

1. **Create the VM** with HTTP and HTTPS traffic allowed, and give it a **static external
   IP** (otherwise it changes on restart and breaks DNS).

2. **Point `enxoval-do-moroni.com` at it.** The domain is on Cloudflare, so in the
   Cloudflare dashboard → DNS:

   | Type | Name | Content | Proxy status |
   | --- | --- | --- | --- |
   | `A` | `@` | the VM's static IP | **DNS only** (grey cloud) |
   | `A` | `www` | the VM's static IP | **DNS only** (grey cloud) |

   **The grey cloud matters.** With the orange cloud on, Cloudflare terminates TLS itself and
   every visitor reaches Caddy from a Cloudflare address — which collapses the claim rate
   limit into one shared bucket for the whole site. Switching it on later means setting
   `DJANGO_NUM_PROXIES=2` and reading the client IP from `CF-Connecting-IP` in the Caddyfile.

   Also set Cloudflare's SSL/TLS mode to **Full (strict)**. The default "Flexible" would talk
   to the VM over plain http and loop against Django's https redirect.

   Wait for it to resolve before going further — Caddy cannot get a certificate until it does:

   ```bash
   dig +short A enxoval-do-moroni.com     # should print the VM's IP, not a Cloudflare one
   ```

   `www` redirects to the bare domain, so there is one canonical address.

3. **Bootstrap it** — installs Docker, creates `/opt/enxoval`, adds the nightly backup cron:

   ```bash
   gcloud compute ssh enxoval-vm
   # copy deploy/bootstrap-vm.sh up, then:
   sudo bash bootstrap-vm.sh "$USER"
   ```

   Log out and back in afterwards, so your new `docker` group membership applies.

4. **Copy the deploy files** into `/opt/enxoval/`:

   ```bash
   gcloud compute scp deploy/docker-compose.prod.yml deploy/Caddyfile \
       deploy/release.sh deploy/backup.sh enxoval-vm:/opt/enxoval/
   gcloud compute ssh enxoval-vm --command 'chmod +x /opt/enxoval/*.sh'
   ```

5. **Write `/opt/enxoval/.env`** from [`deploy/env.example`](deploy/env.example). Generate the
   two secrets with `openssl rand -base64 48`.

6. **Log in to GHCR once on the VM**, so it can pull the image:

   ```bash
   docker login ghcr.io -u <github-user>
   ```

   Use a [fine-grained token](https://github.com/settings/tokens) with only `read:packages`.
   It is stored in `~/.docker/config.json`, so deploys never carry a token.

7. **First release, and the owner account:**

   ```bash
   /opt/enxoval/release.sh latest
   cd /opt/enxoval && docker compose -f docker-compose.prod.yml \
     exec web python manage.py createsuperuser
   ```

### GitHub secrets the deploy needs

Repo → Settings → Secrets and variables → Actions:

| Secret | What it is |
| --- | --- |
| `VM_HOST` | The VM's static external IP |
| `VM_USER` | The Linux user you bootstrapped |
| `VM_SSH_KEY` | A private key whose public half is in that user's `~/.ssh/authorized_keys` |
| `VM_SSH_KNOWN_HOSTS` | Output of `ssh-keyscan <vm-ip>` |

`VM_SSH_KNOWN_HOSTS` is not optional padding: without a pinned host key the deploy would
hand the VM's credentials to anything that can answer on that address.

Generate a deploy-only key rather than reusing your own:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/enxoval-deploy -C "github-actions" -N ""
gcloud compute ssh enxoval-vm --command \
  "echo '$(cat ~/.ssh/enxoval-deploy.pub)' >> ~/.ssh/authorized_keys"
ssh-keyscan <vm-ip>          # → VM_SSH_KNOWN_HOSTS
cat ~/.ssh/enxoval-deploy    # → VM_SSH_KEY
```

### Rolling back

Actions → Deploy → Run workflow, and give it an earlier image tag (a commit SHA). It skips
the build and releases that tag.

One honest caveat: a rollback restores the **code**, not the **schema**. If the bad release
applied a migration, that migration is still applied. `release.sh` takes a `pg_dump` before
every deploy for exactly this case — they are in `/opt/enxoval/backups/`, newest 30 kept,
plus a nightly dump at 03:20.

### Operating it

```bash
cd /opt/enxoval
docker compose -f docker-compose.prod.yml logs -f web     # follow the app
docker compose -f docker-compose.prod.yml ps              # what is running
./backup.sh                                               # dump on demand
curl https://<your-domain>/healthz                         # app + database check

# restore a dump into a running stack
gunzip -c backups/enxoval-<stamp>.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U enxoval -d enxoval
```

The `caddy_data` volume holds the TLS certificates. Deleting it means re-issuing them, and
Let's Encrypt rate-limits that — leave it alone.

### Somewhere other than a VM

`render.yaml` still works if you ever want a managed host instead: push to GitHub, then
New → Blueprint on Render. It provisions Postgres and wires up `DATABASE_URL` itself.

Container environment variables, wherever it runs:

| Variable | Needed? | Notes |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | yes | Long random string. |
| `DJANGO_DEBUG` | yes | `False` in production. |
| `DJANGO_ALLOWED_HOSTS` | yes | Your domain, comma separated. Render/Railway/Fly are auto-detected. |
| `DATABASE_URL` | recommended | Postgres URL. Falls back to SQLite, which most hosts wipe on redeploy. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | for emails | Without `EMAIL_HOST`, notification e-mails print to the server log instead of sending. Reservations are still saved either way. |
| `DJANGO_TIME_ZONE` | no | Defaults to `America/Sao_Paulo`. |
| `DJANGO_HSTS_SECONDS` | no | HTTPS is forced and remembered for a year by default. Set to `0` if the domain must also answer over plain http. |

To try the production setup on your machine: `docker compose up --build` → http://localhost:8000.

### Gmail as the mail sender

Gmail rejects your normal password. Turn on 2-step verification, create an
[App Password](https://myaccount.google.com/apppasswords), and use that as
`EMAIL_HOST_PASSWORD` with `EMAIL_HOST=smtp.gmail.com` and `EMAIL_PORT=587`.

## Layout

```
backend/
  config/settings.py    env-driven settings (SQLite → Postgres is one variable)
  registry/models.py    Registry (one, via Registry.load()), Item, Claim
  registry/views.py     public endpoints + owner-only CRUD
frontend/src/
  config.js             where the owner's area lives
  api.js                fetch wrapper, JWT storage, silent token refresh
  pages/PublicRegistry  the page everyone sees, with the "Seus dados" gate
  pages/RegistryEditor  items, reservations and settings
.github/workflows/
  ci.yml                pull-request checks, reused by the deploy
  deploy.yml            build → push to GHCR → release on the VM
deploy/                 everything that lives on the VM
```

## API

Public, no authentication:

| Method | Path |
| --- | --- |
| `GET` | `/api/public/` |
| `POST` | `/api/public/items/<id>/claim/` — requires `first_name`, `last_name`, `email` |

Owner-only, `Authorization: Bearer <token>` from `POST /api/auth/login/`:
`/api/registry/` (GET and PATCH only — there is no second enxoval to create or delete),
`/api/items/`, `/api/claims/`.

Django's own admin is at `/admin/` if you ever want to edit data directly.

## Notes on the design

- Reservations are rate limited to 20/hour per IP. Two things make that number real: the
  count lives in a shared database cache, so gunicorn's workers do not each keep their own,
  and `NUM_PROXIES` pins which `X-Forwarded-For` entry identifies the visitor, so a forged
  header cannot buy a fresh allowance. Both are covered by tests.
- Name, surname and a valid e-mail are required by the server, not just the form.
- The public API never exposes who reserved what — visitors only see counts.
- Reserving locks the item row, so two people clicking at the same moment can't over-reserve.
- Deleting an item deletes its reservations; the UI warns you first with the count.
- If the notification e-mail fails to send, the reservation is still saved and shown in the
  panel — an SMTP outage never loses one.
