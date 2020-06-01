# Cambanzo - utilities for grabbing camera feeds and running object detection

![](example_out.png?raw=true)

## `foggycam2` for Nest camera access

### Getting access to your Nest camera feeds

As described in the docs for [foggycam2](https://github.com/nextshell/foggycam2#how-to-configure), you need to specify three parameters to access feeds. Follow the steps in [this guide](https://github.com/chrisjshull/homebridge-nest#using-a-google-account) to get access to the configuration for your cameras. You need these three fields: `issueToken`, `cookies`, and `apiKey`.


### Install `foggycam2`

Get it and install some dependencies (I had some errors so I ran some manually):
```shell
git clone https://github.com/nextshell/foggycam2.git
cd foggycam2
pip install -r src/requirements.txt
sudo apt install ffmpeg imagemagick
pip install nvidia-ml-py3
pip install typed-ast
pip install astroid
```

Copy the template config file and add the three parameters you got previously:
```shell
cp _config.json config.json
```


## Amcrest camera access

[Amcrest cameras](https://amcrest.com/ip-cameras.html) support streaming video. After enabling, for a camera with ip `192.168.1.1`, this is the rtsp
stream url for the default channel: `rtsp://192.168.1.1/cam/realmonitor?channel=1&subtype=0`.


## Wyze

TODO: Experiment with [openipc-firmware](https://github.com/openipcamera/openipc-firmware) for Wyze cameras.


## darknet

I'm using the [darknet](https://pjreddie.com/darknet/) neural network library
and example code. I have a [darknet fork](https://github.com/andypayne/darknet) updated to work with OpenCV 4 and configured for use with a GPU and cudNN.


### Build

Get it and build it:
```shell
git clone git@github.com:andypayne/darknet.git
cd darknet
make
```


### Get the modified config file

I modified the config file for use in testing. I tried training on my system
with several config options, and it always consumes all available GPU memory. My
config: [yolov3.cfg](https://gist.github.com/andypayne/dce038ebeca60ff6af88bdcf6b60b231)


### Download the weights file

Download [yolov3.weights](https://pjreddie.com/media/files/yolov3.weights).


### Running

Use the path to the modified config file and the downloaded weights file.

Running object detection:
```shell
darknet detect cfg/yolov3.cfg yolov3.weights ../foggycam2/src/capture/<camera_id>/images/<image_name>.jpg -out ./out_image
```

The annotated output image will be a file named `out_image.jpg`.


## Running

### Create a config file using the template

```shell
cp config_example.ini config.ini
```

Then edit `config.ini` and point it to the locations of the dependencies.

