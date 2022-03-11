from __future__ import unicode_literals
import youtube_dl
import sys
import os
import time

class MyLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def my_hook(d):
    if d['status'] == 'downloading':
        print("downloading")
        print(d["speed"])
    if d['status'] == 'finished':
        time.sleep(10)
    if d['status'] == 'error':
        pass

if (len(sys.argv) != 2):
    print("Usage: python yt.py URL")
    exit(1)

ydl_opts = {
    'format': 'worstaudio',
    'logger': MyLogger(),
    'progress_hooks': [my_hook],
    'ignoreerrors' : True,
    'quiet' : True,
    'outtmpl' : 'd.webm',
    'ratelimit' : 8000
}
with youtube_dl.YoutubeDL(ydl_opts) as ydl:
    ydl.download([sys.argv[1]])