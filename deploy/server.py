"""
Design Forge — Static File Server + API
Serves all generated landings from /design_forge/generated/
Each landing: /l/{slug}/

API endpoints:
  POST   /api/generate              {"description": "...", "theme": "telegraph"} → {"url": "...", "slug": "..."}
  GET    /api/list                                                                 → [{"url":"...", "slug":"..."}]
  GET    /api/stats/{slug}                                                         → {"views": N, "slug": "..."}
  DELETE /api/slug/{slug}                                                          → {"ok": true}
  POST   /api/slug/{slug}/rename    {"new_slug": "..."}                           → {"url": "...", "slug": "..."}
  POST   /api/slug/{slug}/duplicate                                                → {"url": "...", "slug": "..."}
  GET    /api/content/{slug}                                                       → content JSON
  POST   /api/content/{slug}        {field: value, ...}                           → {"ok": true}
  POST   /api/bulk                  {"action": "archive|delete", "slugs": [...]}  → {"ok": true}
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
import http.server
import socketserver
import urllib.parse
import threading
import subprocess
import tempfile

GENERATED_DIR = os.path.join(os.path.dirname(__file__), "..", "generated")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "forge.db")
PORT = int(os.environ.get("FORGE_PORT", 9883))

_db_lock = threading.Lock()


ADMIN_TOKEN = os.environ.get("FORGE_ADMIN_TOKEN", "a7x9k2forge2026")


def _get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            hash TEXT PRIMARY KEY,
            content_json TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS views (
            slug TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0,
            last_seen INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            slug TEXT PRIMARY KEY,
            label TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'live',
            updated_at INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def _generate_hero_image_async(content: dict, description: str) -> str:
    """Generate hero image via Pollinations AI (free, no key). Returns URL or empty string."""
    try:
        import urllib.parse
        name = content.get("product_name", "product")
        accent = content.get("color_accent", "#6C63FF")
        prompt = (
            f"Minimalist tech product hero image for {name}. "
            f"Dark background, accent color {accent}, abstract geometric shapes, "
            f"glowing neon elements, professional landing page aesthetic, no text, no UI mockups"
        )
        encoded = urllib.parse.quote(prompt)
        seed = abs(hash(name)) % 99999
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1200&height=630&nologo=true&seed={seed}"
        )
        # Verify image is accessible (quick HEAD check)
        result = subprocess.run(
            ["curl", "-s", "--max-time", "20", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=25
        )
        if result.stdout.strip() == "200":
            return url
        return ""
    except Exception:
        return ""


def meta_get(slug: str) -> dict:
    with _db_lock:
        conn = _get_db()
        row = conn.execute("SELECT label, status FROM meta WHERE slug=?", (slug,)).fetchone()
        conn.close()
    if row:
        return {"label": row[0], "status": row[1]}
    return {"label": "", "status": "live"}


def meta_set(slug: str, label: str = None, status: str = None):
    current = meta_get(slug)
    new_label = label if label is not None else current["label"]
    new_status = status if status is not None else current["status"]
    with _db_lock:
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO meta (slug, label, status, updated_at) VALUES (?,?,?,?)",
            (slug, new_label, new_status, int(time.time()))
        )
        conn.commit()
        conn.close()


def cache_get(description: str, theme: str):
    key = hashlib.sha256(f"{description}|{theme}".encode()).hexdigest()
    ttl = 7 * 86400
    with _db_lock:
        conn = _get_db()
        row = conn.execute("SELECT content_json, created_at FROM cache WHERE hash=?", (key,)).fetchone()
        conn.close()
    if row and (time.time() - row[1]) < ttl:
        return json.loads(row[0])
    return None


def cache_set(description: str, theme: str, content: dict):
    key = hashlib.sha256(f"{description}|{theme}".encode()).hexdigest()
    with _db_lock:
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO cache (hash, content_json, created_at) VALUES (?,?,?)",
            (key, json.dumps(content, ensure_ascii=False), int(time.time()))
        )
        conn.commit()
        conn.close()


def views_increment(slug: str):
    with _db_lock:
        conn = _get_db()
        conn.execute(
            "INSERT INTO views (slug, count, last_seen) VALUES (?,1,?) "
            "ON CONFLICT(slug) DO UPDATE SET count=count+1, last_seen=?",
            (slug, int(time.time()), int(time.time()))
        )
        conn.commit()
        conn.close()


def views_get(slug: str) -> int:
    with _db_lock:
        conn = _get_db()
        row = conn.execute("SELECT count FROM views WHERE slug=?", (slug,)).fetchone()
        conn.close()
    return row[0] if row else 0


class ForgeHandler(http.server.BaseHTTPRequestHandler):

    def _send_json(self, code: int, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, x-api-key")
        self.end_headers()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/slug/"):
            slug = path[len("/api/slug/"):].strip("/")
            self._handle_delete(slug)
        else:
            self._send_json(404, {"error": "not found"})

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        self.send_response(405)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/health"):
            self._send_json(200, {"status": "ok", "service": "Design Forge"})
            return

        if path == "/api/list":
            self._handle_list()
            return

        if path.startswith("/api/stats/"):
            slug = path[len("/api/stats/"):].strip("/")
            self._send_json(200, {"slug": slug, "views": views_get(slug)})
            return

        if path.startswith("/api/content/"):
            slug = path[len("/api/content/"):].strip("/")
            self._handle_content_get(slug)
            return

        if path.startswith("/api/export/"):
            slug = path[len("/api/export/"):].strip("/")
            self._handle_export(slug)
            return

        if path.startswith("/api/meta/"):
            slug = path[len("/api/meta/"):].strip("/")
            self._send_json(200, {"slug": slug, **meta_get(slug)})
            return

        if path.startswith("/api/leads/"):
            slug = path[len("/api/leads/"):].strip("/")
            self._handle_leads_get(slug)
            return

        if path.startswith("/admin/"):
            token = path[len("/admin/"):].strip("/")
            if token == ADMIN_TOKEN:
                self._serve_admin()
            else:
                self._send_json(403, {"error": "forbidden"})
            return

        if path.startswith("/l/"):
            self._serve_landing(path)
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/generate":
            self._handle_generate()
        elif path == "/api/bulk":
            self._handle_bulk()
        elif path.startswith("/api/slug/") and path.endswith("/rename"):
            slug = path[len("/api/slug/"):-len("/rename")].strip("/")
            self._handle_rename(slug)
        elif path.startswith("/api/slug/") and path.endswith("/duplicate"):
            slug = path[len("/api/slug/"):-len("/duplicate")].strip("/")
            self._handle_duplicate(slug)
        elif path.startswith("/api/meta/"):
            slug = path[len("/api/meta/"):].strip("/")
            self._handle_meta_update(slug)
        elif path.startswith("/api/content/"):
            slug = path[len("/api/content/"):].strip("/")
            self._handle_content_update(slug)
        elif path.startswith("/api/leads/"):
            slug = path[len("/api/leads/"):].strip("/")
            self._handle_leads_post(slug)
        else:
            self._send_json(404, {"error": "not found"})

    def _serve_landing(self, url_path: str):
        rel = url_path[3:]
        if not rel or rel == "/":
            self._send_json(404, {"error": "no slug"})
            return
        full_path = os.path.normpath(os.path.join(GENERATED_DIR, rel))
        if not full_path.startswith(os.path.realpath(GENERATED_DIR)):
            self._send_json(403, {"error": "forbidden"})
            return
        if os.path.isdir(full_path):
            full_path = os.path.join(full_path, "index.html")
        if os.path.isfile(full_path):
            slug = rel.strip("/").split("/")[0]
            views_increment(slug)
            with open(full_path, "rb") as f:
                self._send_html(200, f.read())
        else:
            self._send_json(404, {"error": "landing not found"})

    def _handle_generate(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._send_json(400, {"error": "invalid JSON body"})
            return

        description = body.get("description", "").strip()
        theme = body.get("theme", "telegraph")
        use_cache = body.get("cache", True)

        if not description:
            self._send_json(400, {"error": "description is required"})
            return

        content = cache_get(description, theme) if use_cache else None

        if content is None:
            # Load .env
            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ.setdefault(k.strip(), v.strip())

            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from generator.ai_generator import generate_content
            try:
                content = generate_content(description)
            except Exception as e:
                self._send_json(500, {"error": str(e)})
                return
            if use_cache:
                cache_set(description, theme, content)

        # Step 2.5: Generate hero image via Gemini (async, non-blocking)
        hero_image_url = _generate_hero_image_async(content, description)
        if hero_image_url:
            content["hero_image_url"] = hero_image_url

        from generator.template_engine import render
        html = render(content, theme=theme)

        import re
        slug_base = re.sub(r"[^\w\s-]", "", content.get("product_name", "product").lower())
        slug_base = re.sub(r"[\s_]+", "-", slug_base)[:30].strip("-")
        slug = f"{slug_base}-{time.strftime('%m%d-%H%M')}"

        # Inject slug for email form
        html = html.replace("window._forge_slug || 'unknown'", f"'{slug}'")
        if "window._forge_slug" not in html:
            html = html.replace("</body>", f"<script>window._forge_slug='{slug}';</script>\n</body>", 1)

        landing_dir = os.path.join(GENERATED_DIR, slug)
        os.makedirs(landing_dir, exist_ok=True)

        with open(os.path.join(landing_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

        content["_theme"] = theme
        with open(os.path.join(landing_dir, "content.json"), "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)

        url = f"https://forge.v2app.ru/l/{slug}/"
        self._send_json(200, {
            "url": url,
            "slug": slug,
            "product_name": content.get("product_name"),
            "hero_image": hero_image_url or None,
        })

    def _handle_delete(self, slug: str):
        import shutil
        if not slug or "/" in slug or ".." in slug:
            self._send_json(400, {"error": "invalid slug"})
            return
        landing_dir = os.path.normpath(os.path.join(GENERATED_DIR, slug))
        if not landing_dir.startswith(os.path.realpath(GENERATED_DIR)):
            self._send_json(403, {"error": "forbidden"})
            return
        if not os.path.isdir(landing_dir):
            self._send_json(404, {"error": "slug not found"})
            return
        shutil.rmtree(landing_dir)
        with _db_lock:
            conn = _get_db()
            conn.execute("DELETE FROM views WHERE slug=?", (slug,))
            conn.commit()
            conn.close()
        self._send_json(200, {"ok": True, "deleted": slug})

    def _handle_rename(self, slug: str):
        if not slug or "/" in slug or ".." in slug:
            self._send_json(400, {"error": "invalid slug"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        new_slug = body.get("new_slug", "").strip().lower()
        import re
        new_slug = re.sub(r"[^\w-]", "-", new_slug)[:60].strip("-")
        if not new_slug:
            self._send_json(400, {"error": "new_slug is required"})
            return
        src = os.path.normpath(os.path.join(GENERATED_DIR, slug))
        dst = os.path.normpath(os.path.join(GENERATED_DIR, new_slug))
        real_base = os.path.realpath(GENERATED_DIR)
        if not src.startswith(real_base) or not dst.startswith(real_base):
            self._send_json(403, {"error": "forbidden"})
            return
        if not os.path.isdir(src):
            self._send_json(404, {"error": "slug not found"})
            return
        if os.path.exists(dst):
            self._send_json(409, {"error": "new_slug already exists"})
            return
        os.rename(src, dst)
        with _db_lock:
            conn = _get_db()
            conn.execute("UPDATE views SET slug=? WHERE slug=?", (new_slug, slug))
            conn.commit()
            conn.close()
        url = f"https://forge.v2app.ru/l/{new_slug}/"
        self._send_json(200, {"ok": True, "slug": new_slug, "url": url})

    def _handle_meta_update(self, slug: str):
        if not slug or "/" in slug or ".." in slug:
            self._send_json(400, {"error": "invalid slug"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        label = body.get("label")
        status = body.get("status")
        if status and status not in ("live", "archive"):
            self._send_json(400, {"error": "status must be live or archive"})
            return
        meta_set(slug, label=label, status=status)
        self._send_json(200, {"ok": True, "slug": slug, **meta_get(slug)})

    def _serve_admin(self):
        admin_path = os.path.join(os.path.dirname(__file__), "..", "admin.html")
        if os.path.isfile(admin_path):
            with open(admin_path, "rb") as f:
                self._send_html(200, f.read())
        else:
            self._send_json(404, {"error": "admin.html not found"})

    def _handle_list(self):
        if not os.path.isdir(GENERATED_DIR):
            self._send_json(200, [])
            return
        result = []
        for slug in sorted(os.listdir(GENERATED_DIR)):
            idx = os.path.join(GENERATED_DIR, slug, "index.html")
            if os.path.isfile(idx):
                m = meta_get(slug)
                # Get product name from content.json if available
                product_name = slug
                content_path = os.path.join(GENERATED_DIR, slug, "content.json")
                theme = None
                if os.path.isfile(content_path):
                    try:
                        with open(content_path) as cf:
                            c = json.load(cf)
                            product_name = c.get("product_name", slug)
                            theme = c.get("_theme")
                    except Exception:
                        pass
                result.append({
                    "slug": slug,
                    "url": f"https://forge.v2app.ru/l/{slug}/",
                    "views": views_get(slug),
                    "created": int(os.path.getmtime(idx)),
                    "label": m["label"],
                    "status": m["status"],
                    "product_name": product_name,
                    "theme": theme,
                })
        result.sort(key=lambda x: x["created"], reverse=True)
        self._send_json(200, result)

    def _handle_content_get(self, slug: str):
        if not slug or "/" in slug or ".." in slug:
            self._send_json(400, {"error": "invalid slug"})
            return
        content_path = os.path.normpath(os.path.join(GENERATED_DIR, slug, "content.json"))
        if not content_path.startswith(os.path.realpath(GENERATED_DIR)):
            self._send_json(403, {"error": "forbidden"})
            return
        if not os.path.isfile(content_path):
            self._send_json(404, {"error": "content.json not found"})
            return
        try:
            with open(content_path, encoding="utf-8") as f:
                content = json.load(f)
            self._send_json(200, {"slug": slug, "content": content})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_content_update(self, slug: str):
        if not slug or "/" in slug or ".." in slug:
            self._send_json(400, {"error": "invalid slug"})
            return
        content_path = os.path.normpath(os.path.join(GENERATED_DIR, slug, "content.json"))
        idx_path = os.path.normpath(os.path.join(GENERATED_DIR, slug, "index.html"))
        real_base = os.path.realpath(GENERATED_DIR)
        if not content_path.startswith(real_base):
            self._send_json(403, {"error": "forbidden"})
            return
        if not os.path.isfile(content_path):
            self._send_json(404, {"error": "content.json not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            updates = json.loads(self.rfile.read(length))
        except Exception:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        try:
            with open(content_path, encoding="utf-8") as f:
                content = json.load(f)
            # Only update allowed top-level fields (not nested objects to prevent corruption)
            EDITABLE = {
                "product_name", "tagline_line1", "tagline_line2", "subtitle",
                "badge", "install_command", "install_title", "install_subtitle",
                "cta_primary", "cta_secondary", "problem_title", "problem_subtitle",
                "with_title", "with_desc", "without_title", "without_desc",
                "how_title", "how_subtitle", "features_title", "features_subtitle",
                "investor_title", "investor_subtitle", "color_accent", "color_accent2",
            }
            for k, v in updates.items():
                if k in EDITABLE and isinstance(v, str):
                    content[k] = v
                    # Mirror to ru block if key is text (not color)
                    if not k.startswith("color") and "ru" in content and k in content.get("ru", {}):
                        pass  # don't auto-update ru — user can do it separately
            with open(content_path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            # Re-render HTML
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from generator.template_engine import render
            theme = content.get("_theme", "octopus" if "octopus" in slug else "telegraph")
            html = render(content, theme=theme)
            with open(idx_path, "w", encoding="utf-8") as f:
                f.write(html)
            self._send_json(200, {"ok": True, "slug": slug})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_duplicate(self, slug: str):
        import shutil
        if not slug or "/" in slug or ".." in slug:
            self._send_json(400, {"error": "invalid slug"})
            return
        src = os.path.normpath(os.path.join(GENERATED_DIR, slug))
        real_base = os.path.realpath(GENERATED_DIR)
        if not src.startswith(real_base):
            self._send_json(403, {"error": "forbidden"})
            return
        if not os.path.isdir(src):
            self._send_json(404, {"error": "slug not found"})
            return
        new_slug = f"{slug[:40]}-copy-{time.strftime('%m%d-%H%M')}"
        dst = os.path.normpath(os.path.join(GENERATED_DIR, new_slug))
        if not dst.startswith(real_base):
            self._send_json(403, {"error": "forbidden"})
            return
        try:
            shutil.copytree(src, dst)
            url = f"https://forge.v2app.ru/l/{new_slug}/"
            self._send_json(200, {"ok": True, "slug": new_slug, "url": url})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_export(self, slug: str):
        """Return landing as a ZIP archive (index.html + content.json)."""
        import zipfile, io
        if not slug or "/" in slug or ".." in slug:
            self._send_json(400, {"error": "invalid slug"})
            return
        src = os.path.normpath(os.path.join(GENERATED_DIR, slug))
        real_base = os.path.realpath(GENERATED_DIR)
        if not src.startswith(real_base):
            self._send_json(403, {"error": "forbidden"})
            return
        if not os.path.isdir(src):
            self._send_json(404, {"error": "slug not found"})
            return
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in ("index.html", "content.json"):
                fpath = os.path.join(src, fname)
                if os.path.isfile(fpath):
                    zf.write(fpath, fname)
        buf.seek(0)
        data = buf.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{slug}.zip"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_bulk(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        action = body.get("action", "")
        slugs = body.get("slugs", [])
        if action not in ("archive", "delete", "unarchive"):
            self._send_json(400, {"error": "action must be archive|unarchive|delete"})
            return
        if not isinstance(slugs, list) or not slugs:
            self._send_json(400, {"error": "slugs must be a non-empty array"})
            return
        import shutil
        done = []
        for slug in slugs:
            if not slug or "/" in slug or ".." in slug:
                continue
            if action == "delete":
                landing_dir = os.path.normpath(os.path.join(GENERATED_DIR, slug))
                if landing_dir.startswith(os.path.realpath(GENERATED_DIR)) and os.path.isdir(landing_dir):
                    shutil.rmtree(landing_dir)
                    with _db_lock:
                        conn = _get_db()
                        conn.execute("DELETE FROM views WHERE slug=?", (slug,))
                        conn.commit()
                        conn.close()
                    done.append(slug)
            elif action == "archive":
                meta_set(slug, status="archive")
                done.append(slug)
            elif action == "unarchive":
                meta_set(slug, status="live")
                done.append(slug)
        self._send_json(200, {"ok": True, "done": done})

    def _handle_leads_get(self, slug: str):
        if not slug or "/" in slug or ".." in slug:
            self._send_json(400, {"error": "invalid slug"})
            return
        with _db_lock:
            conn = _get_db()
            rows = conn.execute(
                "SELECT id, email, created_at FROM leads WHERE slug=? ORDER BY created_at DESC",
                (slug,)
            ).fetchall()
            conn.close()
        leads = [{"id": r[0], "email": r[1], "created_at": r[2]} for r in rows]
        self._send_json(200, {"slug": slug, "count": len(leads), "leads": leads})

    def _handle_leads_post(self, slug: str):
        if not slug or "/" in slug or ".." in slug:
            self._send_json(400, {"error": "invalid slug"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        email = body.get("email", "").strip().lower()
        if not email or "@" not in email or len(email) > 200:
            self._send_json(400, {"error": "invalid email"})
            return
        with _db_lock:
            conn = _get_db()
            conn.execute(
                "INSERT INTO leads (slug, email, created_at) VALUES (?, ?, ?)",
                (slug, email, int(time.time()))
            )
            conn.commit()
            conn.close()
        self._send_json(200, {"ok": True})

    def log_message(self, format, *args):
        pass


def run():
    os.makedirs(GENERATED_DIR, exist_ok=True)
    _get_db()
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), ForgeHandler) as httpd:
        print(f"Design Forge server running on port {PORT}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    run()
