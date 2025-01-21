"""Voice assistant implementation module.

This module provides the core voice assistant functionality including:
- Audio input/output processing
- Speech-to-text transcription
- Language model interaction
- Text-to-speech synthesis
- Task coordination and resource management

The assistant implements an event-driven architecture using asyncio
for handling concurrent audio processing and conversation flows.

Classes:
    AudioInput: Handles Discord voice input
    SpeechToText: Manages speech recognition
    LanguageModel: Handles conversation logic
    TextToSpeech: Converts responses to audio
    AudioOutput: Manages Discord audio output
    VoiceAssistant: Main coordinator class
"""

import asyncio
import io
import re
from typing import Any, Dict, Optional

import discord

from discord_vc_sinks.audio_sinks import MultiAudioSink
from openai_api.openai_client import OpenAIClient
from speech_to_text.whisper_stt import OpenAIWhisper
from voice_assistant.logging_config import logger


class AudioInput:
    """Handles audio input processing from Discord voice channel.

    Attributes:
        audio_sink (MultiAudioSink): Instance for capturing Discord audio packets
        audio_queue (asyncio.Queue): Queue for audio data
        loop (asyncio.AbstractEventLoop): Event loop for async operations
    """

    def __init__(self, audio_sink: MultiAudioSink, audio_queue: asyncio.Queue) -> None:
        self.audio_sink: MultiAudioSink = audio_sink
        self.audio_queue: asyncio.Queue = audio_queue
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self.audio_sink.callback_func = self._send_to_speech_to_text_queue

    def _send_to_speech_to_text_queue(self, speaker: int, pcm_s16le: bytes) -> None:
        """Queues captured audio data for processing.

        Args:
            speaker (int): Discord user ID of the speaker
            pcm_s16le (bytes): Raw PCM audio data
        """
        asyncio.run_coroutine_threadsafe(
            self.audio_queue.put((speaker, pcm_s16le)), self.loop
        )


class SpeechToText:
    """Handles conversion of audio to text using speech recognition.

    Attributes:
        transcriber (OpenAIWhisper): Speech recognition client
        state (Dict[str, Any]): Shared state dictionary
        audio_queue (asyncio.Queue): Input queue for audio data
        speech_to_text_queue (asyncio.Queue): Output queue for transcribed text
    """

    def __init__(
        self,
        transcriber: OpenAIWhisper,
        state: Dict[str, Any],
        audio_queue: asyncio.Queue,
        speech_to_text_queue: asyncio.Queue,
    ) -> None:
        self.transcriber = transcriber
        self.state = state
        self.audio_queue = audio_queue
        self.speech_to_text_queue = speech_to_text_queue

    async def _transcription_worker(self) -> None:
        """Background task that processes audio chunks into text.

        Continuously pulls from audio queue and pushes transcription results.
        """
        while True:
            item = await self.audio_queue.get()
            if item is None:
                break
            speaker, pcm_s16le = item
            message = self.transcriber.transcribe_pcm(pcm_s16le)
            if message is not None:
                await self.speech_to_text_queue.put((speaker, message))

    async def _log_transcription(
        self, speaker: int, confidence: float, message: str
    ) -> None:
        """Logs transcription results.

        Args:
            speaker (int): Discord user ID
            confidence (float): Transcription confidence score
            message (str): Transcribed text
        """
        logger.info(f"[User] {speaker} says ({confidence}% confidence): {message}")

    async def _handle_caller_id(self, speaker: int, message: str) -> None:
        if self.state["caller_id"] is not None:
            if self.state["caller_id"] == speaker:
                self.state["message_call"] = (speaker, message)
                return
            else:
                return
        if any(
            word.lower() in message.lower() for word in self.state["activate_words"]
        ):
            self.state["caller_id"] = speaker
            self.state["message_call"] = (speaker, message)

    async def _process_transcriptions(self) -> None:
        """Processes transcription results and manages conversation state.

        Handles speaker identification and activation word detection.
        """
        while True:
            result = await self.speech_to_text_queue.get()
            if result is None:
                break
            speaker, transcription = result
            confidence, message = transcription

            await self._log_transcription(speaker, confidence, message)
            await self._handle_caller_id(speaker, message)


class LanguageModel:
    """Manages conversation flow using language model.

    Handles context management and response generation.

    Attributes:
        language_model: OpenAI API client
        state: Shared conversation state
    """

    def __init__(self, language_model: OpenAIClient, state: Dict[str, Any]) -> None:
        self.language_model = language_model
        self.state = state

    def _get_context(self, message: str) -> None:
        """Updates conversation context with new message.

        Args:
            message (str): User message to add to context
        """
        if self.state["chat_history"]:
            self.state["chat_history"].append({"role": "user", "content": message})
        else:
            context = [
                {"role": "system", "content": self.state["system_prompt"]},
                {"role": "user", "content": message},
            ]
            self.state["chat_history"] = context

    async def _log_response(self, response: str) -> None:
        logger.info(f"[Voicebot] Alvin says: {response}")

    def _check_chat_status(self, response: str) -> str:
        if response.split()[-1] == "True":
            logger.info(
                f"Conversation between [User] {self.state['caller_id']} and [Voicebot] Alvin ended"
            )
            self.state["caller_id"] = None
            self.state["chat_history"] = []
            return response.rsplit(None, 1)[0]
        else:
            return response

    async def _message_sending_loop(self, audio_output: "TextToSpeech") -> None:
        """Main conversation loop that generates responses.

        Args:
            audio_output (TextToSpeech): Instance for audio synthesis
        """
        while True:
            if self.state["message_call"]:
                speaker, message = self.state["message_call"]
                if message:
                    self._get_context(message)
                    response = await self.language_model.get_chat_response(
                        self.state["chat_history"]
                    )
                    await self._log_response(response)
                    self.state["chat_history"].append(
                        {"role": "assistant", "content": response}
                    )
                    response = self._check_chat_status(response)

                    await audio_output._process_response(response)
                self.state["message_call"] = None
            await asyncio.sleep(1)


class TextToSpeech:
    """Converts text responses to speech audio.

    Handles text segmentation and audio synthesis.

    Attributes:
        synthesizer: Text-to-speech client
        state: Shared state dictionary
        text_to_speech_queue: Queue for synthesized audio
    """

    def __init__(
        self,
        synthesizer: OpenAIClient,
        state: Dict[str, Any],
        text_to_speech_queue: asyncio.Queue,
    ) -> None:
        self.synthesizer = synthesizer
        self.state = state
        self.text_to_speech_queue = text_to_speech_queue

    async def _process_response(self, response: str, chunk_size: int = 2) -> None:
        """Converts text response to audio in manageable chunks.

        Args:
            response (str): Text to synthesize
            chunk_size (int, optional): Number of sentences per chunk. Defaults to 2.
        """
        if not response:
            return

        segments = re.findall(r"[^.!?]+[.!?]?", response)
        segments = [seg.strip() for seg in segments if seg.strip()]

        chunks = [
            " ".join(segments[i : i + chunk_size])
            for i in range(0, len(segments), chunk_size)
        ]

        running_task = None
        for i, chunk in enumerate(chunks):
            if i < len(chunks) - 1:
                asyncio.create_task(
                    self.synthesizer.get_text_to_speech(chunks[i + 1])
                    )
            
            if running_task:
                audio_data = await running_task
                await self.text_to_speech_queue.put(audio_data)
            
            running_task = asyncio.create_task(
                self.synthesizer.get_text_to_speech(chunk)
            )
        
        if running_task:
            audio_data = await running_task
            await self.text_to_speech_queue.put(audio_data)


class AudioOutput:
    """Manages audio playback to Discord voice channel.

    Handles queuing and playing synthesized audio responses.

    Attributes:
        text_to_speech_queue: Queue containing audio to play
    """

    def __init__(self, text_to_speech_queue: asyncio.Queue) -> None:
        self.text_to_speech_queue = text_to_speech_queue

    async def _play_response_on_channel(self, audio_sink: MultiAudioSink) -> None:
        """Continuously plays queued audio responses.

        Args:
            audio_sink (MultiAudioSink): Discord voice client wrapper
        """
        while True:
            audio_data = await self.text_to_speech_queue.get()
            if audio_data is None:
                break
            if audio_sink.vc:
                audio_source = discord.FFmpegPCMAudio(io.BytesIO(audio_data), pipe=True)
                audio_sink.vc.play(audio_source)

                while audio_sink.vc.is_playing():
                    await asyncio.sleep(0.5)


class VoiceAssistant:
    """Main voice assistant class orchestrating the entire pipeline.

    Coordinates audio input/output, speech recognition, language model,
    and text-to-speech components.

    Attributes:
        state: Shared state dictionary
        audio_queue: Queue for raw audio
        speech_to_text_queue: Queue for transcribed text
        text_to_speech_queue: Queue for synthesized audio
        audio_input: AudioInput instance
        speech_to_text: SpeechToText instance
        language_model: LanguageModel instance
        text_to_speech: TextToSpeech instance
        audio_output: AudioOutput instance
    """

    def __init__(self) -> None:
        self.state: Dict[str, Any] = {
            "system_prompt": "Jesteś przyjaznym i zabawnym asystentem głosowym na platformie Discord, a Twoje imię to Alvin. Zachowuj się, jakbyś rozmawiał na kanale głosowym Discord. Wszelkie cyfry i liczby zapisuj słownie.Do odpowiedzi używaj tylko słów! Jeśli użytkownik podziękuje lub wykryjesz zakończenie rozmowy, napisz na koniec słowo 'True'",
            "activate_words": ["alvin", "alwin"],
            "chat_history": [],
            "message_call": None,
            "caller_id": None
        }

        self._message_task: Optional[asyncio.Task] = None
        self._process_transcriptions_task: Optional[asyncio.Task] = None
        self._transcription_worker_task: Optional[asyncio.Task] = None
        self._response_playback_task: Optional[asyncio.Task] = None

        self.audio_queue: asyncio.Queue = asyncio.Queue()
        self.speech_to_text_queue: asyncio.Queue = asyncio.Queue()
        self.text_to_speech_queue: asyncio.Queue = asyncio.Queue()

        self.audio_input = AudioInput(MultiAudioSink(), self.audio_queue)
        self.speech_to_text = SpeechToText(
            OpenAIWhisper(), self.state, self.audio_queue, self.speech_to_text_queue
        )
        self.language_model = LanguageModel(OpenAIClient(), self.state)
        self.text_to_speech = TextToSpeech(
            OpenAIClient(), self.state, self.text_to_speech_queue
        )
        self.audio_output = AudioOutput(self.text_to_speech_queue)

    async def listen(self):
        """Starts all assistant components and begins listening.

        Initializes background tasks for audio processing pipeline.
        """
        logger.info("Voicebot connected to voice channel!")
        self._message_task = asyncio.create_task(
            self.language_model._message_sending_loop(self.text_to_speech)
        )
        self._transcription_worker_task = asyncio.create_task(
            self.speech_to_text._transcription_worker()
        )
        self._process_transcriptions_task = asyncio.create_task(
            self.speech_to_text._process_transcriptions()
        )
        self._response_playback_task = asyncio.create_task(
            self.audio_output._play_response_on_channel(self.audio_input.audio_sink)
        )

    async def stop_listening(self):
        """Gracefully stops all assistant components.

        Cancels tasks and cleans up resources.
        """
        if self.audio_input.audio_sink.vc is not None:
            logger.info("Attempting to hang up from voice channel...")
            try:
                if self._message_task is not None:
                    self._message_task.cancel()
                if self._process_transcriptions_task is not None:
                    self._process_transcriptions_task.cancel()
                self.audio_input.audio_sink.cleanup()
                await self.language_model.language_model.client.close()
                await self.audio_queue.put(None)
                await self.speech_to_text_queue.put(None)
            except Exception as e:
                logger.error(e)
            await self.audio_input.audio_sink.vc.disconnect()
            self.audio_input.audio_sink.vc = None
            logger.info("Disconnected from voice channel.")
