from dotenv import load_dotenv
import os

from openai_api.openai_models import openai_gpt
from discord_vc_tools.audio_api import AudioListener

from discord.ext import commands
import discord


load_dotenv()

owner_id = os.getenv("OWNER_ID")
discord_token = os.getenv("DISCORD_TOKEN")


class DiscordBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.audio_listener = None
        self.tc_system_prompt = "Jesteś voicebotem na platformie Discord. Twoje imię to Alvin. Odpowiadaj zawsze zwięźle i krótko, maksymalnie na 100 słów."


bot = DiscordBot()

# Events


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    messages = [
        {"role": "system", "content": bot.tc_system_prompt},
        {"role": "user", "content": message.content},
    ]
    response = openai_gpt(messages)
    await message.channel.send(response)


# Commands


@bot.command(name="hello")
async def hello_command(ctx):
    await ctx.send("Hello!")


@bot.command(name="join")
async def join_command(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        voice_channel = await channel.connect()
        await ctx.send(f"Joined {channel}")
    else:
        await ctx.send("You are not in a voice channel.")


@bot.command(name="leave")
async def leave_command(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel.")
    else:
        await ctx.send("I am not in a voice channel.")


@bot.command(name="shutdown", hidden=True)
async def shutdown_command(ctx):
    if str(ctx.author.id) == owner_id:
        await ctx.send("Shutting down...")
        await bot.close()
    else:
        await ctx.send("You do not have permission to shut down the bot.")


@bot.command(name="listen")
async def listen(ctx):
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("You are not connected to a voice channel.")
    else:
        bot.audio_listener = AudioListener()
        bot.loop.create_task(bot.audio_listener.message_sending_loop(bot.guilds[0]))
        await bot.audio_listener.listen(ctx.author)


@bot.command(name="stop_listening")
async def stop_listening(ctx):
    await bot.audio_listener.stop_listening()
    bot.audio_listener = None


@bot.command(name="check")
async def listen(ctx):
    await ctx.send(f"Voice channel: {ctx.author.voice.channel}")
    await ctx.send(f"Text channel: {ctx.channel}")


@bot.command(name="stop")
async def stop_command(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("Stopped playing audio.")
