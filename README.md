# yspin
This library is a little Youtube video handler that I wrote for archiving videos. You can download videos from Youtube into folders, and then parse these folders and reupload them to a single channel. 

Yspin requires ``ffmpeg``, ``pytube``, ``urllib``, and ``playwright``. 

## Usage
### Downloading
To download a list of videos, you must create a text file with all the links you need. Be sure each link is on its own line, and that you do not have blank lines. You can then pass the filepath into ``download_from_file``, or if it's in the current directory and named ``videos.txt``, you can call the function with no arguments. The program will then spawn many processes, each downloading a chunk of links from Youtube. Be sure you have a ``__main__``, with any functions that must be called for each process being out of ``__main__``, and any that should not be called being inside of it.

Here is an example of a list of videos:
```
https://www.youtube.com/watch?v=kJQP7kiw5Fk
https://www.youtube.com/watch?v=LECSVlc6O1g
https://www.youtube.com/watch?v=JGwWNGJdvx8
```

You will now have a bunch of subfolders with the following format:
```
videos 
└─── Video_name_1
│   │──   desc.txt
│   │──   thumb.png
│   │──   title.txt
│   \──   vid.mp4
│   ...
```
These will be used to properly reupload videos later.

### Reuploading
To reupload your folders, you need to call ``upload_to_channel``, passing the path to your "secrets" json file (or nothing if it's called ``secrets.json``. 

The file should be in the following format:
```json
{
  "link": "https://www.youtube.com/channel/...",
  "username": "name@site",
  "password": "your_silly_password"
}
```
There are slight variations you can use, but I won't go into them here as they aren't the intended format.

You should now see your videos being reuploaded. Unlike with the downloader, the reuploader should not be run as multiple processes. Youtube will flag your account as being hacked, and will sign you out. The same goes for uploading too quickly. You can change the amount of time between chunked uploads, but be careful.

You also need to verify your Youtube account to upload thumbnails. If you do not, the reuploader will time out. You may also have issues with upload limits if you are reuploading a lot of videos.

## Notes
This program was meant for archival purposes. It is not meant to be extremely portable, nor flexible. If you run into any issues with the intended usage, let me know; otherwise, you're on your own.
