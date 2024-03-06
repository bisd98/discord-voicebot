from dotenv import load_dotenv
from openai import OpenAI
import openai
import os

load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')

client = OpenAI(api_key=api_key)

def model_response(messages):
    model_name = "gpt-3.5-turbo"

    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=200,
        n=1,
        stop=None,
        temperature=0.7,
    )
    
    message = response.choices[0].message.content
    messages.append(response.choices[0].message)

    return message

def model_audio_response(messages):
    response = openai.audio.speech.create(
        model="tts-1",
        voice="echo",
        input=messages,
    )
    
    audio_data = response.content

    return audio_data



