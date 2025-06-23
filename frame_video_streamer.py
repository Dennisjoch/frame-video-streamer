#!/usr/bin/env python3
"""
A final, optimized video streamer that uses the officially supported
ImageSpriteBlock protocol with a 4-color grayscale palette for the
maximum achievable performance on the Frame hardware.
"""
import asyncio
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from PIL import Image
import cv2

import numpy as np

from frame_msg import FrameMsg, TxImageSpriteBlock, TxSprite

ISB_MESSAGE_ID = 0x20

# A fixed 4-color grayscale palette for the best trade-off
# between image information and data size (2 bits per pixel).
FIXED_PALETTE_4_COLORS = np.array([
    [0, 0, 0], [85, 85, 85], [170, 170, 170], [255, 255, 255]
])

class FinalStreamer:
    def __init__(self, file_path, width=128, height=80, fps_limit=14):
        self.file_path = file_path
        self.width = width
        self.height = height
        self.fps_limit = fps_limit
        self.frame = FrameMsg()
        self.running = False
        self.palette_bytes = FIXED_PALETTE_4_COLORS.astype(np.uint8).tobytes()
        # Create the palette image once during initialization for maximum efficiency
        self.palette_image = Image.new('P', (1, 1))
        self.palette_image.putpalette(self.palette_bytes)

    async def _upload_lua_app(self):
        """Uploads the official sprite display app."""
        print("Uploading sprite player app...")
        await self.frame.upload_stdlua_libs(lib_names=['data', 'image_sprite_block'])
        
        script_dir = Path(__file__).parent
        tmp_dir = script_dir / "tmp"
        if not tmp_dir.exists(): tmp_dir.mkdir()
        lua_app_path = tmp_dir / "sprite_player_app.lua"

        lua_app_content = """
local data = require('data.min')
local image_sprite_block = require('image_sprite_block.min')
data.parsers[0x20] = image_sprite_block.parse_image_sprite_block
print('Sprite player app ready.')
while true do
    pcall(function()
        if data.process_raw_items() > 0 then
            local isb = data.app_data[0x20]
            if isb and isb.current_sprite_index > 0 and (isb.progressive_render or (isb.active_sprites == isb.total_sprites)) then
                for index = 1, isb.active_sprites do
                    local spr = isb.sprites[index]
                    local y_offset = isb.sprite_line_height * (index - 1)
                    if index == 1 then image_sprite_block.set_palette(spr.num_colors, spr.palette_data) end
                    frame.display.bitmap(1, y_offset + 1, spr.width, 2^spr.bpp, 0, spr.pixel_data)
                end
                frame.display.show()
            end
        end
    end)
    frame.sleep(0.001)
end
"""
        with open(lua_app_path, "w") as f: f.write(lua_app_content)
        await self.frame.upload_frame_app(local_filename=str(lua_app_path))

    async def _frame_producer(self, queue):
        """Reads video frames and puts them into the queue."""
        cap = cv2.VideoCapture(self.file_path)
        if not cap.isOpened():
            print(f"Error: Could not open video file {self.file_path}")
            self.running = False
            return
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_step = max(1, round(source_fps / self.fps_limit))
        print(f"Source video: {source_fps:.2f} FPS. Processing every {frame_step}th frame for a target of ~{self.fps_limit} FPS.")
        frame_number = 0
        while self.running:
            ret, frame_data = cap.read()
            if not ret: break
            if frame_number % frame_step == 0:
                # Convert to grayscale for processing
                gray_frame = cv2.cvtColor(frame_data, cv2.COLOR_BGR2GRAY)
                await queue.put(gray_frame)
            frame_number += 1
        await queue.put(None)
        cap.release()

    async def _frame_consumer(self, queue):
        """Processes frames and sends them as individual ImageSpriteBlocks."""
        sent_frames = 0
        start_time = time.time()
        while self.running:
            gray_frame_data = await queue.get()
            if gray_frame_data is None: self.running = False; break
            
            img = Image.fromarray(gray_frame_data).resize((self.width, self.height), Image.Resampling.NEAREST)
            # Convert the grayscale image to RGB so we can quantize it to a color palette
            img_rgb = img.convert('RGB')
            # Quantize the image to our 4-color palette using the pre-built palette image
            quantized_img = img_rgb.quantize(palette=self.palette_image)
            pixel_data = quantized_img.tobytes()

            sprite = TxSprite(
                width=self.width, height=self.height, num_colors=4,
                palette_data=self.palette_bytes, pixel_data=pixel_data, compress=False
            )
            isb = TxImageSpriteBlock(sprite, sprite_line_height=sprite.height, progressive_render=False)
            
            await self.frame.send_message(ISB_MESSAGE_ID, isb.pack())
            for line_sprite in isb.sprite_lines:
                await self.frame.send_message(ISB_MESSAGE_ID, line_sprite.pack())
            
            sent_frames += 1
            elapsed = time.time() - start_time
            if elapsed > 1:
                fps = sent_frames / elapsed
                print(f"\r[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Sent frames: {sent_frames}, FPS: {fps:.2f} ", end="")
            queue.task_done()

    async def stream(self, force_upload=True):
        """Orchestrates the streaming workflow."""
        try:
            await self.frame.connect()
            # The print response handler is useful for debugging, as it prints all responses
            # from the Frame device, including errors from the Lua script.
            # However, it makes the terminal output very noisy with confirmation messages ('1', 'nil').
            # We'll disable it for a cleaner experience in the final script.
            # To re-enable for debugging, uncomment the following line:
            # self.frame.attach_print_response_handler()

            # We are removing the screen clearing command. The correct API call is unknown,
            # and the first frame of the video will overwrite the entire display anyway,
            # making a dedicated clear command redundant.
            
            if force_upload:
                await self._upload_lua_app()
                # We need to wait a bit for the app to be ready before starting it.
                await asyncio.sleep(1)
                await self.frame.start_frame_app()
            
            queue = asyncio.Queue(maxsize=4)
            self.running = True
            producer = asyncio.create_task(self._frame_producer(queue))
            consumer = asyncio.create_task(self._frame_consumer(queue))
            await asyncio.gather(producer, consumer)
        except Exception as e:
            print(f"\nAn error occurred: {e}")
        finally:
            if self.frame.is_connected():
                print("\nDisconnecting...")
                await self.frame.disconnect()

async def main():
    parser = argparse.ArgumentParser(description="Stream a video to a Frame device.")
    # To set a default video for local testing, uncomment the following line
    # and replace the path with your own video file.
    # DEFAULT_VIDEO = "/path/to/your/video.mp4"
    parser.add_argument("video_file", help="The path to the video file to stream.")
    parser.add_argument("--width", type=int, default=128, help="Width to resize the video to.")
    parser.add_argument("--height", type=int, default=80, help="Height to resize the video to.")
    parser.add_argument("--fps", type=int, default=14, help="Target FPS for streaming.")
    args = parser.parse_args()

    # If a default video is set, use it when no argument is provided.
    # if 'DEFAULT_VIDEO' in locals() and not args.video_file:
    #    args.video_file = DEFAULT_VIDEO
    
    if not args.video_file or not Path(args.video_file).is_file():
        print(f"Error: Video file not found at '{args.video_file}' or no file provided.")
        parser.print_help()
        sys.exit(1)

    streamer = FinalStreamer(args.video_file, width=args.width, height=args.height, fps_limit=args.fps)
    await streamer.stream()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1) 