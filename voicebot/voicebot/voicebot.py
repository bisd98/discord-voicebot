from dotenv import load_dotenv
import discord
from discord.ext import commands
import os 

load_dotenv()

owner_id = os.getenv('OWNER_ID')
discord_token = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.command(name='hello')
async def hello_command(ctx):
    await ctx.send('Hello!')

@bot.command(name='join')
async def join_command(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        voice_channel = await channel.connect()
        await ctx.send(f'Joined {channel}')
    else:
        await ctx.send('You are not in a voice channel.')

@bot.command(name='leave')
async def leave_command(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send('Left the voice channel.')
    else:
        await ctx.send('I am not in a voice channel.')

@bot.command(name='shutdown', hidden=True)
async def shutdown_command(ctx):
    if ctx.author.id == owner_id:
        await ctx.send('Shutting down...')
        await bot.close()
    else:
        await ctx.send('You do not have permission to shut down the bot.')

bot.run(discord_token)