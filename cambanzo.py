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
import time
import argparse
import configparser
import math
import tkinter
import requests
from PIL import Image, ImageTk


# pylint: disable=invalid-name
config = configparser.ConfigParser()
config['Runtime'] = {'Verbose': 'False'}

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

def move_files(files, to_dir):
    """
    Move files to a directory, creating the directory if it doesn't exist.
    """
    os.makedirs(to_dir, exist_ok=True)
    for mfile in files:
        new_mfile = os.path.join(to_dir, os.path.basename(mfile))
        shutil.move(mfile, new_mfile)

def archive_files(files, to_base):
    """
    Archive a list of files/directories to a base location, creating a new dir
    with a timestamp name.
    """
    ts_dir = os.path.join(to_base, timestamp_str())
    os.makedirs(ts_dir, exist_ok=True)
    move_files(files, ts_dir)
    return ts_dir

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
    time.sleep(secs)
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

def timestamp_str(ts=-1):
    """
    Return a unix epoch ms timestamp as a string
    """
    ts = time.time() if ts == -1 else ts
    return str(int(1000 * ts))

def download_image(url, user, pwd, name):
    """
    Download an image with digest auth (for Amcrest camera access)
    """
    res = requests.get(url, auth=requests.auth.HTTPDigestAuth(user, pwd))
    print(f"download status: {res.status_code}")
    if res.status_code != 200:
        print("Error in download_image")
        return -1
    with open(name, 'wb') as wrt:
        wrt.write(res.content)
    return 0

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


class ImageDisplay():
    """
    Show image captures
    """
    def __init__(self):
        self.refresh_cb = None
        self.root = tkinter.Tk()
        self.root.title('cambanzo')
        self.win_width = 1920.0
        self.win_height = 1080.0
        self.can = tkinter.Canvas(self.root,
                                  width=self.win_width,
                                  height=self.win_height)

    # pylint: disable=too-many-locals
    def show_images(self, img_paths):
        """
        Show images
        """
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
            img_w = int(self.win_width / num_rows_cols)
            img_h = int((img_w / orig_w) * orig_h)
        else:
            img_h = int(self.win_height / num_rows_cols)
            img_w = int((img_h / orig_h) * orig_w)
        print(f"resized image w x h  = {img_w} x {img_h}")
        num_cols = int(self.win_width / img_w)
        num_rows = int(self.win_height / img_h)
        print(f"table dimensions     = {num_cols} x {num_rows}")
        self.can.pack()
        imgs = []
        for i, img_path in enumerate(img_paths):
            row_num = i // num_rows
            col_num = i % num_cols
            img = Image.open(img_path)
            img = img.resize((img_w, img_h), Image.ANTIALIAS)
            img_tk = ImageTk.PhotoImage(img)
            imgs.append(img_tk)
            self.can.create_image(img_w * col_num,
                                  img_h * row_num,
                                  anchor=tkinter.NW,
                                  image=img_tk)
        self.root.bind("<KeyPress>", self.on_keypress)
        self.root.mainloop()

    def on_keypress(self, e):
        """
        key press handler
        """
        print(f"press: [{e.char}]")
        print(f"event: {e}")
        if e.char == 'q':
            self.root.destroy()
            sys.exit(0)
        elif e.char == ' ':
            if self.refresh_cb:
                self.refresh_cb(self)
            self.root.destroy()

    def on_refresh(self, fn):
        """
        Refresh
        """
        self.refresh_cb = fn


def get_camera_ids(path):
    """
    Get the camera ids from foggycam2's captures.
    """
    return matching_files_in([path], r'^[A-Fa-f0-9]{32}$', full_path=False)

def run_obj_det(img_path):
    """
    Run darknet YOLO on an image file
    """
    with chdir(config['Darknet']['Path']):
        print('object detection cmd:')
        darknet_cmd = config['Darknet']['Cmd'].format(config['Darknet']['YoloCfg'],
                                                      config['Darknet']['YoloWeights'],
                                                      img_path,
                                                      config['Darknet']['OutImgFilepathPre'],
                                                      config['Darknet']['DataCfg'])
        print(darknet_cmd)
        od_res = subprocess.run(darknet_cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, shell=True, check=True)
    return od_res

def run_obj_dets(img_paths, verbose=False):
    """
    Run darknet YOLO on multiple image files
    """
    out_img_paths = []
    od_dets = []
    with chdir(config['Darknet']['Path']):
        img_path_basename = 'obj_det_out_' + timestamp_str() + '_'
        out_img_path = ''.join([config['Darknet']['OutImgFilepathPre'],
                                '_',
                                img_path_basename])
        darknet_cmd_tmpl = config['Darknet']['Cmd']
        darknet_cmd = darknet_cmd_tmpl.format(config['Darknet']['YoloCfg'],
                                              config['Darknet']['YoloWeights'],
                                              out_img_path,
                                              config['Darknet']['DataCfg'],
                                              ' '.join(img_paths))
        print(verbose and f"Darknet cmd:\n[{darknet_cmd}\n]")
        subprocess.check_output(darknet_cmd, shell=True)
        od_res = subprocess.run(darknet_cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, shell=True, check=True)
        det_re = r'\[DETECTED\] (\w+): (\d+)%'
        od_dets_run = re.findall(det_re, od_res.stdout.decode('utf-8'))
        od_dets.append(od_dets_run)
        for i in range(len(img_paths)):
            out_img_paths.append(config['Darknet']['Path'] + '/' + out_img_path +
                                 '__' + f'{i:02}' + '.jpg')
    return od_dets, out_img_paths

def run_cycle():
    """
    Run one cycle of acquisition and detection
    """
    img_paths = []
    verbose = config['Runtime']['Verbose']
    if config['Foggycam']['Enabled']:
        fc_runtime_secs = int(config['Foggycam']['DefRuntimeSecs'])
        fc_res = run_for(fc_runtime_secs, ["python", config['Foggycam']['Cmd']])
        print(verbose and f"foggycam2 response: {fc_res}")
        #cam_ids = get_camera_ids(config['Foggycam']['CapPath'])
        cam_paths = matching_files_in([config['Foggycam']['CapPath']], r'^[A-Fa-f0-9]{32}$')
        print(verbose and f"cam_paths = {cam_paths}")
        img_paths.extend(matching_files_in([path + '/images' for path in cam_paths], r'\.jpg$'))
    if config['Amcrest']['Enabled']:
        # pylint: disable=line-too-long
        img_filename = os.path.join(os.path.abspath(config['DEFAULT']['OutDir']), 'amcr_' + timestamp_str() + '.jpg')
        download_image(config['Amcrest']['StillUrl'],
                       config['Amcrest']['User'],
                       config['Amcrest']['Pass'],
                       img_filename)
        img_paths.append(img_filename)
        print(f"Amcrest img: {img_filename}")
    max_num_imgs = 9
    if config['Darknet']['Enabled']:
        obj_dets, obj_det_imgs = run_obj_dets(img_paths[:max_num_imgs], verbose)
        print(f"DETECTIONS: {obj_dets}")
        archive_files(img_paths, config['DEFAULT']['OutDir'])
        arch_dir = archive_files(obj_det_imgs, config['DEFAULT']['OutDir'])
        obj_det_imgs = [os.path.join(arch_dir, os.path.basename(p)) for p in
                        obj_det_imgs]
        return obj_det_imgs[:max_num_imgs]
    return img_paths[:max_num_imgs]

def run_archive():
    """
    Archive files
    """
    img_paths = []
    cam_paths = matching_files_in([config['Foggycam']['CapPath']], r'^[A-Fa-f0-9]{32}$')
    img_paths.extend(matching_files_in([path + '/images' for path in cam_paths], r'\.jpg$'))
    archive_files(img_paths, config['DEFAULT']['OutDir'])

def log(msg, should_print=None):
    """
    Print msg if should_print is True or Verbose is specified.
    """
    if should_print or (should_print is None and config['Runtime']['Verbose'] == 'True'):
        print(msg)

def refresh_imgs(img_disp):
    """
    Refresh the images
    """
    imgs = run_cycle()
    img_disp.show_images(imgs)

def main():
    """
    Utmost mechanical
    """
    def_conf_file = 'config.ini'
    arg_p = argparse.ArgumentParser(description='Cambanzo')
    arg_p.add_argument('--verbose', '-v',
                       dest='verbose',
                       default=False,
                       action='store_true',
                       help='verbose mode')
    arg_p.add_argument('--archive', '-a',
                       dest='archive_only',
                       action='store_true',
                       help='archive any existing images and exit')
    arg_p.add_argument('--config-file', '-c',
                       dest='config_file',
                       default=def_conf_file,
                       help=f'specify a config file to use (defaults to {def_conf_file})')
    args = arg_p.parse_args()
    config.read(args.config_file)
    config['Runtime']['Verbose'] = str(args.verbose)
    if args.archive_only:
        log("Archiving...")
        run_archive()
        log("Complete.")
        sys.exit(0)
    while True:
        imgs = run_cycle()
        img_disp = ImageDisplay()
        img_disp.on_refresh(refresh_imgs)
        img_disp.show_images(imgs)

if __name__ == "__main__":
    main()
