# bot.py

import discord
import sys
from discord.ext import tasks
from json import dumps, load
from os.path import exists
from datetime import datetime
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


class User:
    def __init__(
        self,
        name: str = "",
        took_meds: bool = False,
        meds_time: datetime = None,
        last_reminder: datetime = None,
    ):
        self.name: str = name
        self.took_meds: bool = took_meds
        self.meds_time: datetime.time = meds_time
        self.last_reminder: datetime.time = last_reminder

    def get_time(self) -> datetime:
        if not self.meds_time:
            return None
        return self.meds_time

    def set_time(self, time: datetime):
        self.meds_time = time

    def unset_time(self):
        self.meds_time = None

    def to_dict(self) -> Dict:
        meds_time = None
        if self.meds_time:
            meds_time = self.meds_time.strftime("%I:%M %p")

        last_reminder = None
        if self.last_reminder:
            last_reminder = self.last_reminder.strftime("%I:%M %p")

        return {
            "name": self.name,
            "took_meds": self.took_meds,
            "meds_time": meds_time,
            "last_reminder": last_reminder,
        }


def user_from_dict(data) -> User:
    meds_time = None
    if data["meds_time"]:
        meds_time = datetime.strptime(data["meds_time"], "%I:%M %p")

    last_reminder = None
    if data["last_reminder"]:
        last_reminder = datetime.strptime(data["last_reminder"], "%I:%M %p")

    user = User(
        data["name"],
        data["took_meds"],
        meds_time,
        last_reminder,
    )
    return user


class Database:
    def __init__(self):
        self.data = {"users": {}}

    def load(self, filename):
        loaded_data = load(open(filename, "r"))
        for name, user_data in loaded_data["users"].items():
            self.data["users"][name] = user_from_dict(user_data)

    def save(self, filename):
        output_data = {"users": {}}
        for name, user in self.data["users"].items():
            output_data["users"][name] = user.to_dict()
        open(filename, "w").write(dumps(output_data))

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

    tokens = message.content.lower().split()
    cmd = tokens[0]
    name = message.author.name
    user = db.get_user(name)
    if not user:
        db.add_user(name)
        user = db.get_user(name)

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
            time = datetime.strptime(tokens[1] + " " + tokens[2], "%I:%M %p")
        except Exception:
            await channel.send("Please specify a time like this: /set_time 7:12 PM")
            return

        user.set_time(time)
        await channel.send(f"You just set your meds time for {user.get_time()}")

    if cmd == "/unset_time":
        user.unset_time()
        await channel.send("You just unset your meds time. I won't bother you.")

    if cmd == "/took":
        user.took_meds = True
        await message.channel.send(f"{name} has just taken their meds today! Congrats!")

    sys.stdout.flush()
    db.save(DB_FILENAME)


counter = 0


@tasks.loop(seconds=5.0)
async def clock():
    global db
    global counter
    now = datetime.now()
    for user in db.get_users():
        print(counter)
        counter += 1
        if not user.get_time():
            continue

        if now.time().hour == 5:  # oh boy! 5 am!
            user.last_reminder = None

        if now > user.get_time():
            if not user.took_meds and not user.last_reminder:
                user.last_reminder = now.time()
                await channel.send(f"Time for {user.name} to take their meds!")

    db.save(DB_FILENAME)


client.run(TOKEN)
