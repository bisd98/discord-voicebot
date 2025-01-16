"""Discord bot implementation for voice assistant integration.

This module provides the Discord bot implementation that interfaces with the voice
assistant system. It handles:
- Voice channel connections
- Command processing
- Message handling
- Voice recording management
- Bot lifecycle management

Classes:
    DiscordBot: Custom Discord bot implementation

Commands:
    listen: Start voice assistant in current channel
    stop_listening: Stop voice assistant in current channel
    shutdown: Gracefully shut down the bot (owner only)
"""

import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from voice_assistant.assistant import VoiceAssistant

load_dotenv()

owner_id = os.getenv("OWNER_ID")
discord_token = os.getenv("DISCORD_TOKEN")


class DiscordBot(commands.Bot):
    """Custom Discord bot with voice assistant capabilities.

    Attributes:
        voice_assistant (VoiceAssistant): Voice assistant instance
    """

    def __init__(self) -> None:
        """Initialize bot with required intents and voice assistant."""
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.voice_assistant = VoiceAssistant()


bot = DiscordBot()
connections = {}


@bot.event
async def on_ready():
    """Handle bot ready event.

    Logs successful login information.
    """
    print(f"Logged in as {bot.user.name}")


@bot.event
async def on_message(message: discord.Message):
    """Handle incoming messages.

    Processes commands and generates responses for regular messages.

    Args:
        message (discord.Message): Received message
    """
    if message.author == bot.user:
        return

    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    messages = [
        {
            "role": "system",
            "content": "Jesteś zabawnym asystentem tekstowym na platformie Discord. Twoje imię to Alvin. Odpowiadaj zawsze zwięźle i krótko, maksymalnie na 100 słów.",
        },
        {"role": "user", "content": message.content},
    ]
    response = (
        await bot.voice_assistant.language_model.language_model.get_chat_response(
            messages
        )
    )
    await message.channel.send(response)


@bot.command(name="listen")
async def listen(ctx):
    """Start voice assistant in current voice channel.

    Args:
        ctx: Command context
    """
    voice = ctx.author.voice

    if not voice:
        await ctx.send("You aren't in a voice channel!")

    vc = await voice.channel.connect()
    connections.update({ctx.guild.id: vc})

    await bot.voice_assistant.listen()

    vc.start_recording(
        bot.voice_assistant.audio_input.audio_sink, once_done, ctx.channel
    )
    await ctx.send("Started listening!")


async def once_done(sink: discord.sinks, channel: discord.TextChannel, *args):
    """Handle completion of voice recording.

    Args:
        sink (discord.sinks): Audio sink instance
        channel (discord.TextChannel): Channel for notifications
        *args: Additional arguments
    """
    await bot.voice_assistant.stop_listening()


@bot.command()
async def stop_listening(ctx):
    """Stop voice assistant in current channel.

    Args:
        ctx: Command context
    """
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_recording()
        del connections[ctx.guild.id]
    else:
        await ctx.send("I am currently not listening here.")


@bot.command(name="shutdown", hidden=True)
async def shutdown_command(ctx):
    """Shut down the bot (owner only).

    Args:
        ctx: Command context
    """
    if str(ctx.author.id) == owner_id:
        await ctx.send("Shutting down...")
        await bot.close()
    else:
        await ctx.send("You do not have permission to shut down the bot.")
