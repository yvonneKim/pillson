# bot.py

import discord
from dataclasses import dataclass, asdict
from discord.ext.tasks import loop
from discord.ext.commands import Bot
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
role_book = None
next_reset = central.localize(datetime.now()) + timedelta(hours=5)
end_of_time = datetime.max.replace(tzinfo=central)

roles = [
    {"streak": 0, "name": "Unmedicated Plebian", "base_obj": None},
    {"streak": 1, "name": "Barely Medicated Mess", "base_obj": None},
    {"streak": 2, "name": "Pill Buddy", "base_obj": None},
    {"streak": 3, "name": "Triple Piller", "base_obj": None},
    {"streak": 7, "name": "Medication Sensation", "base_obj": None},
    {"streak": 14, "name": "Well-Medicated One", "base_obj": None},
    {"streak": 21, "name": "Master of Taking Pills", "base_obj": None},
    {"streak": 28, "name": "Pill-Poppin PHD", "base_obj": None},
]


@dataclass
class User:
    name: str = ""
    took_meds: bool = False
    streak: int = 0
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
                o["streak"],
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


async def init_roles(guild):
    existing_roles = await guild.fetch_roles()
    for role in roles:
        role_obj = discord.utils.get(existing_roles, name=role["name"])
        if not role_obj:
            role_obj = await guild.create_role(name=role["name"])

        role["base_obj"] = role_obj


def role_for_streak(streak):
    for role in reversed(roles):
        if streak >= role["streak"]:
            return role["base_obj"]

    return None


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

    await init_roles(guild)
    print("Pillson online! Please be nice to me.")
    clock.start()


@bot.command(name="unset_time", brief="Turns off your meds reminder")
async def unset_time(ctx):
    user = db.get_user(ctx.author.name)
    print(f"{user.name} issued unset_time command!")
    user.next_reminder = end_of_time
    await ctx.send("You just unset your meds time. I won't bother you.")


@bot.command(name="took", brief="Records your meds being taken for today")
async def took(ctx):
    user = db.get_user(ctx.author.name)
    print(user)
    print(f"{user.name} issued took command!")
    if user.took_meds:
        await ctx.send("You've already taken your meds today.")

    else:
        user.took_meds = True
        user.streak += 1
        await ctx.send(f"{user.name} now has a pill poppin streak at {user.streak}!")
        user_role = role_for_streak(user.streak)
        if user_role not in ctx.author.roles:
            print(f"{user.name} just earned a new role: {user_role.name}")
            await ctx.author.remove_roles(*[role["base_obj"] for role in roles])
            await ctx.author.add_roles(user_role)
            await ctx.send(f"CONGRATS! {user.name} is now a {user_role.name}!")


@bot.command(name="set_time", brief="Sets a reminder for this time")
async def set_time(ctx, *, time_str):
    user = db.get_user(ctx.author.name)
    print(f"{user.name} issued set_time command!")
    try:
        parsed_time = datetime.strptime(time_str, "%I:%M %p").time()
        next_reminder = central.localize(datetime.combine(datetime.now(), parsed_time))
        print(next_reminder)
    except Exception:
        await channel.send("Please specify a time like this: /set_time 7:12 PM")
        return

    user.next_reminder = next_reminder
    await channel.send(
        f"You just set your meds time for {user.next_reminder.strftime('%I:%M %p')}"
    )
    print(f"{user.name} successfully set time for {user.next_reminder}")


@bot.command(name="reset_pillson", hidden=True)
async def reset_pillson(ctx):
    await reset()


async def reset():
    for user in db.get_users():
        if not user.took_meds:
            await channel.send(
                f"{user.name} broke their streak at {user.streak}. Back to zero :("
            )
            print(f"{user.name} broke their streak, previously: {user.streak}")
            user.streak = 0

        user.reset()


@loop(seconds=5.0)
async def clock():
    global db
    global next_reset
    now = central.localize(datetime.now())
    if now > next_reset:
        print(f"({now}) Resetting...")
        await reset()
        next_reset += timedelta(days=1)
        print(f"Reset. Next reset time is {next_reset}")

    for user in db.get_users():
        if now > user.next_reminder:
            if not (user.took_meds or user.reminded):
                print(f"{user.name} did NOT take their meds yet- reminding.")
                await channel.send(f"Time for {user.name} to take their meds!")
                user.reminded = True

            user.next_reminder += timedelta(days=1)
            print(f"{user.name} Next reminder is: {user.next_reminder}")

    db.save(DB_FILENAME)


bot.run(TOKEN)
