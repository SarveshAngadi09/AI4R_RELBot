# Base image
FROM ubuntu:24.04

# Set locale and non-interactive frontend
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    DEBIAN_FRONTEND=noninteractive

# Install core dependencies, ROS2, GStreamer, and Python tools in one go
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      # Localization & ROS prerequisites
      locales curl gnupg lsb-release git \
      # Python & build tools
      python3-pip python3-numpy python3-opencv python3-scipy \
      python3-matplotlib python3-pil python3-yaml python3-psutil \
      python3-requests python3-tqdm build-essential software-properties-common \
      # GStreamer core + plugins + tools
      python3-gi gir1.2-gst-plugins-base-1.0 gir1.2-gstreamer-1.0 \
      gstreamer1.0-tools gstreamer1.0-plugins-base \
      gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
      gstreamer1.0-plugins-ugly gstreamer1.0-libav  gstreamer1.0-x && \
    # Generate locale
    locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8 && \
    # Add ROS2 Jazzy repo key and list
    mkdir -p /etc/apt/keyrings && \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
      | gpg --dearmor -o /etc/apt/keyrings/ros2-keyring.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/ros2-keyring.gpg] \
      http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
      > /etc/apt/sources.list.d/ros2.list && \
    # Install ROS2 desktop and Python libs
    apt-get update && \
    apt-get install -y --no-install-recommends \
      ros-jazzy-desktop python3-colcon-common-extensions && \
    # Keep ROS/OpenCV/NumPy apt-managed; pip only supplies ML packages missing from apt.
    pip3 install --break-system-packages --no-cache-dir \
      "torch==2.11.0" "torchvision==0.26.0" \
      "polars==1.39.3" "ultralytics-thop==2.0.18" && \
    pip3 install --break-system-packages --no-cache-dir --no-deps \
      "ultralytics==8.4.38" && \
    # Cleanup apt caches
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Ensure ROS2 is sourced in every shell, with a hint for ROS_DOMAIN_ID
RUN echo 'source /opt/ros/jazzy/setup.bash' >> /root/.bashrc && \
    echo '# export ROS_DOMAIN_ID=<RELBot_ID>  # set per robot' >> /root/.bashrc

# Default to Bash
CMD ["/bin/bash"]
