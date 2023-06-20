#! /usr/bin/env python3

import argparse
import pytube # paru python-pytube
import climage # paru python-climage
import requests
import tempfile
import datetime
import yt_dlp
import subprocess
#os.path.insert('../minq-caching-thing')
import minq_caching_thing; mct = minq_caching_thing.Minq_caching_thing()
import urllib
import sys
import json
import os
import threading

THUMB_SIZE = 80

class Ytdlp_silent_logger:
    def error(msg):
        #print("Captured Error: "+msg)
        pass
    def warning(msg):
        #print("Captured Warning: "+msg)
        pass
    def debug(msg):
        #print("Captured Log: "+msg)
        pass

def slow_print(*a, **kw):
    print(*a, **kw)
    input('press enter')

def term(cmds:list, silent=False, detach=False):
    kwargs = {'check': True}

    if silent:
        kwargs['stdout'] = subprocess.DEVNULL
        kwargs['stderr'] = subprocess.DEVNULL

    thr = threading.Thread(target=subprocess.run, args=[cmds], kwargs=kwargs)
    thr.start()

    if not detach:
        thr.join()

def get_temp_file_name():
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
        return f.name

def get_cached_url(url, return_path):
    content = mct.get_url(url, return_path=return_path)
    if content == None:
        print(f'ERROR: no internet + content not cached: `{url}`')
        sys.exit(1)
    return content

def download_file(url):
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'}
    try:
        page = requests.get(url, headers=headers)
    except requests.exceptions.ConnectionError:
        return get_cached_url(url, return_path=True)

    assert page.ok
    file_data = page.content

    mct.cache_url(url, file_data, blocking=True)
    return mct.get_url(url, return_path=True)

def download_video(url):
    cached_url = 'yt-dlp://' + url

    cached_file = mct.get_url(cached_url, return_path=True)
    if cached_file != None:
        return cached_file

    resulting_file = get_temp_file_name() + '.webm'

    ytdl_format_options = {
        #'format': 'bestaudio/best',
        'outtmpl': resulting_file,
        'noplaylist': True,
        'nocheckcertificate': True,
        #'ignoreerrors': False,
        #'logtostderr': False,
        #'quiet': True,
        #'no_warnings': True,
        #'default_search': 'auto',
        #'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
    }
    ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
    ytdl.download(url)
    #resulting_file = ytdl.prepare_filename(ytdl.extract_info(url, download=True))

    with open(resulting_file, 'rb') as f:
        mct.cache_url(cached_url, f.read(), blocking=False)

    return resulting_file

def play_video(file):
    term(['mpv', '--', file], silent=True, detach=True)

def interactive_youtube_browser(search_term):
    yt_dlp_options = {
        'quiet': True,
        'logger': Ytdlp_silent_logger,
    }
    ytdl = yt_dlp.YoutubeDL(yt_dlp_options)

    print(f'searching for `{search_term}`...')

    search = pytube.Search(search_term)

    cache_url = 'pytube-search://' + search_term

    try:
        results = search.results # TODO somehow avoid this and only use the bottom one
    except urllib.error.URLError:
        cached = get_cached_url(cache_url, return_path=False)
        video_urls = json.loads(cached)
    else:
        video_urls = [video.watch_url for video in results]

        mct.cache_url(cache_url, json.dumps(video_urls), blocking=False)

    cur_item_idx = 0
    while True:
        if cur_item_idx < 0:
            cur_item_idx = 0

        elif cur_item_idx >= len(video_urls):
            print('getting more results...')
            results = search.get_next_results()
            video_urls += [video.watch_url for video in results] # TODO is it possible that this returns an empty list?

        video_url = video_urls[cur_item_idx]

        cache_url = 'yt-dlp-video-info://' + video_url
        try:
            video_info = ytdl.extract_info(video_url, download=False)
        except yt_dlp.utils.DownloadError:
            video_info = get_cached_url(cache_url, return_path=False)
            video_info = json.loads(video_info)
        else:
            mct.cache_url(cache_url, json.dumps(video_info))

        title = video_info['fulltitle'] # video_info['title']
        description = video_info['description']
        uploader = video_info['uploader']
        duration = video_info['duration_string'] # video_info['duration']
        upload_date = video_info['upload_date'] # video_info['release_date'] is not always defined
        likes = video_info['like_count']
        views = video_info['view_count']
        categories = video_info['categories']
        tags = video_info['tags']
        thumb_url = video_info['thumbnail']

        y3,y2,y1,y0,m1,m0,d1,d0 = upload_date
        upload_year = y3 + y2 + y1 + y0
        upload_month = m1 + m0
        upload_day = d1 + d0

        thumb_file = download_file(thumb_url)
        thumb_data = climage.convert(
            thumb_file,
            is_unicode=True,
            is_truecolor=True, is_256color=False, is_8color=False,
            width=THUMB_SIZE,
            # palette : Sets mapping of RGB colors scheme to system colors. Options are : [“default”, “xterm”, “linuxconsole”, “solarized”, “rxvt”, “tango”, “gruvbox”, “gruvboxdark”]. Default is “default”.
        )

        print()
        print(f'title   : {title}')
        print(f'uploader: {uploader}')
        print(f'duration: {duration}')
        print(f'uploaded: {upload_year} {upload_month} {upload_day}')

        #print(f'url     : {video_url}')
        #print(f'thumb   : {thumb_file}')
        print(thumb_data)

        cmd = input('> ')

        match cmd:
            case 'categories':
                slow_print(categories)

            case 'download':
                video_file = download_video(video_url)

            case 'exit':
                break

            case 'next' | 'n' | '':
                cur_item_idx += 1

            case 'play':
                video_file = download_video(video_url) # TODO this is cancer
                play_video(video_file)

            case 'prev' | 'p':
                cur_item_idx -= 1

            case 'search':
                term = input('Enter search term > ')
                return interactive_youtube_browser(term)

            case 'tags':
                slow_print(tags)

            case 'thumb':
                slow_print(thumb_file)

            case 'url':
                slow_print(video_url)

            case other:
                slow_print(f'unknown command: `{cmd}`')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Command line port of youtube')
    parser.add_argument('search_term', help='String to search for')
    args = parser.parse_args()

    interactive_youtube_browser(args.search_term)
