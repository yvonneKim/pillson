# bot.py

import discord
import sys
from discord.ext import tasks
from json import dumps, load
from os.path import exists
from datetime import datetime, timedelta

TOKEN = "NICE TRY"
GUILD = "DONT BOTHER"
CHANNEL = "take-ur-meds"
client = discord.Client()

db = {"users": {}}
db_filename = "db.json"

channel = None


@client.event
async def on_ready():
    print(f"Token is {TOKEN}")
    guild = discord.utils.get(client.guilds, name=GUILD)
    if not guild:
        print(f"Guild {GUILD} not found! Exiting.")
        exit(0)

    print(f"Guild {GUILD} found!")

    global channel
    channel = discord.utils.get(guild.channels, name=CHANNEL)
    if not channel:
        print(f"Channel {CHANNEL} not found! Exiting.")
        exit(0)

    print(f"Channel {CHANNEL} found!")

    load_db()
    clock.start()


@client.event
async def on_message(message):
    global db
    if message.author == client.user:
        return

    if message.channel != channel:
        return

    tokens = message.content.lower().split()
    cmd = tokens[0]
    user = message.author.name

    if user not in db["users"]:
        register_new_user(user)

    if cmd == "/help":
        help_message = (
            "/set_time - set your time to take meds\n"
            + "/unset_time - remove your time to take meds\n"
            + "/took - record your meds being taken for the day\n"
            + "/help - display this message"
        )

        await channel.send(help_message)

    if cmd == "/set_time":
        time = (datetime.now() + timedelta(seconds=3)).time().strftime("%I:%M:%S")
        db["users"][user]["meds_time"] = time
        await channel.send(f"You just set your meds time for {time}")

    if cmd == "/unset_time":
        db["users"][user]["meds_time"] = None
        await channel.send("You just unset your meds time. I won't bother you.")

    if cmd == "/took":
        sys.stdout.flush()
        record_meds_taken(user)
        await message.channel.send(f"{user} has just taken their meds today! Congrats!")

    save_db()


def save_db():
    global db
    open(db_filename, "w").write(dumps(db))


def load_db():
    global db
    if not exists(db_filename):
        save_db()

    db = load(open(db_filename, "r"))


def register_new_user(user):
    print(f"Adding new user {user}")
    db["users"][user] = {"meds_history": [], "meds_time": None, "reminded": False}
    save_db()


def record_meds_taken(user):
    global db
    users = db["users"]
    if user not in users:
        print("fart")

    users[user]["meds_history"].append(datetime.now().strftime("%c"))


@tasks.loop(seconds=5.0)
async def clock():
    global db
    now = datetime.now()
    for user, data in db["users"].items():
        print(data)
        if not data["meds_time"]:
            continue

        if now.time() in [3, 4, 5, 6]:
            data["reminded"] = False

        if now.time() > datetime.strptime(data["meds_time"], "%I:%M:%S").time():
            if data["meds_history"]:
                last_time_taken = datetime.strptime(data["meds_history"][-1], "%c")
            else:
                last_time_taken = datetime.min
            if last_time_taken.day < now.day and not data["reminded"]:
                await channel.send(f"Time for {user} to take their meds!")
                data["reminded"] = True
                save_db()


@clock.error
async def on_error(err):
    print("OH SHIT!!")
    print(err)


client.run(TOKEN)
