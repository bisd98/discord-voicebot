from google.cloud import speech_v1
from google.cloud import texttospeech

# Authorize credentials via command: gcloud auth login

def gcloud_tts(text):
	
	client = texttospeech.TextToSpeechClient()
	input_text = texttospeech.SynthesisInput(text=text)
	voice = texttospeech.VoiceSelectionParams(language_code="pl-PL", name="pl-PL-Standard-B")

	audio_config = texttospeech.AudioConfig(
		audio_encoding=texttospeech.AudioEncoding.LINEAR16,
		sample_rate_hertz=48000,
		pitch=-3,
		speaking_rate=1.15,
		effects_profile_id=["headphone-class-device"]
		)

	response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)
	audio_bytes = response.audio_content
	
	return audio_bytes


def gcloud_stt(audio_data):
	
	client = speech_v1.SpeechClient()	
	audio = speech_v1.RecognitionAudio(content=audio_data)
	
	config = speech_v1.RecognitionConfig(
		encoding='LINEAR16',
		sample_rate_hertz=48000,
		language_code='pl-PL',
		audio_channel_count=2,
	)

	response = client.recognize(config=config, audio=audio)
	text = response.results[0].alternatives[0].transcript if len(response.results) > 0 else ''

	return text

