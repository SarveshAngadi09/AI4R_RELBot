# AI4R_RELBot

**AI for Autonomous Robot** Course<br>
University of Twente - Assignment 1

This repository contains the Docker setup and starter ROS 2 package for Assignment 1 of the AI for Autonomous Robot course. In this assignment, you will use the RELBot hardware platform and extend the provided ROS 2 workflow with perception logic such as object detection, tracking, and SLAM.

All development for this assignment should happen inside the provided Docker container. The source code is stored on the host machine and mounted into the container, so your ROS 2 packages remain available after the container stops.

---
# Section 1. ROS 2 Package: `relbot_video_interface`

The included `relbot_video_interface` package receives a GStreamer video stream and publishes object position messages on `/object_position`. The RELBot controller uses this topic to decide how the robot should move.

---

## Prerequisites

- **Ubuntu** host (tested on 20.04+)
- **RELBot** hardware module

### Prepare the Host PC and Docker Container

Clone this repository on the Ubuntu host machine. The repository includes the `Dockerfile`, the `assignment1_setup.sh` helper script, and the starter ROS 2 package.

```bash
# 1. Clone the repo and enter it
git clone https://github.com/UAV-Centre-ITC/AI4R_RELBot.git
cd AI4R_RELBot

# 2. Make the helper script executable
chmod +x assignment1_setup.sh

# 3. Run the script to build (first run) or attach (subsequent runs):
./assignment1_setup.sh  # use in every shell where you want a ROS 2 Docker session
```

This script will:

- Build the Docker image on first use.
- Start or attach to the `relbot_ai4r_assignment1` container on later runs.
- Mount the host folder `./ai4r_ws/src` into the container at `/ai4r_ws/src`.

The default mapping is controlled by these variables at the top of `assignment1_setup.sh`:

```bash
HOST_FOLDER="${1:-$(pwd)/ai4r_ws/src}"    # host path to mount (defaults to ./ai4r_ws/src)
CONTAINER_FOLDER="/ai4r_ws/src"           # container mount point
```

To mount a different source folder, pass it as the first argument:

```bash
./assignment1_setup.sh /path/to/your/src
```

If you change the mount configuration after a container already exists, remove and recreate the container before expecting the new mount to appear.

Inside the container, the workspace is `/ai4r_ws`, and ROS 2 packages are placed under `/ai4r_ws/src`.

---

## Step 1: Connect to the RELBot

1. **WLAN (default)**
   - The RELBot auto-connects to SSID **RAM-lab**.
   - Ensure your host PC is on **RAM-lab**.

2. **Ethernet (alternative)**
   - Connect a standard Ethernet cable between your Ubuntu host and the RELBot.
   - In **Settings > Network > Wired**, set IPv4 Method to **"Shared to other computers"** (this shares your host's connection via DHCP).
   - Check your host's interface and assigned IP with:
     ```bash
     ifconfig  # look under eth0, enp*, or similar
     ```
   - The RELBot's Ethernet IP appears on its LCD. You can also inspect connected devices with:
     ```bash
     arp -n
     ```

3. **Determine IPs**
   - **RELBot IP**: read it from the RELBot LCD.
   - **Host IP**: run `ifconfig` and note the address under the active interface (`wlan0`, `eth0`, `enp*`, etc.).

4. **SSH access**
   ```bash
   ssh pi@<RELBOT_IP>
   # For GUI apps, enable X11 forwarding:
   ssh -X pi@<RELBOT_IP>
   ```

> **Tip:** Open three terminals on the RELBot. VS Code's Remote SSH extension can simplify this.

---

## Step 2: Stream External Webcam Video

Run this step on the RELBot. List the available video devices and use an even-numbered device: `/dev/video0` for the RELBot camera or `/dev/video2` for the external webcam.

1. **List video devices**
   ```bash
   ls /dev/video*
   ```
   Example output:
   ```text
   /dev/video0  /dev/video1  /dev/video2  /dev/video3
   ```
   Use `/dev/video0` for the RELBot camera or `/dev/video2` for the external webcam. If your RELBot shows a different even-numbered device, use that device in the GStreamer pipeline.

2. **Determine your host IP**
   Run this on the Ubuntu host machine that will receive the stream:
   ```bash
   ifconfig  # look under wlan0 or eth0
   ```

3. **Start the GStreamer pipeline**

   For best performance with the RELBot controller (which assumes a 320 px image width), update your video capture pipeline to use a 320x240 resolution (i.e. width=320, height=240). Replace `<HOST_IP>` with the IP address of the Ubuntu host machine.

   ```bash
   gst-launch-1.0 -v \
   v4l2src device=/dev/video2 ! \
   image/jpeg,width=320,height=240,framerate=30/1 ! \
   jpegdec ! videoconvert ! \
   x264enc tune=zerolatency bitrate=800 speed-preset=ultrafast ! \
   rtph264pay config-interval=1 pt=96 ! \
   udpsink host=<HOST_IP> port=5000
   ```

   Pipeline explanation:
   - `v4l2src device=/dev/video2` captures frames from the external webcam.
   - `image/jpeg,width=320,height=240,framerate=30/1` requests an MJPEG stream at 320x240 and 30 FPS.
   - `jpegdec ! videoconvert` decodes and converts the camera frames.
   - `x264enc tune=zerolatency bitrate=800 speed-preset=ultrafast` encodes low-latency H.264 video.
   - `rtph264pay config-interval=1 pt=96` packetizes the H.264 stream as RTP.
   - `udpsink host=<HOST_IP> port=5000` sends the stream to the Ubuntu host on UDP port 5000.

---

## Step 3: Launch Controller Nodes on the RELBot

Prebuilt ROS 2 packages for the FPGA and Raspberry Pi controllers are provided with your RELBot hardware. Report hardware issues for a replacement; software bugs will be patched across all robots.

Keep the webcam streaming terminal from Step 2 running. Then open two additional terminals on the RELBot.

**Terminal 1:**
```bash
source ~/ai4r_ws/install/setup.bash
cd ~/ai4r_ws/
sudo ./build/demo/demo   # low-level motor and FPGA interface
```

**Terminal 2:**
```bash
source ~/ai4r_ws/install/setup.bash
ros2 launch sequence_controller sequence_controller.launch.py   # high-level state machine
```

---

## Step 4: Configure Your Docker Container

Set up your ROS 2 workspace to communicate with the RELBot via a unique domain ID.

1. **Start or attach to the Docker container**

   Run this from the repository root on the Ubuntu host:
   ```bash
   ./assignment1_setup.sh
   ```

2. **Preview the video stream**

   Run this inside the Docker container to verify that the UDP stream from Step 2 is arriving:
   ```bash
   gst-launch-1.0 -v \
   udpsrc port=5000 caps="application/x-rtp,media=video,encoding-name=H264,payload=96" ! \
   rtph264depay ! avdec_h264 ! autovideosink
   ```

3. **Set your ROS domain**
   ```bash
   export ROS_DOMAIN_ID=<RELBot_ID>   # e.g., 8 for RELBot08
   ```
   Add this line to `~/.bashrc` inside the container if you want it to persist across shell sessions. The Docker container and the ROS 2 nodes on the RELBot must use the same `ROS_DOMAIN_ID`.

---

### Build and Test `relbot_video_interface`

The `relbot_video_interface` package is included in this repository under `ai4r_ws/src/relbot_video_interface` on the host and is mounted into the Docker container at `/ai4r_ws/src/relbot_video_interface`.

Once the Docker container is running, the video stream is visible, and `ROS_DOMAIN_ID` is set, build and launch the package:

```bash
# From inside the container, at the workspace root:
cd /ai4r_ws

# 1) Build only the provided package:
colcon build --packages-select relbot_video_interface

# 2) Source workspace:
source install/setup.bash

# 3) Launch the video interface node:
ros2 launch relbot_video_interface video_interface.launch.py
```

You should see the live camera feed streaming and placeholder `/object_position` messages being published. If no errors occur, the setup is correct and you can proceed to add or modify detection logic.


Happy coding, and good luck with your assignment!

---
# Section 2. Important Configuration and Commands

## GPU Access from Docker Container

The Docker setup is intended to support GPU-accelerated deep learning. The `assignment1_setup.sh` script already starts the container with `--gpus all`, so no script edit is needed when the host is configured correctly.

1. **Verify the NVIDIA driver on the host**

   Run this on the Ubuntu host, outside Docker:
   ```bash
   nvidia-smi
   ```
   If this command fails, install or repair the NVIDIA driver before continuing.

2. **Install the NVIDIA Container Toolkit on the host**

   Follow NVIDIA's official installation instructions for your Ubuntu version, then restart Docker. After installation, verify that Docker sees the NVIDIA runtime:

   ```bash
   docker info | grep -i "runtimes"
   ```

3. **Recreate the assignment container if needed**

   Docker run options are fixed when a container is created. If you installed GPU support after creating `relbot_ai4r_assignment1`, remove the old container and launch it again:

   ```bash
   docker stop relbot_ai4r_assignment1
   docker rm relbot_ai4r_assignment1
   ./assignment1_setup.sh
   ```

   This removes only the container instance. Your assignment packages under `./ai4r_ws/src` remain on the host because they are mounted into the container.

4. **Verify GPU access inside the container**

   ```bash
   nvidia-smi
   ```

   You should see the same GPU information inside the container as on the host.


## ROS 2 Cheatsheet

Below are common ROS 2 commands and tools for development and debugging within the Docker container:

```bash
# Build and source workspace
colcon build
source /opt/ros/jazzy/setup.bash
source /ai4r_ws/install/setup.bash

# List available packages
ros2 pkg list

# Run a node directly
ros2 run relbot_video_interface video_interface

# Launch using a launch file
ros2 launch relbot_video_interface video_interface.launch.py

# Inspect running nodes and topics
ros2 node list
ros2 topic list
ros2 topic echo /object_position

# Manage node parameters
ros2 param list /video_interface
ros2 param get /video_interface gst_pipeline
ros2 param set /video_interface gst_pipeline "<new_pipeline_string>"

# Publish a test message once to move the RELBot. If this does not work, check the ROS_DOMAIN_ID from Step 4.3.
ros2 topic pub /object_position geometry_msgs/msg/Point "{x: 100.0, y: 0.0, z: 0.0}" --once

# Debug with RQT tools
rqt                  # launch RQT plugin GUI
rqt_graph            # visualize topic-node graph

# View TF frames (if using tf2)
ros2 run tf2_tools view_frames.py
# opens frames.pdf showing TF tree

# Record and playback topics
ros2 bag record /object_position  <other_topics>    # start recording
ros2 bag play <bagfile>               # play back recorded data and process it offline
```

---
## VS Code Development Environment

For seamless development, you can use VS Code's Remote extensions to work directly inside your Docker container and SSH into the RELBot:

1. **Install Extensions**
   - **Remote Development**

2. **Connect to the Docker Container**
   - Press <kbd>F1</kbd>, then choose **Dev-Containers: Attach to Running Container...**
   - Select your `relbot_ai4r_assignment1` container.
   - VS Code will reopen with the container filesystem as your workspace.

3. **SSH into the RELBot**
   - In the **Remote Explorer** sidebar, under **Remotes (SSH/Tunnels)**, click **Configure** to add a host entry for `pi@<RELBOT_IP>`.
   - Press <kbd>F1</kbd>, then choose **Remote-SSH: Connect to Host...** and select your RELBot entry.
   - VS Code opens a new window connected to the robot, letting you inspect logs or edit files over SSH.

4. **Workflow Tips**
   - Use split windows: one VS Code window attached to Docker for code, build, and debug work, and another attached to the RELBot for robot-side logs and changes.
   - Ensure `~/.ssh/config` has your RELBot entry for quick access:
     ```text
     Host  <RELBot_IP>
         HostName <RELBot_IP>
         ForwardX11 yes
         User pi
     ```
