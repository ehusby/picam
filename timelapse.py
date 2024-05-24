#!/usr/bin/env python

import argparse
import datetime
import glob
import os
import subprocess
import time
from picamera import PiCamera

from suntime import Sun


LOCAL_TIME_ZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

SUN = None
YOUTUBE_PLAYLIST_NAME = None


def save_video(vid_date, output_directory):
    input_path_pattern = f"{output_directory}/{vid_date.strftime('IMG_%Y%m%d')}*.jpg"

    run_list = [
        {
            "out_path": f"{output_directory}/{vid_date.strftime('VID_%Y%m%d.mp4')}",
            "cmd": """ ffmpeg -loglevel error -framerate 30 -pattern_type glob -i '{in_path}' -c:v libx264 -preset ultrafast -pix_fmt yuv420p '{out_path}' """,
            "upload_title": None,
        },
        {
            "out_path": f"{output_directory}/{vid_date.strftime('VID_%Y%m%d_TS.mp4')}",
            "cmd": """ ffmpeg -loglevel error -framerate 30 -pattern_type glob -i '{in_path}' -c:v libx264 -preset ultrafast -pix_fmt yuv420p -vf "drawtext=fontfile=/Library/Fonts/Arial\ Unicode.ttf: fontsize=84: fontcolor=white: text='%{{metadata\:DateTime\:def_value}}': x=(w-tw)/2: y=h-(2*lh)" '{out_path}' """,
            "upload_title": vid_date.strftime('%Y-%m-%d %A') if YOUTUBE_PLAYLIST_NAME is not None else None,
        },
    ]

    success = None
    for run in run_list:
        out_path = run["out_path"]
        cmd = run["cmd"].format(
            in_path=input_path_pattern,
            out_path=out_path,
        )
        if os.path.isfile(out_path):
            print(f"Output video already exists, will not overwrite: {out_path}")
            success = False
        else:
            print(f"Generating video file: {out_path}")
            proc = subprocess.run(cmd, shell=True)
            success = (success or success is None) and proc.returncode == 0

            upload_title = run["upload_title"]
            if upload_title is not None and proc.returncode == 0:
                print(f"Uploading to YouTube with video title '{upload_title}': {out_path}")
                proc = subprocess.run(f""" youtube-upload --privacy="unlisted" --title="{upload_title}" --playlist="{YOUTUBE_PLAYLIST_NAME}" "{out_path}" """, shell=True, timeout=600)

    if success and all(os.path.isfile(f) for f in [run["out_path"] for run in run_list]):
        print(f"Deleting daily image files: {input_path_pattern}")
        time.sleep(2)
        for f in glob.glob(input_path_pattern):
            os.remove(f)
        print("Delete complete")


def capture_photos(interval_sec, output_directory):
    camera = PiCamera()
    camera.shutter_speed = 1500
    camera.resolution = (2592, 1944)

    ended_day = None

    try:
        while True:
            now = datetime.datetime.now(tz=LOCAL_TIME_ZONE)
            # now = datetime.datetime(year=2024, month=5, day=11, hour=14, tzinfo=LOCAL_TIME_ZONE)

            sunrise_time = SUN.get_sunrise_time(at_date=now, time_zone=LOCAL_TIME_ZONE)
            sunset_time = SUN.get_sunset_time(at_date=now, time_zone=LOCAL_TIME_ZONE)

            if now.date() == ended_day:
                pass

            elif now.time() < (sunrise_time - datetime.timedelta(minutes=40)).time():
                pass

            elif now.time() > (sunset_time + datetime.timedelta(minutes=40)).time():
                ended_day = now.date()
                input_path_pattern = f"{output_directory}/{ended_day.strftime('IMG_%Y%m%d')}*.jpg"
                if len(glob.glob(input_path_pattern)) > 0:
                    print("\nEnding day and generating daily video")
                    time.sleep(2)
                    save_video(ended_day, output_directory)
                    print("\nSleeping until next day's capture")

            else:
                img_path = f"{output_directory}/{now.strftime('IMG_%Y%m%d%H%M%S.jpg')}"
                camera.capture(img_path)
                print(f"\r{now.strftime('%Y-%m-%d %H:%M:%S')} -- Photo captured and saved: {img_path}", end='', flush=True)

            # Wait for the specified interval before capturing the next photo
            time.sleep(interval_sec)

    except KeyboardInterrupt:
        print("\nDetected KeyboardInterrupt for timelapse capture script")


def main():
    global SUN
    global YOUTUBE_PLAYLIST_NAME

    parser = argparse.ArgumentParser(
        description="Capture timelapse photos with a Raspberry Pi camera and create 30 FPS daily videos.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-t", "--interval",
        type=int,
        default=30,
        help="Time interval between photo captures in seconds",
    )
    parser.add_argument(
        "-o", "--output_directory",
        type=str,
        required=True,
        help="Directory to save captured photos and videos",
    )
    parser.add_argument(
        "-lat", "--latitude",
        type=float,
        required=True,
        help="Latitude of camera location",
    )
    parser.add_argument(
        "-lon", "--longitude",
        type=float,
        required=True,
        help="Longitude of camera location",
    )
    parser.add_argument(
        "--youtube-playlist",
        type=str,
        help="Upload timestamped video to YouTube playlist with this name (requires youtube-upload install: https://github.com/tokland/youtube-upload)",
    )
    args = parser.parse_args()

    args.output_directory = os.path.expanduser(args.output_directory)
    if not os.path.isdir(args.output_directory):
        parser.error(f"Output directory does not exist: {args.output_directory}")

    SUN = Sun(args.latitude, args.longitude)
    YOUTUBE_PLAYLIST_NAME = args.youtube_playlist

    capture_photos(args.interval, args.output_directory)


if __name__ == "__main__":
    print("Starting timelapse capture script")
    main()
    print("Exiting timelapse capture script")
