from dis import disco
from re import sub
import discord
import subprocess
import sys
import os
from environs import Env
from urllib.parse import urlparse, parse_qs
import requests
import re
# REMEBER TO CHANGE
env = Env()
env.read_env()
BOT_SECRET = env.str("BOT_SECRET")
API_KEY = env.str("API_KEY")
YTAPI_URL = "https://www.googleapis.com/youtube/v3/"
FILTER = "-filter_complex \"acrossover=split=1200 6000[LOW][MID][HIGH];[LOW]volume=1.1[VLOW];[MID]volume=1.05[VMID];[HIGH]volume=1.0[VHIGH];[VLOW]aformat=sample_fmts=s16:channel_layouts=stereo[OLOW];[VMID]aformat=sample_fmts=s16:channel_layouts=stereo[OMID];[VHIGH]aformat=sample_fmts=s16:channel_layouts=stereo[OHIGH];[OLOW][OMID][OHIGH]amerge=inputs=3\""
#FILTER = "-filter_complex \"crystalizer=i=1.15\""
FFMPEG_OPTIONS = "-ar 48000 -b:a 128k " + FILTER
#penis
# REMEMBER TO CHANGE
def parseSongData(res):
    details = []
    count = 1
    for item in res["items"]:
        embed = discord.Embed()
        embed.title = str(count) + ": " + item["snippet"]["title"]
        embed.url = "https://www.youtube.com/watch?v=" + item["id"]
        embed.set_author(name=item["snippet"]["channelTitle"], url="https://www.youtube.com/channel/"+item["snippet"]["channelId"])
        embed.set_image(url=item["snippet"]["thumbnails"]["default"]["url"])
        timestr = item["contentDetails"]["duration"]
        out = ':'.join(re.split('[A-Z]', timestr[2:len(timestr)-1]))
        embed.add_field(name="video length:", value=out, inline=True)
        details.append(embed)
        count += 1
    return details

def fetchSongData(songlist):
    songlist = [parse_qs(urlparse(s).query).get("v")[0] for s in songlist]
    print(songlist)
    params = {
        "key" : API_KEY,
        "part" : "snippet,contentDetails",
        "id" : ','.join(songlist)
    }
    r = requests.get(YTAPI_URL + "videos", params=params)
    return r.json()
# KNOWN ISSUES OF PRIVATE PLAYLIST
def parseVideoUrls(res):
    urls = []
    for item in res["items"]:
        urls.append("https://www.youtube.com/watch?v=" + item["contentDetails"]["videoId"])
    return (urls, res.get("nextPageToken")) # the second should be None if nothing

def fetchPlaylistData(plId, nextPage=None):
    params = {
            "key" : API_KEY,
            "part" : "contentDetails",
            "maxResults" : 5,
            "playlistId" : plId
        }
    if nextPage != None:
        params["pageToken"] = nextPage 
    r = requests.get(YTAPI_URL + "playlistItems", params=params)
    return r.json()

def getYTDLArgs(url):
    return ["youtube-dl", url, '-i', '-f', '251', '--no-part', '--no-cache-dir',  '-o', '-']
class YTSongQueue():
    queue = []
    maxItems = -1
    def __init__(self, items=[], max=-1):
        self.queue = items
        self.maxItems = max
    def enqueue(self, elem):
        if not self.isFull():
            self.queue.append(elem)
    def dequeue(self):
        if self.isEmpty():
            return None
        else:
            return self.queue.pop(0)
    def getNthOfQueue(self, n):
        if 0 <= n < len(self.queue) and not self.isEmpty():
            return self.queue[n]
        else:
            return None
    def getFirstOfQueue(self):
        return self.getNthOfQueue(0)
    def emptyQueue(self):
        self.queue = []
    def isEmpty(self):
        return self.queue == []
    def isFull(self):
        return self.maxItems != -1 and len(self.queue) == self.maxItems
    def __str__(self):
        return str(self.queue)

class MyClient(discord.Client):
    yt_process = None
    source = None
    playing_list = False
    playlistIds = []
    queue = YTSongQueue() # if all results --> FUTURE: CREATE QUEUE CLASS BECAUSE THIS IS BAD

    def getCommonVC(self, user):
        for vc in self.voice_clients:
            if vc.channel == user.channel:
                return vc
        return None

    def killPlayingProcess(self, vc):
        self.yt_process.kill()
        vc.stop()
        self.yt_process.wait()

    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
    
    async def on_message(self, message):
        print('Message from {0.author}: {0.content}'.format(message))
        command = message.content.split(" ")
        if (command[0] == "!help"):
            pass
        # Voice related commands
        voiceClient = self.getCommonVC(message.author.voice)
        if (command[0] == "!connect" and message.author.voice != None): # connect logic
            if (voiceClient):
                await self.voiceClient.move_to(message.author.voice.channel)
            else:
                await message.author.voice.channel.connect()
            await message.channel.send("Connected to " + str(message.author.voice.channel))
        if (voiceClient):
            if (command[0] == "!disconnect"): # disconnect logic
                self.queue.emptyQueue()
                if (voiceClient.is_playing() or voiceClient.is_paused()):
                    self.killPlayingProcess(voiceClient)
                await voiceClient.disconnect()
            if (command[0] == "!play"): # play music logic --> youtube supported NEED TO ADD PLAYLIST
                if (len(command) != 2): # add options
                    await message.channel.send("Usage: !play youtubeURL")
                    return
                #add to queue
                query_dict = parse_qs(urlparse(command[1]).query)
                if (query_dict.get("list")):
                    plId = query_dict.get("list")[0]
                    self.playing_list = True
                    urls, token = parseVideoUrls(fetchPlaylistData(plId)) 
                    self.queue.enqueue({"listId" : plId, "urls": urls, "nextPageToken": token})
                else:
                    self.queue.enqueue({"listId" : None, "urls": [command[1]], "nextPageToken": None})
                # return message 
                if (voiceClient.is_playing() or voiceClient.is_paused()):
                    await message.channel.send("Enqueued Song/List")
                    return
                else:
                    await message.channel.send("Playing Song")
                    try:
                        # CLEAN UP SUBROUTINE
                        def cleanup(error): # ALWAYS KILL THE PROCESS BEFORE KILLING THE VOICECLIENT
                            if (self.queue.isEmpty()):
                                return
                            self.yt_process.kill()
                            self.source.cleanup()
                            first = self.queue.getFirstOfQueue()
                            first["urls"].pop(0) # remove the song just played
                            if (len(first["urls"]) == 0): # no more urls
                                if (first["nextPageToken"] == None): # check next page
                                    self.queue.dequeue() # remove the item
                                    if self.queue.isEmpty(): # empty queue
                                        return
                                    else:
                                        first = self.queue.getFirstOfQueue()
                                else:
                                    urls, token = parseVideoUrls(fetchPlaylistData(first["listId"], nextPage=first["nextPageToken"])) 
                                    first["urls"] = urls
                                    first["nextPageToken"] = token
                            #spawn process
                            self.yt_process = subprocess.Popen(getYTDLArgs(first["urls"][0]), stdout=subprocess.PIPE)
                            self.source = discord.FFmpegOpusAudio(self.yt_process.stdout, pipe=True, options=FFMPEG_OPTIONS)
                            #play audio
                            voiceClient.play(self.source, after=cleanup)
                        # playing song
                        self.yt_process = subprocess.Popen(getYTDLArgs(self.queue.getFirstOfQueue()["urls"][0]), stdout=subprocess.PIPE)
                        self.source = discord.FFmpegOpusAudio(self.yt_process.stdout, pipe=True, options=FFMPEG_OPTIONS)
                        voiceClient.play(self.source, after=cleanup)
                    except discord.ClientException:
                        await message.channel.send("Error: playback error!")
                        return
            if (command[0] == "!stop"): # stop music logic
                if (voiceClient.is_playing() or voiceClient.is_paused()):
                    self.queue.emptyQueue()
                    self.killPlayingProcess(voiceClient)
                    await message.channel.send("Player stopped!")
            if (command[0] == "!pause"): # pause music logic
                if (voiceClient.is_playing()):
                    voiceClient.pause()
                    await message.channel.send("Song paused!")
            if (command[0] == "!resume"): # resume music logic
                if (voiceClient.is_paused()):
                    voiceClient.resume()
                    await message.channel.send("Song resumed!")
            if (command[0] == "!skip"):
                if (voiceClient.is_playing() or voiceClient.is_paused()):
                    self.killPlayingProcess(voiceClient)
                    await message.channel.send("Song skiped! Playing next song if possible...")
                else:
                    await message.channel.send("No Songs are playing!")
            if (command[0] == "!lq" or command[0] == "!listqueue"):
                if len(command) != 1 and len(command) != 2:
                    await message.channel.send("Usage: !listqueue [num]")
                    return
                if self.queue.isEmpty():
                    await message.channel.send("Song queue is empty!")
                    return
                prntnum = 5
                if (len(command) == 2):
                    prntnum = int(command[1])
                song_urls = []
                queuepos = 0
                while prntnum > 0:
                    queueData = self.queue.getNthOfQueue(queuepos)
                    if (queueData == None):
                        break
                    song_urls += queueData["urls"][:prntnum]
                    prntnum -= len(queueData["urls"])
                    queuepos += 1
                print(song_urls)
                embeds = parseSongData(fetchSongData(song_urls))
                for embed in embeds:
                    await message.channel.send(embed=embed)
        #loop function
        print(self.voice_clients, voiceClient, self.queue)

client = MyClient()
#client.run(env.str("BOT_TOKEN"))
client.run(BOT_SECRET)