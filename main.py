from downloader import download_from_file, set_output_dir
from reuploader import upload_to_channel


if __name__ == "__main__":
    download_from_file('videos.txt')
    upload_to_channel()
