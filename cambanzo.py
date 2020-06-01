#!/usr/bin/env python3
"""
Cambanzo - utilities for grabbing camera feeds and running object detection
"""
import sys
import re
import os
import shutil
import subprocess
import threading
from time import sleep
import configparser
import math
import tkinter
from PIL import Image, ImageTk


# pylint: disable=invalid-name
config = configparser.ConfigParser()

def matching_files_in(dirs, pat, full_path=True):
    """
    Return all files matching the pat regex in the given directories.
    """
    patc = re.compile(pat)
    abs_fs = []
    for dir_ent in dirs:
        files = os.listdir(dir_ent)
        for mfile in files:
            if re.search(patc, mfile):
                new_path = os.path.abspath(os.path.join(dir_ent, mfile)) if full_path else mfile
                abs_fs.append(new_path)
    return abs_fs

def copy_files(files, to_dir):
    """
    Copy files to a directory, creating the directory if it doesn't exist.
    """
    os.makedirs(to_dir, exist_ok=True)
    for mfile in files:
        shutil.copy(mfile, to_dir)

# pylint: disable=invalid-name
class chdir:
    """
    Change the working diretory - context manager
    """
    def __init__(self, newPath):
        self.newPath = os.path.expanduser(newPath)
        self.savedPath = self.newPath

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)
        return self

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)

def basename_no_ext(file_path):
    """
    Given a filename with path, return the base name of the file without the
    path or extension.
    """
    base = os.path.basename(file_path)
    return os.path.splitext(base)[0]


def kill_after(secs, proc):
    """
    Kill proc after sleeping
    """
    sleep(secs)
    proc.kill()

def run_for(secs, cmd):
    """
    Run cmd, sleep secs, then kill cmd. Return cmd's output, if possible.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            universal_newlines=True)
    th = threading.Thread(target=kill_after, args=(secs, proc))
    th.start()
    out = []
    line = proc.stdout.readline()
    while line:
        out.append(line)
        line = proc.stdout.readline()
    th.join()
    return out

def display_image(img_path):
    """
    Display an image given its filepath.
    """
    img = Image.open(img_path)
    img.show()

def image_size(img_path):
    """
    Return the size (width, height) of an image
    """
    img = Image.open(img_path)
    return img.size

# pylint: disable=too-many-locals
def show_images(img_paths):
    """
    Show images with tkinter
    """
    root = tkinter.Tk()
    root.title('cambanzo')
    WIN_WIDTH = 1280
    WIN_HEIGHT = 720
    # Naively gridding into squares for now
    num_rows_cols = math.ceil(math.sqrt(len(img_paths)))
    print(f"grid # of rows and cols = {num_rows_cols}")
    # Using the dimensions of the first image for sizing
    orig_w, orig_h = image_size(img_paths[0])
    print(f"{len(img_paths)} image(s)")
    print(f"original image w x h = {orig_w} x {orig_h}")
    img_w = 0
    img_h = 0
    if orig_w > orig_h:
        img_w = int(WIN_WIDTH / num_rows_cols)
        img_h = int((img_w / orig_w) * orig_h)
    else:
        img_h = int(WIN_HEIGHT / num_rows_cols)
        img_w = int((img_h / orig_h) * orig_w)
    print(f"resized image w x h  = {img_w} x {img_h}")
    num_cols = int(WIN_WIDTH / img_w)
    num_rows = int(WIN_HEIGHT / img_h)
    print(f"table dimensions     = {num_cols} x {num_rows}")
    can = tkinter.Canvas(root, width=WIN_WIDTH, height=WIN_HEIGHT)
    can.pack()
    imgs = []
    for i, img_path in enumerate(img_paths):
        row_num = i // num_rows
        col_num = i % num_cols
        img = Image.open(img_path)
        img = img.resize((img_w, img_h), Image.ANTIALIAS)
        img_tk = ImageTk.PhotoImage(img)
        imgs.append(img_tk)
        can.create_image(img_w * col_num, img_h * row_num, anchor=tkinter.NW,
                         image=img_tk)
    root.mainloop()

def run_foggycam(fc_script):
    """
    Run foggycam2
    """
    fc_cmd = 'python {}'.format(fc_script)
    print('foggycam2 command: {}'.format(fc_cmd))
    fc_res = subprocess.check_output(fc_cmd, shell=True)
    print('foggycam2 result: {}'.format(fc_res))

def get_camera_ids(path):
    """
    Get the camera ids from foggycam2's captures.
    """
    return matching_files_in([path], r'^[A-Fa-f0-9]{32}$', full_path=False)

def run_obj_det(img_path):
    """
    Run darknet YOLO on an image file
    """
    with chdir('../darknet/'):
        print('object detection cmd:')
        darknet_cmd = config['DEFAULT']['DarknetCmd'].format(config['DEFAULT']['YoloCfg'],
                                                             config['DEFAULT']['YoloWeights'],
                                                             img_path,
                                                             config['DEFAULT']['OutImgFilepathPre'],
                                                             config['DEFAULT']['DarknetDataCfg'])
        print(darknet_cmd)
        od_res = subprocess.check_output(darknet_cmd, shell=True)
    return od_res

def run_obj_dets(img_paths):
    """
    Run darknet YOLO on multiple image files
    """
    out_img_paths = []
    with chdir('../darknet/'):
        for img_path in img_paths:
            img_path_basename = basename_no_ext(img_path)
            out_img_path = ''.join([config['DEFAULT']['DispImgFilepath'],
                                    config['DEFAULT']['OutImgFilepathPre'],
                                    '_',
                                    img_path_basename])
            darknet_cmd_tmpl = config['DEFAULT']['DarknetCmd']
            darknet_cmd = darknet_cmd_tmpl.format(config['DEFAULT']['YoloCfg'],
                                                  config['DEFAULT']['YoloWeights'],
                                                  img_path,
                                                  out_img_path,
                                                  config['DEFAULT']['DarknetDataCfg']),
            subprocess.check_output(darknet_cmd, shell=True)
            out_img_paths.append(out_img_path + '.jpg')
    return out_img_paths

def main():
    """
    It is stupid that a docstring for main is required by this linter.
    """
    args = sys.argv[1:]
    if len(args) == 1 and (args[0] == '-h' or args[0] == '--help'):
        print("Usage: {} <config file path>".format(sys.argv[0]))
        sys.exit(1)
    config_file = args[0] if len(args) == 1 else 'config.ini'
    config.read(config_file)
    fc_runtime_secs = int(config['DEFAULT']['DefFoggycamRuntimeSecs'])
    fc_res = run_for(fc_runtime_secs, ["python", config['DEFAULT']['FoggycamCmd']])
    print("foggycam2 response: {}".format(fc_res))
    #cam_ids = get_camera_ids('../foggycam2/src/capture')
    cam_paths = matching_files_in(['../foggycam2/src/capture'], r'^[A-Fa-f0-9]{32}$')
    print(f"cam_paths = {cam_paths}")
    img_paths = matching_files_in([path + '/images' for path in cam_paths], r'\.jpg$')
    print(f"img_paths = {img_paths}")
    max_num_imgs = 9
    obj_det_imgs = run_obj_dets(img_paths[:max_num_imgs])
    #show_images(img_paths[:max_num_imgs])
    show_images(obj_det_imgs[:max_num_imgs])

if __name__ == "__main__":
    main()
