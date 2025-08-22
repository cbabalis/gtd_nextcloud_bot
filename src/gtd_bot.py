#!/usr/bin/env python3
"""
GTD bot: Telegram → Nextcloud (Markdown text files)
- Capture and organize GTD items into plain Markdown files on Nextcloud via WebDAV.
- Single-user design; Nextcloud app password recommended.

Commands:
  /in <text>
  /next <@context> <text>
  /wait <text>
  /proj <+Project> <text>
  /tickler <YYYY-MM-DD> <text>
  /list <inbox|wait|proj|tickler|next @context> [n]
  /done <inbox|wait|proj|tickler|next @context> <match...>
  /weekly
  /tickle
"""

import os, re, asyncio, logging, datetime as dt
from typing import Optional, Tuple
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ----------------- Config -----------------
TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TG_ALLOWED_CHAT = os.getenv("TELEGRAM_ALLOWED_CHAT", "").strip()
NC_BASE = os.getenv("NEXTCLOUD_BASE_URL", "").rstrip("/")
NC_USER = os.getenv("NEXTCLOUD_USER", "").strip()
NC_PASS = os.getenv("NEXTCLOUD_PASSWORD", "").strip()
GTD_ROOT = os.getenv("NEXTCLOUD_GTD_ROOT", "GTD").strip()

TICKLER_RUN_HOUR = int(os.getenv("TICKLER_RUN_HOUR", "7"))
WEEKLY_PUSH_DOW = os.getenv("WEEKLY_PUSH_DOW")
WEEKLY_PUSH_HOUR = os.getenv("WEEKLY_PUSH_HOUR")

assert TG_TOKEN, "Missing TELEGRAM_TOKEN"
assert NC_BASE and NC_USER and NC_PASS, "Missing Nextcloud env vars"

DAV_BASE = f"{NC_BASE}/remote.php/dav/files/{NC_USER}"
GTD_DIR_URL = f"{DAV_BASE}/{GTD_ROOT}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# ----------------- WebDAV helpers -----------------
def dav_req(method, url, **kw): return requests.request(method, url, auth=(NC_USER, NC_PASS), **kw)
def dav_head(url): return dav_req("HEAD", url)
def dav_mkcol(url): return dav_req("MKCOL", url)
def dav_get(url): 
    r = dav_req("GET", url); return r.status_code, r.content, r.headers.get("ETag")
def dav_put(url, data, etag=None):
    headers={}; 
    if etag: headers["If-Match"]=etag
    return dav_req("PUT", url, data=data, headers=headers)

def ensure_remote_dir(path_url):
    r = dav_head(path_url)
    if r.status_code == 404:
        dav_mkcol(path_url)

def read_text(url): 
    st,c,e = dav_get(url)
    if st==404: return 404,"",None
    if st!=200: return st,"",None
    return 200,c.decode("utf-8","ignore"),e

def write_text(url, text, etag=None):
    r = dav_put(url, text.encode("utf-8"), etag)
    if r.status_code in (200,201,204): return r.status_code
    if r.status_code==412: return dav_put(url, text.encode("utf-8"), None).status_code
    return r.status_code

def append_line(url, line):
    st,txt,e=read_text(url)
    if st==404: txt=""; e=None
    elif st!=200: raise RuntimeError(f"GET {st}")
    new = txt + line.rstrip()+"\n"
    write_text(url,new,e)

def read_tail(url,n=10):
    st,txt,_=read_text(url)
    if st==404: return "(empty)"
    if st!=200: return f"Error {st}"
    lines=[ln for ln in txt.splitlines() if ln.strip()]
    return "\n".join(lines[-n:]) if lines else "(empty)"

def remove_first_matching(url,needle):
    st,txt,e=read_text(url)
    if st!=200: return None
    lines=txt.splitlines()
    for i,ln in enumerate(lines):
        if needle.lower() in ln.lower():
            removed=lines.pop(i)
            write_text(url,"\n".join(lines)+("\n" if lines else ""),e)
            return removed
    return None

# ----------------- Paths -----------------
def today(): return dt.date.today().isoformat()
def clean(s): return re.sub(r"\s+"," ",s).strip()
def md(name): return f"{GTD_DIR_URL}/{name}.md"
def path_inbox(): return md("Inbox")
def path_wait(): return md("WaitingFor")
def path_proj(): return md("Projects")
def path_tickler(): return md("Tickler")
def path_done(): return md("Done")
def path_next_dir(): return f"{GTD_DIR_URL}/Next"
def path_next(ctx): return f"{path_next_dir()}/@{re.sub(r'[^a-z0-9_-]+','_',ctx.lstrip('@').lower())}.md"

def ensure_structure():
    ensure_remote_dir(GTD_DIR_URL); ensure_remote_dir(path_next_dir())

# ----------------- Telegram auth -----------------
def auth_ok(update): 
    if not TG_ALLOWED_CHAT: return True
    try: return update.effective_chat.id == int(TG_ALLOWED_CHAT)
    except: return True
async def deny(update): await update.message.reply_text("Not authorized")

# ----------------- Commands -----------------
async def cmd_in(update,ctx): 
    if not auth_ok(update): return await deny(update)
    t=clean(" ".join(ctx.args)); 
    if not t: return await update.message.reply_text("Usage: /in <text>")
    append_line(path_inbox(),f"{today()} {t}")
    await update.message.reply_text("Captured to Inbox.")

async def cmd_next(update,ctx):
    if not auth_ok(update): return await deny(update)
    if len(ctx.args)<2 or not ctx.args[0].startswith("@"):
        return await update.message.reply_text("Usage: /next <@context> <text>")
    c=ctx.args[0]; t=clean(" ".join(ctx.args[1:]))
    append_line(path_next(c),f"{today()} {t} {c}")
    await update.message.reply_text(f"Added to Next {c}.")

async def cmd_wait(update,ctx):
    if not auth_ok(update): return await deny(update)
    t=clean(" ".join(ctx.args)); 
    if not t: return await update.message.reply_text("Usage: /wait <text>")
    append_line(path_wait(),f"{today()} WAITING {t}")
    await update.message.reply_text("Added to Waiting For.")

async def cmd_proj(update,ctx):
    if not auth_ok(update): return await deny(update)
    if len(ctx.args)<2 or not ctx.args[0].startswith("+"):
        return await update.message.reply_text("Usage: /proj <+Project> <text>")
    p=ctx.args[0]; t=clean(" ".join(ctx.args[1:]))
    append_line(path_proj(),f"{today()} {p} :: {t}")
    await update.message.reply_text(f"Logged under {p}.")

async def cmd_tickler(update,ctx):
    if not auth_ok(update): return await deny(update)
    if len(ctx.args)<2: return await update.message.reply_text("Usage: /tickler <YYYY-MM-DD> <text>")
    d=ctx.args[0]; 
    try: dt.date.fromisoformat(d)
    except: return await update.message.reply_text("Date must be YYYY-MM-DD")
    t=clean(" ".join(ctx.args[1:]))
    append_line(path_tickler(),f"{d} TICKLER {t}")
    await update.message.reply_text("Added to Tickler.")

async def cmd_list(update,ctx):
    if not auth_ok(update): return await deny(update)
    if not ctx.args: return await update.message.reply_text("Usage: /list <list>")
    k=ctx.args[0].lower(); n=int(ctx.args[1]) if len(ctx.args)>1 and ctx.args[1].isdigit() else 10
    if k=="inbox": out=read_tail(path_inbox(),n)
    elif k in ("wait","waiting"): out=read_tail(path_wait(),n)
    elif k in ("proj","projects"): out=read_tail(path_proj(),n)
    elif k in ("tickler","tick"): out=read_tail(path_tickler(),n)
    elif k=="next" and len(ctx.args)>1 and ctx.args[1].startswith("@"): out=read_tail(path_next(ctx.args[1]),n)
    else: return await update.message.reply_text("Unknown list")
    await update.message.reply_text(out)

async def cmd_done(update,ctx):
    if not auth_ok(update): return await deny(update)
    if len(ctx.args)<2: return await update.message.reply_text("Usage: /done <list> <match>")
    k=ctx.args[0].lower(); rest=ctx.args[1:]
    if k=="inbox": p=path_inbox()
    elif k in ("wait","waiting"): p=path_wait()
    elif k in ("proj","projects"): p=path_proj()
    elif k in ("tickler","tick"): p=path_tickler()
    elif k=="next" and rest[0].startswith("@"): p=path_next(rest[0]); rest=rest[1:]
    else: return await update.message.reply_text("Bad usage")
    needle=" ".join(rest); rm=remove_first_matching(p,needle)
    if not rm: return await update.message.reply_text("Not found")
    append_line(path_done(),f"{today()} DONE ~~{rm}~~")
    await update.message.reply_text("Marked done.")

def count_lines(p): st,txt,_=read_text(p); return len([l for l in txt.splitlines() if l.strip()]) if st==200 else 0
def weekly_summary():
    return "\n".join([
        f"# Weekly Review ({dt.date.today()})",
        f"- Inbox: {count_lines(path_inbox())}",
        f"- Waiting: {count_lines(path_wait())}",
        f"- Projects: {count_lines(path_proj())}",
        f"- Tickler: {count_lines(path_tickler())}",
        "",
        "**Inbox last 5:**",read_tail(path_inbox(),5),
        "**Waiting last 5:**",read_tail(path_wait(),5)
    ])

def move_due_ticklers():
    st,txt,e=read_text(path_tickler()); 
    if st!=200: return 0
    lines=txt.splitlines(); rem=[]; moved=0
    for ln in lines:
        m=re.match(r"^(\d{4}-\d{2}-\d{2}) (.+)$",ln)
        if m:
            d=dt.date.fromisoformat(m[1])
            if d<=dt.date.today():
                append_line(path_inbox(),f"{today()} [TICKLER] {m[2]}"); moved+=1
            else: rem.append(ln)
        else: rem.append(ln)
    if moved: write_text(path_tickler(),"\n".join(rem)+"\n",e)
    return moved

async def cmd_weekly(update,ctx):
    if not auth_ok(update): return await deny(update)
    await update.message.reply_text(weekly_summary())

async def cmd_tickle(update,ctx):
    if not auth_ok(update): return await deny(update)
    m=move_due_ticklers(); await update.message.reply_text(f"Moved {m} ticklers")

async def on_startup(app): ensure_structure()

def main():
    # Register the async startup callback via the builder
    app = (
        ApplicationBuilder()
        .token(TG_TOKEN)
        .post_init(on_startup)   # <-- runs your async on_startup(app) before polling
        .build()
    )
    app.add_handler(CommandHandler("in",cmd_in))
    app.add_handler(CommandHandler("next",cmd_next))
    app.add_handler(CommandHandler("wait",cmd_wait))
    app.add_handler(CommandHandler("proj",cmd_proj))
    app.add_handler(CommandHandler("tickler",cmd_tickler))
    app.add_handler(CommandHandler("list",cmd_list))
    app.add_handler(CommandHandler("done",cmd_done))
    app.add_handler(CommandHandler("weekly",cmd_weekly))
    app.add_handler(CommandHandler("tickle",cmd_tickle))

    logging.info("Starting bot...")
    app.run_polling()

if __name__=="__main__": main()

