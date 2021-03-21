# bot.py

import discord
import sys
from dataclasses import dataclass, asdict
from discord.ext import tasks
from json import dumps, load, JSONEncoder
from os.path import exists
from datetime import datetime, time, timedelta
from typing import Dict

TOKEN = ""
GUILD = ""
CHANNEL = ""
DB_FILENAME = ""

with open("config", "r") as f:
    config = load(f)
    TOKEN = config["TOKEN"]
    GUILD = config["GUILD"]
    CHANNEL = config["CHANNEL"]
    DB_FILENAME = config["DB_FILENAME"]

client = discord.Client()

channel = None
db = None
next_reset = datetime.today() + timedelta(hours=5)


@dataclass
class User:
    name: str = ""
    took_meds: bool = False
    next_reminder: time = datetime.max
    reminded: bool = False


class UserEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, User):
            return asdict(o)
        return str(o)


def user_from_dict(data: Dict) -> User:
    user = User(
        data["name"],
        data["took_meds"],
        datetime.fromisoformat(data["next_reminder"]),
        data["reminded"],
    )
    return user


class Database:
    def __init__(self):
        self.data = {"users": {}}

    def load(self, filename):
        loaded_data = load(open(filename, "r"))
        print(loaded_data)
        for name, user in loaded_data["users"].items():
            self.data["users"][name] = user_from_dict(user)

    def save(self, filename):
        print(self.data)
        open(filename, "w").write(dumps(self.data, indent=4, cls=UserEncoder))

    def add_user(self, name):
        self.data["users"][name] = User(name)

    def get_user(self, name):
        return self.data["users"].get(name)

    def get_users(self):
        return [user for _, user in self.data["users"].items()]


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

    global db
    db = Database()
    if not exists(DB_FILENAME):
        db.save(DB_FILENAME)

    db.load(DB_FILENAME)
    clock.start()


@client.event
async def on_message(message):
    global db
    if message.author == client.user:
        return

    if message.channel != channel:
        return

    message_sender = message.author.name
    if not db.get_user(message_sender):
        db.add_user(message_sender)

    user = db.get_user(message_sender)

    tokens = message.content.lower().split()
    cmd = tokens[0]
    if cmd == "/help":
        help_message = (
            "/set_time - set your time to take meds\n"
            + "/unset_time - remove your time to take meds\n"
            + "/took - record your meds being taken for the day\n"
            + "/help - display this message"
        )
        await channel.send(help_message)

    if cmd == "/set_time":
        try:
            parsed_time = datetime.strptime(
                tokens[1] + " " + tokens[2], "%I:%M %p"
            ).time()
            next_reminder = datetime.combine(datetime.now(), parsed_time)
        except Exception:
            await channel.send("Please specify a time like this: /set_time 7:12 PM")
            return

        user.next_reminder = next_reminder
        await channel.send(
            f"You just set your meds time for {user.next_reminder.strftime('%I:%M %p')}"
        )

    if cmd == "/unset_time":
        user.next_reminder = datetime.max
        await channel.send("You just unset your meds time. I won't bother you.")

    if cmd == "/took":
        if user.took_meds:
            await message.channel.send(f"You've already taken your meds today.")

        else:
            user.took_meds = True
            await message.channel.send(
                f"{user.name} has just taken their meds today! Congrats!"
            )

    sys.stdout.flush()
    db.save(DB_FILENAME)


def reset_users():
    for user in db.get_users():
        user.took_meds = False
        user.reminded = False


@tasks.loop(seconds=5.0)
async def clock():
    global db
    global next_reset
    now = datetime.now()

    if now > next_reset:
        reset_users()
        next_reset += timedelta(days=1)

    for user in [u for u in db.get_users() if u.next_reminder]:
        if now > user.next_reminder:
            if not (user.took_meds or user.reminded):
                await channel.send(f"Time for {user.name} to take their meds!")
                user.reminded = True

            user.next_reminder += timedelta(days=1)

    db.save(DB_FILENAME)


client.run(TOKEN)
