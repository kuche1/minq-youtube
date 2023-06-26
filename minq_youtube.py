#! /usr/bin/env python3

import argparse
import pytube # paru python-pytube
#import climage # paru python-climage
import requests
import tempfile
import datetime
import yt_dlp # paru yt-dlp
import subprocess
import minq_caching_thing; mct = minq_caching_thing.Minq_caching_thing()
import urllib
import sys
import json
import os
import threading
import time

################################# settings - variables

SETTINGS_FOLDER = os.path.expanduser('~/.config/minq-youtube')

SETTING_VIU_THUMB_WIDTH_NAME = 'viu-thumb-width'
SETTING_VIU_THUMB_WIDTH_DEFAULT_VALUE = 80

SETTING_CACHE_VALIDITY_NAME = 'cache-validity'
SETTING_CACHE_VALIDITY_DEFAULT_VALUE = 60 * 60 * 2 # 2 hours

################################# classes

class Ytdlp_silent_logger:
    def error(msg):
        pass
    def warning(msg):
        pass
    def debug(msg):
        pass

################################# settings - functions

def del_setting(name):
    file = os.path.join(SETTINGS_FOLDER, name)
    os.remove(file)

def set_setting_str(name, value):
    file = os.path.join(SETTINGS_FOLDER, name)
    os.makedirs(os.path.dirname(file), exist_ok=True)

    with open(file, 'w') as f:
        f.write(value)

def get_setting_str(name, default_value):
    file = os.path.join(SETTINGS_FOLDER, name)
    os.makedirs(os.path.dirname(file), exist_ok=True)

    if not os.path.isfile(file):
        set_setting_str(name, default_value)
    
    with open(file, 'r') as f:
        return f.read()

def get_setting_int(name, default_value):
    value = get_setting_str(name, str(default_value))

    try:
        return int(value)
    except ValueError:
        pass

    file = os.path.join(SETTINGS_FOLDER, name)
    slow_print(f'setting `{name}` located at `{file}` has invalid value `{value}`; overwriting with new value - `{default_value}`')

    with open(file, 'w') as f:
        f.write(str(default_value))

    return get_setting_int(name, default_value)

################################# IO

def print_image(path):

    width = get_setting_int(SETTING_VIU_THUMB_WIDTH_NAME, SETTING_VIU_THUMB_WIDTH_DEFAULT_VALUE)
    term(['viu', '--width', str(width), '--', path])
    print() # leve an empty line since wezterm is acting like a piece of shit otherwise

    if False:
        image_data = climage.convert(
            path,
            is_unicode=True,
            is_truecolor=True, is_256color=False, is_8color=False,
            width=CLIMAGE_THUMB_SIZE,
            # palette : Sets mapping of RGB colors scheme to system colors. Options are : [“default”, “xterm”, “linuxconsole”, “solarized”, “rxvt”, “tango”, “gruvbox”, “gruvboxdark”]. Default is “default”.
        )

        print(image_data)

def slow_print(*a, **kw):
    print(*a, **kw)
    input('press enter')

def play_video(file):
    term(['mpv', '--', file], silent=True, detach=True)

################################# internet


def error_no_cache_no_internet(url):
    print(f'ERROR: no internet + content not cached: `{url}`')
    sys.exit(1)

def get_cached_url(url, return_path):
    content = mct.get_url(url, return_path=return_path)
    if content == None:
        error_no_cache_no_internet(url)
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

################################# else

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

################################# main

def settings_menu():
    CMD_ALL = []
    CMD_ALL += [CMD_CHANGE := ['change', 'set']]
    CMD_ALL += [CMD_DELETE := ['delete', 'del']]
    CMD_ALL += [CMD_EXIT := ['exit', 'e']]
    CMD_ALL += [CMD_LIST := ['list', 'ls']]

    while True:
        act = input('Enter action > ')

        if act in CMD_CHANGE:
            name = input('Enter setting name > ')
            value = input('Enter new value > ')
            set_setting_str(name, value)

        elif act in CMD_DELETE:
            name = input('Enter setting name > ')
            del_setting(name)

        elif act in CMD_EXIT:
            break

        elif act in CMD_LIST:
            for (path,folders,files) in os.walk(SETTINGS_FOLDER):
                for file in files:
                    path_to_setting = os.path.join(path, file)
                    name = path_to_setting[len(SETTINGS_FOLDER):]
                    if name.startswith('/'): # hacky but works
                        name = name[1:]
                    print(f'name: `{name}` ; value: `{get_setting_str(path_to_setting, "unreachable")}`')

        else:
            print(f'unknown action: `{act}`')
            print('available actions:')
            for c in CMD_ALL:
                print(f'\t{c}')
            slow_print()

def interactive_youtube_browser(search_term):

    yt_dlp_options = {
        'quiet': True,
        'logger': Ytdlp_silent_logger,
    }
    ytdl = yt_dlp.YoutubeDL(yt_dlp_options)

    print(f'searching for `{search_term}`...')
    search = pytube.Search(search_term)

    cache_url = 'pytube-search-with-timestamp://' + search_term

    refresh = True
    cached = mct.get_url(cache_url, return_path=False)
    if cached != None:
        cache_time, cache_data = json.loads(cached)
        now = time.time()
        cache_validity = get_setting_int(SETTING_CACHE_VALIDITY_NAME, SETTING_CACHE_VALIDITY_DEFAULT_VALUE)
        if abs(now - cache_time) < cache_validity: # taking into account systems with fucked up clock
            refresh = False

    if refresh:
        try:
            results = search.results
        except urllib.error.URLError:
            if cached == None:
                error_no_cache_no_internet(cache_url)
            video_urls = cache_data
        else:
            video_urls = [video.watch_url for video in results]
            data_to_cache = [time.time(), video_urls]
            mct.cache_url(cache_url, json.dumps(data_to_cache), blocking=False)
    else:
        video_urls = cache_data

    cur_item_idx = 0
    while True:
        if cur_item_idx < 0:
            cur_item_idx = 0

        elif cur_item_idx >= len(video_urls):
            slow_print('no more results to show')
            cur_item_idx -= 1
            continue

        video_url = video_urls[cur_item_idx]

        cache_url = 'yt-dlp-video-info://' + video_url
        try:
            video_info = ytdl.extract_info(video_url, download=False) # TODO this takes too much time, let's use the cached version instead if available ; mby cache the time as well and determine if restart is needed
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
        views = video_info['view_count']
        categories = video_info['categories']
        tags = video_info['tags']
        thumb_url = video_info['thumbnail']

        try: likes = video_info['like_count']
        except KeyError: likes = -1

        y3,y2,y1,y0,m1,m0,d1,d0 = upload_date
        upload_year = y3 + y2 + y1 + y0
        upload_month = m1 + m0
        upload_day = d1 + d0

        thumb_file = download_file(thumb_url)

        print()
        print(f'title   : {title}')
        print(f'uploader: {uploader}')
        print(f'duration: {duration}')
        print(f'uploaded: {upload_year} {upload_month} {upload_day}')

        #print(f'url     : {video_url}')
        #print(f'thumb   : {thumb_file}')
        print_image(thumb_file)

        cmd = input('> ')

        CMD_ALL = []
        CMD_ALL += [CMD_CATEGORIES := ['categories']]
        CMD_ALL += [CMD_DOWNLOAD := ['download']]
        CMD_ALL += [CMD_EXIT := ['exit', 'e']]
        CMD_ALL += [CMD_NEXT := ['next', 'n', '']]
        CMD_ALL += [CMD_PLAY := ['play']]
        CMD_ALL += [CMD_PREV := ['prev', 'p']]
        CMD_ALL += [CMD_SEARCH := ['search']]
        CMD_ALL += [CMD_SETTINGS := ['settings', 'setting', 'set']]
        CMD_ALL += [CMD_TAGS := ['tags']]
        CMD_ALL += [CMD_THUMB := ['thumb']]
        CMD_ALL += [CMD_URL := ['url']]

        if cmd in CMD_CATEGORIES:
            slow_print(categories)

        elif cmd in CMD_DOWNLOAD:
            video_file = download_video(video_url)

        elif cmd in CMD_EXIT:
            break

        elif cmd in CMD_NEXT:
            cur_item_idx += 1

        elif cmd in CMD_PLAY:
            video_file = download_video(video_url)
            play_video(video_file)

        elif cmd in CMD_PREV:
            cur_item_idx -= 1

        elif cmd in CMD_SEARCH:
            term = input('Enter search term > ')
            return interactive_youtube_browser(term)

        elif cmd in CMD_SETTINGS:
            settings_menu()

        elif cmd in CMD_TAGS:
            slow_print(tags)

        elif cmd in CMD_THUMB:
            slow_print(thumb_file)

        elif cmd in CMD_URL:
            slow_print(video_url)

        else:
            print(f'unknown command: `{cmd}`')
            print('available commands:')
            for c in CMD_ALL:
                print(f'\t{c}')
            slow_print()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Command line port of youtube')
    parser.add_argument('search_term', help='Term to search for')
    args = parser.parse_args()

    interactive_youtube_browser(args.search_term)
