from dotenv import load_dotenv
import openai
import os

load_dotenv()

openai.api_key = os.getenv('OPENAI_API_KEY')

def model_response(messages):
    model_name = "gpt-3.5-turbo"

    response = openai.chat.completions.create(
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