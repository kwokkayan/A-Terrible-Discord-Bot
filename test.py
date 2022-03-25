from dis import disco
from re import sub
import discord
from discord.ext import commands
import subprocess
import sys
import os
from environs import Env
from urllib.parse import urlparse, parse_qs
import requests
import re

import youtube_dl
# REMEBER TO CHANGE
env = Env()
env.read_env()
BOT_SECRET = env.str("BOT_SECRET")
API_KEY = env.str("API_KEY")
YTAPI_URL = "https://www.googleapis.com/youtube/v3/"
#FILTER = "-filter_complex \"acrossover=split=1200 6000[LOW][MID][HIGH];[LOW]volume=1.1[VLOW];[MID]volume=1.05[VMID];[HIGH]volume=1.0[VHIGH];[VLOW]aformat=sample_fmts=s16:channel_layouts=stereo[OLOW];[VMID]aformat=sample_fmts=s16:channel_layouts=stereo[OMID];[VHIGH]aformat=sample_fmts=s16:channel_layouts=stereo[OHIGH];[OLOW][OMID][OHIGH]amerge=inputs=3\""
#FILTER = "-filter_complex \"crystalizer=i=1.15\""
FFMPEG_OPTIONS = "-ar 48000 -b:a 128k "
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
        # format time string -- very messy
        timestr = item["contentDetails"]["duration"]
        timearr = ["{:0>2s}".format(s) for s in re.split('[A-Z]', timestr[2:len(timestr)-1])]
        out = ':'.join(timearr)
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

class VoiceChannelCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = YTSongQueue()
        self.yt_process = None
        self.source = None

    def killPlayingProcess(self, vc):
        self.yt_process.kill()
        vc.stop()
        self.yt_process.wait()

    def getGuildVoiceClient(self, guildVCs):
        for vc in self.bot.voice_clients:
            for g_vc in guildVCs:
                if vc.channel == g_vc:
                   return vc
        return None 

    def getCommonVC(self, user):
        for vc in self.bot.voice_clients:
            if vc.channel == user.channel:
                return vc
        return None

    @commands.Cog.listener()
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.bot.user))
        
    @commands.Cog.listener()
    async def on_message(self, message):
        pass

    @commands.command()
    async def connect(self, ctx):
        vc = ctx.author.voice
        common_vc = self.getGuildVoiceClient(ctx.guild.voice_channels)
        if vc == None:
            await ctx.send("Please connect to a voice channel.")
        elif self.getCommonVC(vc):
            await ctx.send("Already connected.")
        elif common_vc:
            await common_vc.move_to(vc.channel)
            await ctx.send("Connected to " + str(vc.channel))
        else:
            await vc.channel.connect()
            await ctx.send("Connected to " + str(vc.channel))

    @commands.command()
    async def disconnect(self, ctx):
        common_vc = self.getGuildVoiceClient(ctx.guild.voice_channels)
        if common_vc:
            if common_vc.is_playing() or common_vc.is_paused():
                self.queue.emptyQueue()
                self.killPlayingProcess(common_vc)
            await common_vc.disconnect()
            await ctx.send("Disconnected")
        else:
            await ctx.send("No channel to disconnect from")

    @commands.command()
    async def play(self, ctx, *args):
        if len(args) == 0:
            await ctx.send("Usage: !play youtubeURL [OPTIONS]")
        common_vc = self.getGuildVoiceClient(ctx.guild.voice_channels)
        if not common_vc:
            await ctx.send("Not connected to any channels!")
            return
        # parse url
        query_dict = parse_qs(urlparse(args[0]).query)
        if (query_dict.get("list")):
            plId = query_dict.get("list")[0]
            self.playing_list = True
            urls, token = parseVideoUrls(fetchPlaylistData(plId)) 
            self.queue.enqueue({"listId" : plId, "urls": urls, "nextPageToken": token})
        else:
            self.queue.enqueue({"listId" : None, "urls": [args[0]], "nextPageToken": None})
        if (common_vc.is_playing() or common_vc.is_paused()):
            await ctx.send("Enqueued Song/List")
            return
        else:
            await ctx.send("Playing Song")
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
                    self.yt_process = subprocess.Popen(getYTDLArgs(first["urls"][0]), bufsize=3840, stdout=subprocess.PIPE)
                    self.source = discord.FFmpegOpusAudio(self.yt_process.stdout, pipe=True, options=FFMPEG_OPTIONS)
                    #play audio
                    common_vc.play(self.source, after=cleanup)
                # playing song
                self.yt_process = subprocess.Popen(getYTDLArgs(self.queue.getFirstOfQueue()["urls"][0]), bufsize=3840, stdout=subprocess.PIPE)
                self.source = discord.FFmpegOpusAudio(self.yt_process.stdout, pipe=True, options=FFMPEG_OPTIONS)
                common_vc.play(self.source, after=cleanup)
            except discord.ClientException:
                await ctx.send("Error: playback error!")

    @commands.command()
    async def stop(self, ctx):
        common_vc = self.getGuildVoiceClient(ctx.guild.voice_channels)
        if not common_vc:
            await ctx.send("Not connected to any channels!")
        elif common_vc.is_playing() or common_vc.is_paused():
            self.queue.emptyQueue()
            self.killPlayingProcess(common_vc)
            await ctx.send("Stopped playing music")
    
    @commands.command()
    async def pause(self, ctx):
        common_vc = self.getGuildVoiceClient(ctx.guild.voice_channels)
        if not common_vc:
            await ctx.send("Not connected to any channels!")
        elif common_vc.is_playing():
            common_vc.pause()
            await ctx.send("Music paused")
        else:
            await ctx.send("Invalid music command!")

    @commands.command()
    async def resume(self, ctx):
        common_vc = self.getGuildVoiceClient(ctx.guild.voice_channels)
        if not common_vc:
            await ctx.send("Not connected to any channels!")
        elif common_vc.is_paused():
            common_vc.resume()
            await ctx.send("Music resumed")
        else:
            await ctx.send("Invalid music command!")

    @commands.command()
    async def skip(self, ctx):
        common_vc = self.getGuildVoiceClient(ctx.guild.voice_channels)
        if not common_vc:
            await ctx.send("Not connected to any channels!")
        elif common_vc.is_paused() or common_vc.is_playing():
            self.killPlayingProcess(common_vc)
            await ctx.send("Music skipped!")
        else:
            await ctx.send("Invalid music command!")

    @commands.command()
    async def listqueue(self, ctx):
        if self.queue.isEmpty():
            await ctx.send("Song queue is empty!")
            return
        prntnum = 5
        song_urls = []
        queuepos = 0
        while prntnum > 0:
            queueData = self.queue.getNthOfQueue(queuepos)
            if (queueData == None):
                break
            song_urls += queueData["urls"][:prntnum]
            prntnum -= len(queueData["urls"])
            queuepos += 1
        embeds = parseSongData(fetchSongData(song_urls))
        for embed in embeds:
            await ctx.send(embed=embed)

client = commands.Bot(command_prefix="!")
client.add_cog(VoiceChannelCommand(client))
client.run(env.str("BOT_SECRET"))