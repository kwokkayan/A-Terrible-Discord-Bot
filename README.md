# Discord-Bot
An awful attempt at building a discord bot for personal use.
## Installing Dependencies locally
1. Python Libraries: [Youtube-dl](http://ytdl-org.github.io/youtube-dl/), [discord.py](https://github.com/Rapptz/discord.py), and others. Install [pipenv](https://pipenv.pypa.io/en/latest/) to get them.
2. Binaries: [ffmpeg](https://ffmpeg.org/). Install the one your OS uses.
3. API keys: get you a [Discord bot secret](https://discord.com/developers/applications) and [Youtube Data API key](https://developers.google.com/youtube/v3). 
## Running locally
1. Create a .env file in the root directory with the following:
```
BOT_SECRET=YOUR_BOT_SECRET
API_KEY=YOUR_API_KEY
```
2. Add the bot to the server and run test.py.
3. Wait for the login message.
## Running on Heroku
1. Add buildpacks for [ffmpeg](https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest.git) first and python second.
2. Set Config Vars the same as the .env file above.
3. Push the root directory to the heroku application.
4. Enable the worker resource when the build successfully completes.
5. Wait for the login message.  
## Available Commands
```
!help             -- shows all commands
!connect          -- connects to the voice channel where the message sender is
!disconnect       -- disconnects from the voice channel
!play Youtube_URL -- plays the audio of a youtube video. 
                     Supports single videos and public playlists. 
                     Enqueues to a song queue if the bot is playing.
!stop             -- stops the audio and clears the song queue.
!skip             -- skips to the next song in the queue.
!listqueue        -- lists *some* songs in the queue.
```
## Known Issues
1. Inconsistent playback speed.  
2. Sometimes youtube-dl returns a 403 HTTP response and the music doesn't play. 
3. Private playlists cannot be played.
4. Queue not being updated when a song finishes. **I don't want to waste my API call quotas >_<** 
## More Features
1. Multiplayer text game of some sort.
2. Custom image searching for image sharing sites
3. MORE TO COME
