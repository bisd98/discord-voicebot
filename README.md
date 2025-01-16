# Discord Voicebot Alvin 🤖

**Description**

This project contains the source code for a Discord voicebot named Alvin. Alvin is designed to work with the Polish language, but due to the OpenAI models used via API, it can be modified to work with any language.

**Features:**

* 👂 Capturing incoming audio on Discord voice channels (using the [Pycord](https://github.com/Pycord-Development/pycord))
* 🗣️ Recognizing user speech using OpenAI Whisper speech to text model
* 💬 Generating answers to user queries using the OpenAI GPT model
* 🤖 Generating realistic speech using OpenAI text to speech model


## Installation

1. Clone this repository to your computer.
2. Install the required dependencies:

```
pip install -r requirements.txt
```
3. Configure environment variables.
5. Go to the voicebot directory.
6. Run the bot:

```
python run.py
```

### Configuration

The bot require using environment variables stored in a .env file. This file should be placed in the root directory. Here's how to set it up:

1. Create the .env file:

Create a file named .env and add the following variables:

```
DISCORD_TOKEN=your_discord_bot_token
OWNER_ID=your_discord_user_id 
OPENAI_API_KEY=your_openai_api_key
```

2. Replace placeholders:

* Replace your_discord_bot_token with the actual token for your bot in string type (found on the Discord Developer Portal).
* Replace your_discord_user_id with your numerical Discord ID in integer type (enable Developer Mode in Discord settings to find this).
* Replace your_openai_api_key with your API key from OpenAI in string type.


## Usage

**How to use Alvin:**

1. To start a conversation with Alvin, Greet him by saying his name, for example "Hi Alvin" in the voice channel.
2. Alvin will start listening to you and will respond to your questions and commands.
3. To end the conversation, thank Alvin for his help or say "goodbye".

**Commands**

The bot supports the following commands:

* `listen`: Alvin joins the voice channel of the user who called the command and starts listening
* `stop_listening`: Alvin stops listening and disconnects from the voice channel
* `shutdown`: Alvin disconnects from the server

## Additional information

**Development**

This project is still under development. I encourage you to report bugs and suggestions for the development of the bot.

**License**

This project is licensed under the MIT license.

**Links**

* Discord API: [https://discord.com/developers/docs/intro](https://discord.com/developers/docs/intro)
* Python Discord API Wrapper: [https://github.com/Rapptz/discord.py](https://github.com/Rapptz/discord.py)
* Pycord: [https://github.com/Pycord-Development/pycord](https://github.com/Pycord-Development/pycord)

**Acknowledgments**

This project was created by [bisd98](https://github.com/bisd98/discord-voicebot).
