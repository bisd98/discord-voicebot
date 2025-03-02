"""OpenAI API client module for chat and speech synthesis.

This module provides a singleton client for interacting with OpenAI's APIs,
handling both chat completions and text-to-speech operations asynchronously.

Attributes:
    OpenAIClient: Singleton class for AsyncOpenAI API interactions
"""

import os
from typing import Dict, List

from dotenv import load_dotenv
from openai import AsyncOpenAI


class OpenAIClient:
    """Singleton client for AsyncOpenAI API interactions.

    Implements singleton pattern for managing OpenAI API credentials
    and providing async methods for chat and speech synthesis.

    Attributes:
        client (AsyncOpenAI): AsyncOpenAI API client instance
        _instance (OpenAIClient): Singleton instance reference
    """

    _instance = None

    def __new__(cls) -> "OpenAIClient":
        """Create or return singleton instance.

        Returns:
            OpenAIClient: Singleton instance
        """
        if cls._instance is None:
            cls._instance = super(OpenAIClient, cls).__new__(cls)
            load_dotenv()
            api_key = os.getenv("OPENAI_API_KEY")
            cls._instance.client = AsyncOpenAI(api_key=api_key)
        return cls._instance

    async def get_chat_response(self, messages: List[Dict[str, str]]) -> str:
        """Generate chat response using GPT-4o mini model asynchronously.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with
                'role' and 'content' keys

        Returns:
            str: Generated response text
        """   
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=600,
            n=1,
            stop=None,
            temperature=0.7,
        )

        message = response.choices[0].message.content

        return message

    async def get_text_to_speech(self, text: str) -> bytes:
        """Convert text to speech using OpenAI TTS API asynchronously.

        Args:
            text (str): Input text to synthesize

        Returns:
            bytes: Raw audio data in supported format
        """
        response = await self.client.audio.speech.create(
            model="tts-1",
            voice="echo",
            input=text,
        )

        audio_data = response.content

        return audio_data
