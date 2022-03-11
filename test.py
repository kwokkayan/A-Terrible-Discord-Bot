from dis import disco
from re import sub
import discord
import subprocess
import sys
import os
from environs import Env
from urllib.parse import urlparse, parse_qs
import requests
# REMEBER TO CHANGE
BOT_SECRET = "NzEzMDU2MTc2NzY5NzI4NjEy.XsajUA.KpjqlXIxSDAJLstgucCEVbb6kps"
API_KEY = "AIzaSyCBw1d8pXHmrwIdMEE3OlS5MQ0QW-3oXo0"
YTAPI_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
FILTER = "-filter_complex \"acrossover=split=1200 6000[LOW][MID][HIGH];[LOW]volume=1.07[VLOW];[MID]volume=1.05[VMID];[HIGH]volume=1[VHIGH];[VLOW]aformat=sample_fmts=s16:channel_layouts=stereo[OLOW];[VMID]aformat=sample_fmts=s16:channel_layouts=stereo[OMID];[VHIGH]aformat=sample_fmts=s16:channel_layouts=stereo[OHIGH];[OLOW][OMID][OHIGH]amerge=inputs=3\""
FFMPEG_OPTIONS = "-ar 48000 " + FILTER
# REMEMBER TO CHANGE

# KNOWN ISSUES OF PRIVATE PLAYLIST
def parseVideoUrls(res):
    urls = []
    for item in res["items"]:
        urls.append("https://www.youtube.com/watch?v=" + item["contentDetails"]["videoId"])
    return urls

def fetchPlaylistData(plId):
    r = requests.get(YTAPI_URL, params={
        "key" : API_KEY,
        "part" : "contentDetails",
        "maxResults" : 50,
        "playlistId" : plId
    })
    return r.json()

class MyClient(discord.Client):
    voiceClient = None
    yt_process = None
    source = None
    playing_list = False
    playlistId = None
    urls = None
    queue = None
    def killPlayingProcess(self):
        self.urls = []
        self.yt_process.kill()
        self.voiceClient.stop()
        self.yt_process.wait()
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
    async def on_message(self, message):
        print('Message from {0.author}: {0.content}'.format(message))
        command = message.content.split(" ")
        if (command[0] == "!connect" and message.author.voice != None): # connect logic
            if (self.voiceClient == None):
                self.voiceClient = await message.author.voice.channel.connect()
            else:
                await self.voiceClient.move_to(message.author.voice.channel)
        if (command[0] == "!disconnect" and self.voiceClient != None): # disconnect logic
            await self.voiceClient.disconnect()
            self.voiceClient = None
        if (command[0] == "!play" and self.voiceClient != None): # play music logic --> youtube supported NEED TO ADD PLAYLIST
            if (len(command) != 2):
                await message.channel.send("Usage: !play youtubeURL")
                return
            if (self.voiceClient.is_playing() or self.voiceClient.is_paused()):
                self.killPlayingProcess()
            #parse url to find if list
            self.urls = []
            query_dict = parse_qs(urlparse(command[1]).query)
            if (query_dict.get("list")):
                self.playing_list = True
                self.playlistId = query_dict.get("list")[0]
                self.urls = parseVideoUrls(fetchPlaylistData(self.playlistId))
            # playing songs
            if len(self.urls) == 0: # only one song
                self.yt_process = subprocess.Popen(["youtube-dl", command[1], '-i', '-f', '251', '--no-part', '--no-cache-dir',  '-o', '-'], stdout=subprocess.PIPE)
                try:
                    self.source = discord.FFmpegOpusAudio(self.yt_process.stdout, pipe=True, options=FFMPEG_OPTIONS)
                    def cleanup(error): # ALWAYS KILL THE PROCESS BEFORE KILLING THE VOICECLIENT
                        self.source.cleanup()
                    self.voiceClient.play(self.source, after=cleanup)
                except discord.ClientException:
                    await message.channel.send("Error: playback error!")
                    return
            else: # playlists -- very dirty code
                self.yt_process = subprocess.Popen(["youtube-dl", self.urls.pop(0), '-i', '-f', '251', '--no-part', '--no-cache-dir',  '-o', '-'], stdout=subprocess.PIPE)
                try:
                    self.source = discord.FFmpegOpusAudio(self.yt_process.stdout, pipe=True, options=FFMPEG_OPTIONS)
                    def cleanup(error): # ALWAYS KILL THE PROCESS BEFORE KILLING THE VOICECLIENT
                        self.yt_process.kill()
                        self.source.cleanup()
                        if (len(self.urls) > 0): # next song -- dank js-esque recursion
                            print("next song")
                            self.yt_process = subprocess.Popen(["youtube-dl", self.urls.pop(0), '-i', '-f', '251', '--no-part', '--no-cache-dir',  '-o', '-'], stdout=subprocess.PIPE)
                            self.source = discord.FFmpegOpusAudio(self.yt_process.stdout, pipe=True, options=FFMPEG_OPTIONS)
                            self.voiceClient.play(self.source, after=cleanup)
                        else: # get next page logic
                            pass 
                    self.voiceClient.play(self.source, after=cleanup)
                except discord.ClientException:
                    await message.channel.send("Error: playback error!")
                    return
        if (command[0] == "!stop" and self.voiceClient != None): # stop music logic
            if (self.voiceClient.is_playing() or self.voiceClient.is_paused()):
                self.killPlayingProcess()
        if (command[0] == "!pause" and self.voiceClient != None): # pause music logic
            if (self.voiceClient.is_playing()):
                self.voiceClient.pause()
        if (command[0] == "!resume" and self.voiceClient != None): # resume music logic
            if (self.voiceClient.is_paused()):
                self.voiceClient.resume()
        #loop function
        print(self.voice_clients, self.voiceClient)

env = Env()
env.read_env()

client = MyClient()
#client.run(env.str("BOT_TOKEN"))
client.run(BOT_SECRET)