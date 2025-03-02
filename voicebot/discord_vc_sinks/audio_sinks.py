"""Discord voice chat audio sink implementations.

This module provides custom sink implementations for handling Discord voice chat audio:
- Buffer-based audio processing
- Multi-user audio handling
- Silence detection and frame management

Classes:
    AudioBuffer: Manages audio frame buffering
    BufferAudioSink: Processes single user audio stream
    MultiAudioSink: Handles multiple user audio streams
"""

import logging
import threading
from typing import Dict, Optional

import discord
import numpy as np
from discord.sinks import Sink

discord.opus._load_default()


class AudioBuffer:
    """Audio frame buffer implementation.

    Manages circular buffer for storing audio frames with configurable size
    and channel count.

    Attributes:
        NUM_CHANNELS (int): Number of audio channels
        NUM_SAMPLES (int): Samples per frame
        BUFFER_FRAME_COUNT (int): Maximum frames in buffer
        buffer (np.ndarray): Audio data buffer
        buffer_pointer (int): Current position in buffer
    """

    def __init__(self):
        """Initialize audio buffer with default configuration.

        Sets up numpy buffer array with channels and frame configuration
        from Discord Opus decoder settings.
        """
        self.NUM_CHANNELS = discord.opus.Decoder.CHANNELS
        self.NUM_SAMPLES = discord.opus.Decoder.SAMPLES_PER_FRAME
        self.BUFFER_FRAME_COUNT = 800
        self.buffer = np.zeros(
            shape=(self.NUM_SAMPLES * self.BUFFER_FRAME_COUNT, self.NUM_CHANNELS),
            dtype="int16",
        )
        self.buffer_pointer = 0

    def fill_buffer(self, frame: np.ndarray) -> None:
        """Fill buffer with audio frame data.

        Args:
            frame (np.ndarray): Audio frame data
        """
        start = self.buffer_pointer * self.NUM_SAMPLES
        end = start + self.NUM_SAMPLES
        self.buffer[start:end] = frame
        self.buffer_pointer += 1

    def clear_buffer(self) -> None:
        """Reset buffer to initial state."""
        self.buffer.fill(0)
        self.buffer_pointer = 0


class BufferAudioSink(Sink):
    """Single user audio processing sink.

    Handles audio frame processing and buffer management
    for a single user's audio stream.

    Attributes:
        flush (Callable): Callback for processed audio data
        NUM_CHANNELS (int): Number of audio channels
        NUM_SAMPLES (int): Samples per frame
        BUFFER_FRAME_COUNT (int): Maximum frames in buffer
    """

    def __init__(self, flush):
        """Initialize single user audio sink.

        Args:
            flush (Callable[[int, bytes], None]): Callback for processed audio data
        """
        super().__init__()
        self.flush = flush
        self.timer = None
        self.NUM_CHANNELS = discord.opus.Decoder.CHANNELS
        self.NUM_SAMPLES = discord.opus.Decoder.SAMPLES_PER_FRAME
        self.BUFFER_FRAME_COUNT = 300
        self.buffer = None

    def _get_speaker_buffer(self) -> AudioBuffer:
        """Get or create buffer for current speaker.

        Returns:
            AudioBuffer: Speaker's audio buffer instance
        """
        if self.buffer is None:
            self.buffer = AudioBuffer()
        return self.buffer

    def _build_frame(self, pcm_data: bytes) -> Optional[np.ndarray]:
        """Convert PCM data to numpy array frame.

        Args:
            pcm_data (bytes): Raw PCM audio data

        Returns:
            Optional[np.ndarray]: Processed frame or None if failed
        """
        try:
            frame = np.frombuffer(pcm_data, dtype="int16").reshape(
                self.NUM_SAMPLES, self.NUM_CHANNELS
            )
            return frame
        except Exception:
            logging.exception("Failed to build frame")
            return None

    def write(self, voice_data: bytes, user: int) -> None:
        """Process incoming voice data.

        Args:
            voice_data (bytes): Raw voice data
            user (int): User ID of speaker
        """
        if len(voice_data) <= 3840:
            self._process_data(user, voice_data)
        else:
            # silcence packets
            pass

    def _process_data(self, speaker: int, pcm: bytes) -> None:
        """Process incoming PCM audio data.

        Handles frame building, buffer management and silence detection.

        Args:
            speaker (int): User ID of speaker
            pcm (bytes): Raw PCM audio data
        """
        if self.timer:
            self.timer.cancel()

        frame = self._build_frame(pcm)
        if frame is None:
            return

        current_buffer = self._get_speaker_buffer()
        if current_buffer.buffer_pointer > self.BUFFER_FRAME_COUNT - 2:
            pcm_s16le = current_buffer.buffer.tobytes()
            self.flush(speaker, pcm_s16le)
            current_buffer.clear_buffer()

        current_buffer.fill_buffer(frame)

        self.timer = threading.Timer(1.5, self._timeout_flush, args=(speaker,))
        self.timer.start()

    def _timeout_flush(self, speaker: int) -> None:
        """Flush buffer after timeout period.

        Args:
            speaker (int): User ID of speaker
        """
        current_buffer = self._get_speaker_buffer()
        if current_buffer.buffer_pointer > 0:
            pcm_s16le = current_buffer.buffer[
                : current_buffer.buffer_pointer * self.NUM_SAMPLES
            ].tobytes()
            self.flush(speaker, pcm_s16le)
            current_buffer.clear_buffer()

    def cleanup(self) -> None:
        """Clean up timer resources."""
        if self.timer:
            self.timer.cancel()
        pass


class MultiAudioSink(Sink):
    """Multi-user audio sink manager.

    Manages separate BufferAudioSink instances for each user in voice chat.

    Attributes:
        user_sinks (Dict[int, BufferAudioSink]): Map of user IDs to sinks
        callback_func (Callable): Audio processing callback
    """

    def __init__(self):
        super().__init__()
        self.user_sinks: Dict[int, BufferAudioSink] = {}
        self.callback_func = None

    def _get_or_create_sink(self, user_id: int) -> BufferAudioSink:
        """Get or create sink for user.

        Args:
            user_id (int): Discord user ID

        Returns:
            BufferAudioSink: User's audio sink
        """
        sink = self.user_sinks.get(user_id)
        if sink is None:
            sink = BufferAudioSink(self.callback_func)
            self.user_sinks[user_id] = sink
        return sink

    def wants_opus(self) -> bool:
        """Check if sink wants Opus-encoded data.

        Returns:
            bool: Always False, raw PCM preferred
        """
        return False

    def write(self, data: bytes, user: Optional[int]) -> None:
        """Write audio data for specific user.

        Args:
            data (bytes): Raw audio data
            user (Optional[int]): User ID of speaker
        """
        if user is None:
            return
        self._get_or_create_sink(user).write(data, user)

    def cleanup(self) -> None:
        """Clean up all user sinks and clear resources."""
        keys = list(self.user_sinks.keys())
        for speaker in keys:
            sink = self.user_sinks.get(speaker)
            if sink:
                sink.cleanup()
        self.user_sinks.clear()
