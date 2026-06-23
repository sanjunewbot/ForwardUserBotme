from alphagram import Client, filters
from alphagram.errors import FloodWait
from config import SESSION_STRING
import asyncio
import traceback
import os
from flask import Flask
import threading
import time

flask_app = Flask(__name__)

app = Client("FORWARDER", use_default_api=True, session_string=SESSION_STRING)

logs = []
task = None
s, f = 0, 0
caption = ''

paused = False

not_allowed = []

async def forward(chat_id: int, fwd_id: int, st: int, en: int):
    global s, f
    
WORK_TIME = 15 * 60      # 15 minutes
COOL_TIME = 60 * 60      # 1 hour

start_time = time.time()

c = st

while c <= en:

    while paused:
        await asyncio.sleep(5)
        
    # Auto Cooldown
    if time.time() - start_time >= WORK_TIME:
        logs.append(
            f"Cooldown started for {COOL_TIME // 60} minutes"
        )

        await asyncio.sleep(COOL_TIME)

        logs.append("Cooldown finished. Restarting...")
        start_time = time.time()

    try:
        batch_end = min(c + 199, en)

        msgs = await app.get_messages(
            chat_id,
            list(range(c, batch_end + 1))
        )

        if not isinstance(msgs, list):
            msgs = [msgs]

        for msg in msgs:

            if not msg:
                continue

            if msg.text and 'text' in not_allowed:
                continue
            elif msg.photo and 'photo' in not_allowed:
                continue
            elif msg.video and 'video' in not_allowed:
                continue
            elif msg.animation and 'gif' in not_allowed:
                continue
            elif msg.audio and 'audio' in not_allowed:
                continue
            elif msg.voice and 'voice' in not_allowed:
                continue
            elif msg.document and 'file' in not_allowed:
                continue

            await msg.copy(fwd_id, caption=caption)

            s += 1

            await asyncio.sleep(1.5)

        c = batch_end + 1

    except FloodWait as e:
        t = e.value if isinstance(e.value, int) else 30
        logs.append(f"FloodWait: sleeping {t}s")
        await asyncio.sleep(t)

    except Exception:
        logs.append(traceback.format_exc())
        f += 1


@app.on_message(filters.command("a", '.') & filters.me)
async def allow_handler(_, m):
    types_ = ['text', 'photo', 'video', 'gif', 'audio', 'voice', 'file']
    txt = ''
    for type_ in types_:
        if type_ in not_allowed:
            txt += f'`.{type_}` ❌\n'
        else:
            txt += f'`.{type_}` ✅\n'
    await m.reply(txt)


@app.on_message(filters.command(['text', 'photo', 'video', 'gif', 'audio', 'voice', 'file'], '.') & filters.me)
async def uf_handler(_, m):
    type_ = m.text.split()[0][1:]
    if type_ in not_allowed:
        not_allowed.remove(type_)
        txt = f'Enabled {type_} ✅'
    else:
        not_allowed.append(type_)
        txt = f'Disabled {type_} ❌'
    await m.reply(txt)


@app.on_message(filters.command("id", '.') & filters.me)
async def id_handler(_, m):
    if m.reply_to_message:
        txt = f'Chat ID: `{m.chat.id}`\nMsg ID: `{m.reply_to_message.id}`'
    else:
        txt = f'Chat ID: `{m.chat.id}`'
    await m.reply(txt)


@app.on_message(filters.command("caption", '.') & filters.me)
async def caption_handler(_, m):
    global caption
    spl = m.text.split()

    if len(spl) > 1:
        caption = " ".join(spl[1:])
        await m.reply(f"Caption was set to '{caption}'")
    else:
        if caption:
            await m.reply(f"Caption was set to '{caption}'")
        else:
            await m.reply("No Caption.")


@app.on_message(filters.command("dcaption", '.') & filters.me)
async def dcaption_handler(_, m):
    global caption
    caption = ''
    await m.reply("Caption removed.")


@app.on_message(filters.command("logs", '.') & filters.me)
async def logs_handler(_, m):
    if not logs:
        return await m.reply("No Logs Stored.")

    with open("logs.txt", "w") as e:
        e.write("\n\n".join(logs))

    await m.reply_document("logs.txt")
    os.remove("logs.txt")


@app.on_message(filters.command('f', '.') & filters.me)
async def f_handler(_, m):
    global task, s, f

    if task:
        return await m.reply("A process is already running.")

    spl = m.text.split()

    if len(spl) < 4:
        return await m.reply(
            "Usage:\n.f <from_chat_id> <start_id> <end_id>"
        )

    try:
        chat_id = int(spl[1])
        st_id = int(spl[2])
        en_id = int(spl[3])
        fwd_id = m.chat.id
    except ValueError:
        return await m.reply("Invalid IDs.")

    await m.reply("Forwarding started...\nVisit the hosted URL for progress.")

    s, f = 0, 0
    task = asyncio.create_task(forward(chat_id, fwd_id, st_id, en_id))

    try:
        await task
    except Exception:
        pass
    finally:
        task = None
        await m.reply(f"Forwarding Completed\n\nSuccess: {s}\nFailed: {f}")
        s, f = 0, 0
        
@app.on_message(filters.command('pause', '.') & filters.me)
async def pause_handler(_, m):
    global paused

    paused = True
    await m.reply("Forwarding Paused.")

@app.on_message(filters.command('resume', '.') & filters.me)
async def resume_handler(_, m):
global paused
paused = False
    await m.reply("Forwarding Resumed.")

@app.on_message(filters.command('status', '.') & filters.me)
async def status_handler(_, m):
global paused, task

if not task:
    return await m.reply("No task running.")

if paused:
    await m.reply("Status: PAUSED")
else:
    await m.reply("Status: RUNNING")


@app.on_message(filters.command('cancel', '.') & filters.me)
async def cancel_handler(_, m):
    if not task:
        return await m.reply("No Task is going.")
    task.cancel()
    await m.reply("Cancelled.")


@flask_app.route('/')
def index():
    if not task:
        return "No Task is going.", 200
    return f"{s=}\n{f=}", 200


port = int(os.getenv("PORT", 8000))
threading.Thread(
    target=flask_app.run,
    kwargs={'host': '0.0.0.0', 'port': port},
    daemon=True
).start()

print("Started.")
app.run()
