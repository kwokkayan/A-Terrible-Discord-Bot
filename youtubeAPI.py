import requests

API_KEY = "AIzaSyCBw1d8pXHmrwIdMEE3OlS5MQ0QW-3oXo0"
YTAPI_URL = "https://www.googleapis.com/youtube/v3/playlistItems"

def main():
    r = requests.get(YTAPI_URL, params={
        "key" : API_KEY,
        "part" : "contentDetails",
        "maxResults" : 50,
        "playlistId" : "PLf0Hf-yykj0bAeTeZIMRTuD1-BOpQek-X"
    })
    res = r.json()
    urls = []
    for item in res["items"]:
        urls.append("https://www.youtube.com/watch?v=" + item["contentDetails"]["videoId"])
    print(urls)

if __name__ == "__main__":
    main()