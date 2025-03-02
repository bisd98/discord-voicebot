import asyncio
import io
import re

import discord

from typing import TypedDict, Dict, Any

from speech_to_text.whisper_stt import OpenAIWhisper
from discord_vc_sinks.audio_sinks import MultiAudioSink

from openai_api.openai_client import OpenAIClient
from langgraph.graph import StateGraph, START, END
from voice_assistant.logging_config import logger
 
class State(TypedDict):
    message_call: tuple[int, str]
    input_audio: tuple[int, bytes]
    transcription: tuple[int, tuple[float, str]]
    response: str
    output_audio_queue: asyncio.Queue
    playback_ready: asyncio.Event
    

class VoiceAssistant:
    def __init__(self):
        self.global_state: Dict[str, Any] = {
            "system_prompt": "Jesteś przyjaznym i zabawnym asystentem głosowym na platformie Discord, a Twoje imię to Alvin. Zachowuj się tak, jakbyś rozmawiał na kanale głosowym platformy Discord. Wszelkie cyfry i liczby zapisuj słownie.Do odpowiedzi używaj tylko słów! Jeśli użytkownik podziękuje lub wykryjesz zakończenie rozmowy, napisz na koniec słowo 'True'",
            "activate_words": ["alvin", "alwin"],
            "chat_history": [],
            "caller_id": None
        }
        self.loop = asyncio.get_event_loop()
        
        self.large_language_model = OpenAIClient()
        self.speech_to_text_model = OpenAIWhisper()
        self.text_to_speech_model = OpenAIClient()
        
        self.graph = self.create_graph()
        
        self.audio_sink = MultiAudioSink()
        self.audio_sink.callback_func = lambda speaker, pcm_s16le: asyncio.run_coroutine_threadsafe(
            self.graph.ainvoke({"input_audio": (speaker, pcm_s16le)}),
            self.loop
            )

    def create_graph(self):
        graph = StateGraph(State)
        
        graph.add_node("transcribe_audio", self.transcribe_audio)
        graph.add_node("update_caller_info", self.update_caller_info)
        graph.add_node("generate_response", self.generate_response)
        graph.add_node("synthesize_audio", self.synthesize_audio)
        graph.add_node("play_response", self.play_response_on_channel)

        graph.add_edge(START, "transcribe_audio")
        graph.add_conditional_edges(
            "transcribe_audio",
            self.process_transcription,
            {"process_call": "update_caller_info", "end_call": END}
            )
        graph.add_edge("update_caller_info", "generate_response")
        graph.add_edge("generate_response", "synthesize_audio")
        graph.add_edge("generate_response", "play_response")
        graph.add_edge("play_response", END)
        
        return graph.compile()

    async def clear_assistant_components(self):
        """Gracefully stops all assistant components.

        Cancels tasks and cleans up resources.
        """
        if self.audio_sink.vc is not None:
            logger.info("Attempting to hang up from voice channel...")
            try:
                self.audio_sink.cleanup()
                await self.large_language_model.client.close()
            except Exception as e:
                logger.error(e)
            await self.audio_sink.vc.disconnect()
            self.audio_sink.vc = None
            logger.info("Disconnected from voice channel.")

    async def transcribe_audio(self, state: State) -> None:
        """Process audio input from tuple."""
        if "input_audio" not in state:
            print("No audio input")
            return END
            
        speaker, pcm_s16le = state["input_audio"]
        message = self.speech_to_text_model.transcribe_pcm(pcm_s16le)
        if message is not None:
            return {"transcription": (speaker, message)}
        return {"transcription": None}

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

    async def update_caller_info(self, state: State) -> None:
        speaker, transcription = state["transcription"]
        _, message = transcription
        self.global_state["caller_id"] = speaker
        return {"message_call": (speaker, message)}

    async def process_transcription(self, state: State) -> None:
        """Processes transcription results and manages conversation state.

        Handles speaker identification and activation word detection.
        """
        if state["transcription"] is None:
            return END
        speaker, transcription = state['transcription']
        confidence, message = transcription

        await self._log_transcription(speaker, confidence, message)
        if self.global_state["caller_id"] is not None:
            if self.global_state["caller_id"] == speaker:
                return "process_call"
            else:
                return END
        if any(
            word.lower() in message.lower() for word in self.global_state["activate_words"]
        ):
            return "process_call"
        return END

    def _get_context(self, state: State, message: str) -> None:
        """Updates conversation context with new message.

        Args:
            message (str): User message to add to context
        """
        if self.global_state["chat_history"]:
            self.global_state["chat_history"].append({"role": "user", "content": message})
        else:
            context = [
                {"role": "system", "content": self.global_state["system_prompt"]},
                {"role": "user", "content": message},
            ]
            self.global_state["chat_history"] = context

    async def _log_response(self, response: str) -> None:
        logger.info(f"[Voicebot] Alvin says: {response}")

    def _check_chat_status(self, state:State, response: str) -> str:
        if response.split()[-1] == "True":
            logger.info(
                f"Conversation between [User] {self.global_state['caller_id']} and [Voicebot] Alvin ended"
            )
            self.global_state["caller_id"] = None
            self.global_state["chat_history"] = []
            return response.rsplit(None, 1)[0]
        else:
            return response

    async def generate_response(self, state: State) -> None:
        """Main conversation loop that generates responses."""
        speaker, message = state["message_call"]
        if message:
            self._get_context(state, message)
            response = await self.large_language_model.get_chat_response(
                self.global_state["chat_history"]
            )
            await self._log_response(response)
            self.global_state["chat_history"].append(
                {"role": "assistant", "content": response}
            )
            response = self._check_chat_status(state, response)

            return({"response": response, "output_audio_queue": asyncio.Queue(), "playback_ready": asyncio.Event()})
        #state["message_call"] = None

    async def synthesize_audio(self, state: State) -> None:
        """Continuously synthesizes audio chunks and adds to queue."""
        segments = re.findall(r"[^.!?]+[.!?]?", state["response"])
        segments = [seg.strip() for seg in segments if seg.strip()]
        
        # Process first segment and signal playback can start
        if segments:
            first_chunk = await self.text_to_speech_model.get_text_to_speech(segments[0])
            await state["output_audio_queue"].put(first_chunk)
            state["playback_ready"].set()
            
            # Process remaining segments
            for segment in segments[1:]:
                audio_data = await self.text_to_speech_model.get_text_to_speech(segment)
                await state["output_audio_queue"].put(audio_data)
        
        await state["output_audio_queue"].put(None)
        #return {}

    async def play_response_on_channel(self, state: State) -> None:
        """Plays audio chunks as they become available."""
        # Wait for first chunk to be ready
        await state["playback_ready"].wait()
        
        while True:
            chunk = await state["output_audio_queue"].get()
            if chunk is None:
                state["output_audio_queue"].task_done()
                return {}
                
            if self.audio_sink.vc:
                audio_source = discord.FFmpegPCMAudio(io.BytesIO(chunk), pipe=True)
                self.audio_sink.vc.play(audio_source)
                
                while self.audio_sink.vc.is_playing():
                    await asyncio.sleep(0.3)
