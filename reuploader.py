import json
import re
import time
import os.path

from pytube import Channel
from playwright.sync_api import sync_playwright
from downloader import get_output_dir

did_upload = False


class FileNotFoundException(Exception):
    "Raised when a file needed for reuploading is not found."
    pass


def wait_for(seconds):
    start = time.time()
    while time.time() - start < seconds:
        pass


def write_file(name, contents):
    insert_contents = str(contents).encode('utf-8', 'ignore')
    file = open(name, 'w', encoding='utf-8')
    file.write(str(insert_contents))
    file.close()


def read_file(name):
    file = open(name, 'r', encoding='utf-8')
    contents = file.read()
    file.close()
    return contents


def read_alternates(_dict, first, second):
    try: return _dict[first]
    except KeyError:
        try: return _dict[second]
        except: print('Invalid keys found in dictionary')


def parse_json(file):
    file = open(file, 'r', encoding='utf-8')
    contents = file.read()
    file.close()

    json_data = json.loads(contents)
    link = read_alternates(json_data, 'link', 'channel')
    username = read_alternates(json_data, 'username', 'user')
    password = read_alternates(json_data, 'password', 'pass')

    return link, username, password


def get_page_link(channel_link):
    if re.match('.*(?:www.youtube.com)\\/channel\\/.+', channel_link):
        return re.sub('www', 'studio', channel_link)
    else: return 'https://studio.youtube.com/channel/' + channel_link


def youtube_login(page, link, username, password):
    page.goto(link)

    # Login with username
    page.wait_for_selector('input[type="email"]')
    page.type('input[type="email"]', username)
    page.click('#identifierNext')
    # Login with password
    page.wait_for_selector('input[type="password"]')
    page.type('input[type="password"]', password)
    page.click('#passwordNext')
    page.wait_for_selector('text=Your channel')


def file_chooser_fn(page, element, filepath):
    with page.expect_file_chooser() as fc_prom:
        page.wait_for_selector(element)
        page.click(element)
    file_chooser = fc_prom.value
    file_chooser.set_files(filepath)


def close_secondary_dialog(page):
    if page.locator('ytcp-button[id="close-button"]').count() == 1:
        page.click('ytcp-button[id="close-button"]')
    # Specific options
    elif page.locator('#close-button.ytcp-uploads-still-processing-dialog').count():
        page.click('#close-button.ytcp-uploads-still-processing-dialog')
    elif page.locator('#close-button.ytcp-video-share-dialog').count():
        page.click('#close-button.ytcp-video-share-dialog')
    else:
        print("WARNING: Secondary dialog box could not be closed, last upload may fail")
        page.reload()


def except_upload_limit_reached(page):
    error_element = page.locator('#error-message.error-details.ytcp-uploads-dialog')
    if error_element.is_visible() or error_element.is_enabled():
        raise Exception('Daily upload limit reached.')


def add_screenshot(page, name):
    filepath = 'screenshots/' + name + '.png'
    page.screenshot(path=filepath)


def check_filepath(filepath):
    if not os.path.exists(filepath):
        folder = os.path.dirname(filepath)
        filename = os.path.split(filepath)[1]
        print(f'WARNING: Could not locate "{filename}" in {folder}. Skipping.')
        raise FileNotFoundException


def upload_from_folder(page, folder, time=0):
    # Check if video has been uploaded
    if os.path.exists(folder + '/uploaded') or os.path.exists(folder + '/noupload'): return

    # Get files
    video_file = folder + '/vid.mp4'
    thumbnail_file = folder + '/thumb.png'
    title_file = folder + '/title.txt'

    # Check path validity
    check_filepath(video_file)
    check_filepath(thumbnail_file)
    check_filepath(title_file)

    title = read_file(title_file)
    description = read_file(folder + '/desc.txt')
    visibility = 'PUBLIC'

    if not os.path.exists(video_file):
        print(f'ERROR: Could not find required file for {folder}')
        with open(folder + '/noupload', 'w') as f: f.close()
        return

    print(f'{title}')
    # Open upload menu
    page.wait_for_selector('ytcp-button[id="create-icon"]')
    page.click('ytcp-button[id="create-icon"]')
    page.wait_for_selector('tp-yt-paper-item[id="text-item-0"]')
    page.click('tp-yt-paper-item[id="text-item-0"]')

    # Upload video
    file_chooser_fn(page, 'ytcp-button[id="select-files-button"]', video_file)
    page.wait_for_selector('h1[class="style-scope ytcp-uploads-dialog"]')
    add_screenshot(page, 'upload_page')
    #except_upload_limit_reached(page)

    # Set upload
    global did_upload
    did_upload = True

    # Add title and description
    text_inputs = page.locator('#input')
    if text_inputs.first.locator('div[id="textbox"]').count():
        text_inputs.first.locator('div[id="textbox"]').fill(title)
    else: text_inputs.all()[1].locator('div[id="textbox"]').fill(title)
    text_inputs.last.locator('div[id="textbox"]').fill(description)

    # Add thumbnail
    if os.path.exists(thumbnail_file):
        with page.expect_file_chooser() as file_chooser_promise:
            page.locator('.remove-default-style.style-scope.ytcp-thumbnails-compact-editor-uploader-old').click()
        file_chooser = file_chooser_promise.value
        file_chooser.set_files(thumbnail_file)
    else:
        print(f'WARNING: Thumbnail for {title} could not be found.')

    # Mark as not for kids
    page.click('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]')
    page.wait_for_selector('#step-badge-3')
    page.click('#step-badge-3')

    # Set visibility
    page.wait_for_selector(f'tp-yt-paper-radio-button[name="{visibility}"]')
    page.click(f'tp-yt-paper-radio-button[name="{visibility}"]')

    # Close page
    page.click('#done-button.ytcp-uploads-dialog')
    wait_for(4)
    close_secondary_dialog(page)
    with open(folder + '/uploaded', 'w') as f: f.close()


def get_folders():
    # Get valid folders
    folder_path = get_output_dir()
    subfolders = [str(f.path) for f in os.scandir(folder_path) if f.is_dir()]
    filtered = list(
        filter(lambda _dir: not (os.path.exists(_dir + '/uploaded') or os.path.exists(_dir + '/noupload')), subfolders)
    )
    return filtered


def get_folder_lists():
    filtered = get_folders()
    # Chunk lists
    chunked = []
    for i in range(0, len(filtered), 3):
        chunked.append(filtered[i : i + 3])
    return chunked


def wait_if_uploaded():
    global did_upload
    if did_upload:
        input('Waiting...')


def upload_to_channel(file='secrets.json'):
    (link, username, password) = parse_json(file)
    studio_page = get_page_link(link)
    video_folders = get_folders()
    c = Channel(link)
    print(f'Posting to "{c.channel_name}"')

    try:
        with sync_playwright() as p:
            browser_type = p.firefox
            browser = browser_type.launch()
            page = browser.new_page()
            youtube_login(page, studio_page, username, password)

            for folder in video_folders:
                try: upload_from_folder(page, folder)
                except FileNotFoundException: pass

            print('Done.')
            wait_if_uploaded()
            page.close(run_before_unload=True)
            browser.close()
    except Exception as e:
        print(f'ERROR: {e}')
        wait_if_uploaded()
