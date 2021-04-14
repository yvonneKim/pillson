# bot.py

import discord
import sys
from dataclasses import dataclass, asdict
from discord.ext.tasks import loop
from discord.ext.commands import Bot, DefaultHelpCommand
from json import dumps, load
from os.path import exists
from datetime import datetime, time, timedelta
import pytz


config = load(open("config", "r"))
TOKEN = config["TOKEN"]
GUILD = config["GUILD"]
CHANNEL = config["CHANNEL"]
DB_FILENAME = config["DB_FILENAME"]
central = pytz.timezone("US/Central")

bot = Bot("/")
channel = None
db = None
next_reset = datetime.now(central) + timedelta(hours=5)
end_of_time = datetime.max.replace(tzinfo=central) 


@dataclass
class User:
    name: str = ""
    took_meds: bool = False
    next_reminder: time = end_of_time
    reminded: bool = False

    def reset(self):
        self.took_meds = False
        self.reminded = False

    def encode(o):
        if isinstance(o, User):
            return asdict(o)
        return str(o)

    def decode(o):
        if "name" in o.keys():
            return User(
                o["name"],
                o["took_meds"],
                datetime.fromisoformat(o["next_reminder"]),
                o["reminded"],
            )
        return o


class Database:
    def __init__(self):
        self.data = {"users": {}}

    def load(self, filename):
        self.data = load(open(filename, "r"), object_hook=User.decode)

    def save(self, filename):
        open(filename, "w").write(dumps(self.data, indent=4, default=User.encode))

    def add_user(self, name):
        self.data["users"][name] = User(name)

    def get_user(self, name):
        print(self.data["users"])
        if name not in self.data["users"]:
            self.add_user(name)

        return self.data["users"][name]

    def get_users(self):
        return [user for _, user in self.data["users"].items()]


@bot.event
async def on_ready():
    global channel
    guild = discord.utils.get(bot.guilds, name=GUILD)
    channel = discord.utils.get(guild.channels, name=CHANNEL)

    global db
    db = Database()
    if not exists(DB_FILENAME):
        db.save(DB_FILENAME)

    db.load(DB_FILENAME)
    print("Good to go!")
    clock.start()


@bot.command(name="unset_time", brief="Turns off your meds reminder")
async def unset_time(ctx):
    user = db.get_user(ctx.author.name)
    user.next_reminder = end_of_time
    await ctx.send("You just unset your meds time. I won't bother you.")


@bot.command(name="took", brief="Records your meds being taken for today")
async def took(ctx):
    user = db.get_user(ctx.author.name)
    if user.took_meds:
        await ctx.send("You've already taken your meds today.")

    else:
        user.took_meds = True
        await ctx.send(f"{user.name} has just taken their meds today! Congrats!")


@bot.command(name="set_time", brief="Sets a reminder for this time")
async def set_time(ctx, *, time_str):
    user = db.get_user(ctx.author.name)
    try:
        parsed_time = datetime.strptime(time_str, "%I:%M %p").time()
        next_reminder = datetime.combine(datetime.now(), parsed_time, central)
    except Exception:
        await channel.send("Please specify a time like this: /set_time 7:12 PM")
        return

    user.next_reminder = next_reminder
    await channel.send(
        f"You just set your meds time for {user.next_reminder.strftime('%I:%M %p')}"
    )


@loop(seconds=5.0)
async def clock():
    global db
    global next_reset
    now = datetime.now(central)

    if now > next_reset:
        [user.reset() for user in db.get_users()]
        next_reset += timedelta(days=1)

    for user in db.get_users():
        if now > user.next_reminder:
            if not (user.took_meds or user.reminded):
                await channel.send(f"Time for {user.name} to take their meds!")
                user.reminded = True

            user.next_reminder += timedelta(days=1)

    db.save(DB_FILENAME)


bot.run(TOKEN)
