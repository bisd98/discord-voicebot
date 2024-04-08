import io
import discord
import asyncio
import numpy as np
from discord.ext import voice_recv
from gcloud_api.gcloud_models import gcloud_stt, gcloud_tts
from openai_api.openai_models import openai_gpt


class AudioBuffer:
    def __init__(self, speaker, sink):
        self.buffer = np.zeros(
            shape=(sink.NUM_SAMPLES * sink.BUFFER_FRAME_COUNT, sink.NUM_CHANNELS),
            dtype="int16",
        )
        self.buffer_pointer = 0
        self.speaker = speaker

    def fill_buffer(self, frame, NUM_SAMPLES):
        self.buffer[
            (self.buffer_pointer * NUM_SAMPLES) : (
                (1 + self.buffer_pointer) * NUM_SAMPLES
            )
        ] = frame
        self.buffer_pointer += 1
        print(f"BUFFER POINTER: {self.buffer_pointer}, USER: {self.speaker}")

    def clear_buffer(self):
        self.buffer.fill(0)
        self.buffer_pointer = 0


class BufferAudioSink(voice_recv.BasicSink):
    def __init__(self, flush):
        super().__init__(None)
        self.flush = flush
        self.NUM_CHANNELS = discord.opus.Decoder.CHANNELS
        self.NUM_SAMPLES = discord.opus.Decoder.SAMPLES_PER_FRAME
        self.BUFFER_FRAME_COUNT = 600
        self.buffers = dict()
        self.caller_id = None

    def _get_speaker_buffer(self, speaker):
        if self.buffers.get(speaker) is None:
            self.buffers[speaker] = AudioBuffer(speaker, self)
        return self.buffers[speaker]

    def _build_frame(self, voice_data):
        try:
            frame = np.ndarray(
                shape=(self.NUM_SAMPLES, self.NUM_CHANNELS),
                dtype="int16",
                buffer=voice_data.pcm,
            )
        except Exception as e:
            print(e)
            return None
        return frame

    def write(self, user, voice_data):
        speaker = user.id

        if self.caller_id and speaker != self.caller_id:
            self.flush(speaker, None)
            return

        current_buffer = self._get_speaker_buffer(speaker)

        frame = self._build_frame(voice_data)
        if frame is None:
            self.flush(speaker, None)
            return

        if current_buffer.buffer_pointer > self.BUFFER_FRAME_COUNT - 2:
            pcm_s16le = current_buffer.buffer.tobytes()
            self.flush(speaker, pcm_s16le)
            current_buffer.clear_buffer()
            return

        if np.abs(frame).sum() > 500:
            current_buffer.fill_buffer(frame, self.NUM_SAMPLES)
        elif current_buffer.buffer_pointer > 0:
            pcm_s16le = current_buffer.buffer.tobytes()
            self.flush(speaker, pcm_s16le)
            current_buffer.clear_buffer()


class AudioListener:
    def __init__(self):
        discord.opus._load_default()
        self.transcriber = gcloud_stt
        self.synthesizer = gcloud_tts
        self.language_model = openai_gpt
        self.voice_client = None
        self.audio_sink = BufferAudioSink(self._transcribe)
        self.vc_system_prompt = "Jesteś asystentem głosowym na platformie Discord, a Twoje imię to Alvin. Zachowuj się, jakbyś rozmawiał na kanale głosowym Discord. Do odpowiedzi używaj tylko słów! Na koniec swojej wypowiedzi upewnij się, że użytkownik dalej chce rozmawiać. Jeśli użytkownik podziękuje lub wykryjesz zakończenie rozmowy, napisz na koniec słowo 'True'"
        self.activate_words = ["alvin", "Alvin", "ALVIN", "alwin", "Alwin", "ALWIN"]
        self.chat_history = []
        self.messages = []

    async def listen(self, member):
        self.text_channel = member.voice.channel
        self.voice_channel = member.voice.channel
        if self.voice_channel is not None:
            self.voice_client = await self.voice_channel.connect(
                cls=voice_recv.VoiceRecvClient
            )
            self.voice_client.listen(self.audio_sink)
            print("Connected!")

    def _transcribe(self, speaker, pcm_s16le):
        if self.audio_sink.caller_id:
            if speaker != self.audio_sink.caller_id:
                return
        message = self.transcriber(pcm_s16le)
        print(f"{speaker} says: {message}")
        if self.audio_sink.caller_id or any(
            word in message for word in self.activate_words
        ):
            self.audio_sink.caller_id = speaker
            self.messages.append((speaker, message))

    async def _send_message_to_channel(
        self, member, message
    ):  # future transcriber feature
        speaker_nick = (
            str(member.nick if member.nick is not None else member)
            if member is not None
            else "N/A"
        )
        await self.text_channel.send(f"{speaker_nick} says: {message}")

    async def _play_response_on_channel(self, voice_channel, response):
        if voice_channel:
            audio_data = self.synthesizer(response)
            audio_source = discord.FFmpegPCMAudio(io.BytesIO(audio_data), pipe=True)
            self.voice_client.play(audio_source)
            while self.voice_client.is_playing():
                await asyncio.sleep(1)

    def _get_context(self, message):
        if self.chat_history:
            self.chat_history.append({"role": "user", "content": message})
        else:
            context = [
                {"role": "system", "content": self.vc_system_prompt},
                {"role": "user", "content": message},
            ]
            self.chat_history = context

    def _check_chat_status(self, response):
        if response.split()[-1] == "True":
            self.audio_sink.caller_id = None
            self.chat_history = []
            print("Conversation ended")
            return response.rsplit(None, 1)[0]
        else:
            return response

    async def message_sending_loop(self, guild, timeout=0.5):
        while True:
            if not guild or not self.messages:
                await asyncio.sleep(timeout)
                continue
            for speaker, message in self.messages:
                # member = guild.get_member(speaker) # future transcriber feature
                if message:
                    self._get_context(message)
                    response = self.language_model(self.chat_history)
                    self.chat_history.append({"role": "assistant", "content": response})
                    response = self._check_chat_status(response)
                    await self._play_response_on_channel(self.voice_channel, response)
            self.messages = []

    async def stop_listening(self):
        if self.voice_client is not None:
            print("Attempting to hang up from voice channel")
            try:
                self.voice_client.stop()
                self.voice_client.stop_listening()
            except Exception as e:
                print(e)
            await self.voice_client.disconnect()
            self.voice_client = None
            print("Disconnected!")
