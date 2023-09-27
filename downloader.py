import os
import shutil

import re
from math import ceil
import ffmpeg
import multiprocessing

from queue import Queue
from datetime import datetime
from pytube.exceptions import VideoUnavailable, PytubeError
from pytube import YouTube
import urllib.request

output_dir = os.getcwd() + '/videos'
process_count = multiprocessing.cpu_count()
cache_list = Queue()


# General utilities
class VideoTitleException(Exception):
    "Raised when a video title cannot be found."
    pass


def set_output_dir(_dir):
    global output_dir
    output_dir = _dir


def get_output_dir():
    global output_dir
    return output_dir


def print_video_names(filepath, add_url=False):
    videos = get_video_list(filepath)

    if not add_url:
        for url in videos:
            try:
                video_name = get_video_name(url)
                print(video_name)
            except Exception as e:
                print(e)
    else:
        for url in videos:
            try:
                video_name = get_video_name(url)
                print(f'"{video_name}": {url}')
            except Exception as e:
                print(f'{e}: {url}')


# Video downloading
def get_video_list(filepath):
    file = open(filepath, 'r', encoding='utf-8')
    file_data = file.read()
    file.close()
    return file_data.splitlines()


def download_video_i(yt, path):
    folder = output_dir + '/' + path
    try:
        video = yt.streams.filter(res='1080p', progressive=False).first()
        video.download(folder, 'vid_only.mp4')
    except: yt.streams.get_highest_resolution().download(folder, 'vid_only.mp4')

    try:
        audio = yt.streams.filter(abr='160kbps', progressive=False).first()
        audio.download(folder, 'aud_only.mp3')
    except:
        print(f'ERROR: No audio found for "{yt.title}"')


def format_video(path):
    # Do ffmpeg concat
    folder = output_dir + '/' + path
    vid_out = ffmpeg.input(folder + '/vid_only.mp4')
    aud_out = ffmpeg.input(folder + '/aud_only.mp3')
    out_path = folder + '/vid.mp4'

    try:
        ffmpeg.output(vid_out, aud_out, out_path).run(overwrite_output=True, quiet=True)
        os.remove(folder + '/vid_only.mp4')
        os.remove(folder + '/aud_only.mp3')
        return True
    except ffmpeg.Error:
        print(f'ERROR: FFMPEG formatting failed for "{path}" ({out_path})')
        return False


def download_image(url, path):
    new_url = re.sub('(sddefault|hqdefault)', 'maxresdefault', url)
    full_path = output_dir + '/' + path + '/thumb.png'
    try: img = urllib.request.urlretrieve(new_url, full_path)
    except urllib.error.HTTPError:
        img = urllib.request.urlretrieve(url, full_path)


# Text parsing
def write_description(contents, path):
    full_path = output_dir + '/' + path + '/desc.txt'
    file = open(full_path, 'w', encoding='utf-8')
    file.write(contents)
    file.close()


def write_title(contents, path):
    full_path = output_dir + '/' + path + '/title.txt'
    file = open(full_path, 'w', encoding='utf-8')
    file.write(contents)
    file.close()


def parse_title(title):
    new_title = re.sub('["*\\/\'.|?:<>!()+,.\\[\\]]', '', title)
    return re.sub('[ ]+', '_', new_title)


def parse_time(time_string):
    tstr = str(time_string)
    dt = datetime.strptime(tstr, '%Y-%m-%d %H:%M:%S')
    return dt.strftime('%B %m, %Y')


def parse_description(desc):
    if len(desc) == 0: return 'No description.'
    else: return 'Original description:\n{}'.format(desc)


# Video downloading
def download_video(url):
    try:
        yt_title = get_video_name(url)
        yt = YouTube(url)
    except VideoTitleException as e:
        print(f'WARNING: {url} status {e}. Skipping.')
        return
    except VideoUnavailable:
        print(f'WARNING: {url} could not be opened. Skipping.')
        return

    title = parse_title(yt_title)
    vdir = output_dir + '/' + title
    # Only run if folder does not exist
    if not os.path.exists(vdir):
        print(f'{yt_title}')
        date = parse_time(yt.publish_date)
        desc = parse_description(yt.description)

        os.mkdir(vdir)
        download_image(yt.thumbnail_url, title)

        write_description(f'Uploaded on {date}\n{desc}\n', title)
        write_title(yt_title, title)
        download_video_i(yt, title)

        if not format_video(title):
            shutil.rmtree(vdir)
            return
    cache_list.put(url)


def get_video_name(url, count=3):
    if count:
        try:
            yt = YouTube(url)
            return yt.title
        except VideoUnavailable:
            raise Exception('[Unavailable]')
        except PytubeError:
            return get_video_name(url, count - 1)
    else: Exception('[Error]')


# Multicore implementation
def download_list(video_list):
    for url in video_list:
        try: download_video(url)
        except Exception as e:
            try: name = get_video_name(url)
            except: name = url
            print(f'ERROR: {e} for "{name}"')


def get_video_lists(filepath):
    lines = get_video_list(filepath)
    # Split lines
    split_lines = list()
    chunk_size = ceil(len(lines) / process_count)
    for i in range(0, len(lines), chunk_size):
        split_lines.append(lines[i : i + chunk_size])
    return split_lines


def download_from_file(filepath='videos.txt'):
    clear_bad_dirs()

    jobs = []
    lists = get_video_lists(filepath)

    # Add jobs to process list
    print(f'Process count: {len(lists)}')
    for i in range(len(lists)):
        process = multiprocessing.Process(
            target=download_list,
            args=(lists[i], )
        )
        jobs.append(process)

    # Wait for processes to finish
    try:
        for j in jobs: j.start()
        for j in jobs: j.join()
        print('Downloading done.')
    except:
        print('Something went wrong. Exiting.')


# Filesystem utilities
def get_output_subdirs():
    folder_path = get_output_dir()
    subfolders = [str(f.path) for f in os.scandir(folder_path) if f.is_dir()]
    return subfolders


def clear_bad_dirs():
    subfolders = get_output_subdirs()

    for dir in subfolders:
        if not os.path.exists(dir + '/vid.mp4'):
            shutil.rmtree(dir)


def set_cache():
    pass


def cleanup_dirs():
    clear_bad_dirs()
    subfolders = get_output_subdirs()
    filtered = list(filter(lambda _dir: os.path.exists(_dir + '/uploaded'), subfolders))

    to_folder = os.getcwd() + '\\uploaded\\'

    for dir in filtered:
        stem = os.path.split(dir)[1]
        new_dir = to_folder + stem
        shutil.move(dir, new_dir)
