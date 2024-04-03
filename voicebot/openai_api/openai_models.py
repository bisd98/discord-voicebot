from dotenv import load_dotenv
from openai import OpenAI
import openai
import os

load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=api_key)

def openai_gpt(messages):
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=200,
        n=1,
        stop=None,
        temperature=0.7,
    )
    
    message = response.choices[0].message.content
    messages.append(response.choices[0].message)

    return message

def openai_tts(messages):
    
    response = openai.audio.speech.create(
        model="tts-1",
        voice="shimmer",
        input=messages,
    )
    
    audio_data = response.content

    return audio_data