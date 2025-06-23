# High-Performance Video Streamer for Frame

This project provides a Python script for high-performance video streaming to a [Frame](https://brilliant.xyz/products/frame) device. It was born out of a desire to push the limits of Frame's video capabilities, achieving a fluid, high-framerate stream by implementing a tailored data transmission strategy that sidesteps common bottlenecks.

## Features

-   **High-Performance Streaming:** Uses the `ImageSpriteBlock` protocol with a fixed 4-color (2-bit) grayscale palette for an optimal balance between image quality and data rate.
-   **Flexible Input:** Streams any local video file.
-   **Dynamic & Standalone:** Automatically generates and uploads the required Lua player to the device—no manual setup on the Frame needed.
-   **Configurable:** Easily adjust resolution and target FPS via command-line arguments.

## How It Works

The system is composed of two main parts: a Python sender and a Lua receiver.

1.  **Python Sender (`frame_video_streamer.py`):**
    *   Uses `OpenCV` to capture and process video frames from a file.
    *   Each frame is resized and quantized down to a 4-color grayscale palette using `Pillow`.
    *   The script connects to the Frame via Bluetooth LE and uploads a small Lua application.
    *   It then sends the prepared pixel data in an efficient, continuous stream.

2.  **Lua Receiver (Dynamically generated):**
    *   A lightweight Lua script that runs on the Frame.
    *   It listens for incoming `ImageSpriteBlock` data packets sent from the Python script.
    *   Upon receiving data, it decodes the custom palette and renders the pixels directly to the Frame's display.

## Getting Started

### Prerequisites

-   Python 3.8+
-   A Frame device

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Usage

Run the script from your terminal, providing the path to your video file.

```bash
python frame_video_streamer.py /path/to/your/video.mp4
```

You can also customize the output resolution and target FPS:

```bash
python frame_video_streamer.py /path/to/your/video.mp4 --width 128 --height 80 --fps 14
```

## Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](<your-repository-url>/issues).

If you have an idea for an improvement, please fork the repo and create a pull request.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## Acknowledgements

This project would not be possible without the foundational `frame-msg` library, which brilliantly handles the low-level communication protocol with the Frame device.

-   **`frame-msg` on GitHub:** [CitizenOneX/frame_msg](https://github.com/CitizenOneX/frame_msg)

## License

This project is distributed under the MIT License. See `LICENSE` for more information. 