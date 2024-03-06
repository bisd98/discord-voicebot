from dotenv import load_dotenv
import os

from openai_api.openai_model import model_audio_response, model_response

from discord.ext import commands
import discord
import io
import asyncio


load_dotenv()

owner_id = os.getenv('OWNER_ID')
discord_token = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Events

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return
    
    messages = [{"role": "user", "content": message.content}]
    response = model_response(messages)
    await message.channel.send(response)
    await play_audio(message.author.voice.channel, response=response)
        

#Commands

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
    if str(ctx.author.id) == owner_id:
        await ctx.send('Shutting down...')
        await bot.close()
    else:
        await ctx.send('You do not have permission to shut down the bot.')
        
async def play_audio(voice_channel, response):
    if voice_channel:
        
        audio_data = model_audio_response(response)

        voice_client = discord.utils.get(bot.voice_clients, guild=voice_channel.guild)
        audio_source = discord.FFmpegPCMAudio(io.BytesIO(audio_data), pipe=True)
        voice_client.play(audio_source)
        
        while voice_client.is_playing():
            await asyncio.sleep(1)