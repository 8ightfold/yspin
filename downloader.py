import os
import re
from math import ceil
import ffmpeg
import multiprocessing

from datetime import datetime
from pytube import YouTube
import urllib.request

output_dir = os.getcwd() + '/videos'
process_count = multiprocessing.cpu_count()


def set_output_dir(_dir):
    global output_dir
    output_dir = _dir


def get_output_dir():
    return output_dir


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


def write_description(contents, path):
    full_path = output_dir + '/' + path + '/desc.txt'
    file = open(full_path, 'w')
    file.write(contents)
    file.close()


def write_title(contents, path):
    full_path = output_dir + '/' + path + '/title.txt'
    file = open(full_path, 'w')
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


def download_video(url):
    yt = YouTube(url)
    title = parse_title(yt.title)
    date = parse_time(yt.publish_date)
    desc = parse_description(yt.description)

    vdir = output_dir + '/' + title
    # Only run if folder does not exist
    if not os.path.exists(vdir):
        print(f'{yt.title}')
        os.mkdir(vdir)
        download_image(yt.thumbnail_url, title)

        write_description(f'Uploaded on {date}\n{desc}\n', title)
        write_title(yt.title, title)
        download_video_i(yt, title)
        if not format_video(title):
            os.rmdir(vdir)


def download_list(video_list):
    for video in video_list:
        try: download_video(video)
        except: print(f'ERROR: Parsing failed for {video}')


def get_video_lists(filepath):
    file = open(filepath, 'r')
    file_data = file.read()
    lines = file_data.splitlines()
    file.close()
    # Split lines
    split_lines = list()
    chunk_size = ceil(len(lines) / process_count)
    for i in range(0, len(lines), chunk_size):
        split_lines.append(lines[i : i + chunk_size])
    return split_lines


def download_from_file(filepath='videos.txt'):
    jobs = []
    lists = get_video_lists(filepath)

    # Add jobs to process list
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