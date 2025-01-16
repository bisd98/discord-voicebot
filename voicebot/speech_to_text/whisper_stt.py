"""OpenAI Whisper speech recognition module.

This module provides speech-to-text functionality using OpenAI's Whisper model,
with support for audio preprocessing and validation of transcription results.
"""

import io
import wave
from typing import Optional, Tuple

import librosa
import numpy as np
import torch
import whisper


class OpenAIWhisper:
    """Speech recognition implementation using OpenAI's Whisper model.

    Attributes:
        model (whisper.Whisper): Loaded Whisper model instance
        device (torch.device): Device for model inference (CPU/CUDA)
    """

    def __init__(self):
        """Initialize Whisper model and set compute device."""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = whisper.load_model("small").to(self.device)

    def _process_audio(
        self,
        pcm_data: bytes,
        channels: int = 2,
        sample_rate: int = 48000,
        target_sample_rate: int = 16000,
    ) -> np.ndarray:
        """Process raw PCM audio data for Whisper model input.

        Args:
            pcm_data (bytes): Raw PCM audio data
            channels (int): Number of audio channels
            sample_rate (int): Input sample rate in Hz
            target_sample_rate (int): Target sample rate for model

        Returns:
            np.ndarray: Processed mono audio at target sample rate
        """
        wav_bytes = self._pcm_to_wav_bytes(pcm_data, channels, sample_rate)
        y_resampled, sr = librosa.load(
            io.BytesIO(wav_bytes), sr=target_sample_rate, mono=True
        )
        return y_resampled

    def _pcm_to_wav_bytes(
        self, pcm_data: bytes, channels: int = 2, sample_rate: int = 48000
    ) -> bytes:
        """Convert PCM data to WAV format bytes.

        Args:
            pcm_data (bytes): Raw PCM audio data
            channels (int): Number of audio channels
            sample_rate (int): Sample rate in Hz

        Returns:
            bytes: WAV format audio data
        """
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_data)
            return wav_buffer.getvalue()

    def transcribe_pcm(self, pcm_data: bytes) -> Optional[Tuple[float, str]]:
        """Transcribe PCM audio data to text.

        Args:
            pcm_data (bytes): Raw PCM audio data

        Returns:
            Optional[Tuple[float, str]]: Confidence percentage and transcription text
                                       if valid speech detected, None otherwise
        """
        y_resampled = self._process_audio(pcm_data)
        audio_npy = y_resampled.astype(np.float32)
        with torch.no_grad():
            result = self.model.transcribe(
                audio=audio_npy,
                language="pl",
                temperature=0.5,
                logprob_threshold=-0.7,
                no_speech_threshold=0.2,
                condition_on_previous_text=False,
                word_timestamps=True,
                hallucination_silence_threshold=0.1,
            )

        segments = result.get("segments", [])
        if not segments:
            return None

        perc_prob = round(float(np.exp(segments[0]["avg_logprob"]) * 100), 2)

        return perc_prob, result["text"]
