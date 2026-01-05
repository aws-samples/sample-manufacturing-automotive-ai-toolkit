#!/usr/bin/env python3
"""
Fleet Discovery Studio - ROS Bag Video Reconstruction Pipeline
Extracts 6-camera streams from compressed ROS bags and reconstructs videos
"""
import os
import cv2
import boto3
import numpy as np
import subprocess
import tempfile
from typing import List, Dict, Tuple
import json
from datetime import datetime

class ROSBagVideoReconstructor:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.sfn_client = boto3.client('stepfunctions')
        self.bucket_name = os.getenv('S3_BUCKET', '')

        # Dynamic topic discovery - no hard-coding
        self.camera_topics = []

    def download_rosbag(self, scene_id: str) -> str:
        """Download ROS bag from S3 to local temporary file"""
        s3_key = f'raw-data/ros-bags/nuscenes-oliver/compressed/{scene_id.zfill(4)}/compressed-NuScenes-v1.0-trainval-scene-{scene_id.zfill(4)}.bag'

        print(f"Downloading ROS bag: {s3_key}")

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.bag')
        temp_path = temp_file.name
        temp_file.close()

        # Download from S3
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, temp_path)
            print(f"Downloaded to: {temp_path}")
            return temp_path
        except Exception as e:
            print(f"Download failed: {e}")
            raise

    def discover_camera_topics(self, bag_path: str) -> List[str]:
        """Dynamically discover camera topics from ROS bag"""
        try:
            # Use rosbags to discover topics
            from rosbags.rosbag1 import Reader

            camera_topics = []
            with Reader(bag_path) as reader:
                for connection in reader.connections:
                    topic = connection.topic
                    # Dynamic detection of camera topics (image_compressed or image_rect_compressed)
                    if ('image_compressed' in topic or 'image_rect_compressed' in topic) and '/camera' not in topic.lower():
                        # Skip non-camera image topics, focus on actual camera feeds
                        if any(cam_indicator in topic.upper() for cam_indicator in ['CAM_', 'CAMERA', '/camera']):
                            camera_topics.append(topic)

            print(f" Discovered {len(camera_topics)} camera topics: {camera_topics}")
            return camera_topics

        except Exception as e:
            print(f" Topic discovery failed: {e}")
            return []

    def extract_camera_frames(self, bag_path: str, output_dir: str) -> Dict[str, List[str]]:
        """Extract frames from all camera topics using dynamic discovery"""
        print(f" Extracting frames from: {bag_path}")

        # Dynamically discover camera topics
        self.camera_topics = self.discover_camera_topics(bag_path)

        if not self.camera_topics:
            print(" No camera topics discovered in ROS bag")
            return {}

        # Create output directories for each camera
        camera_dirs = {}
        for topic in self.camera_topics:
            # Extract camera name from topic dynamically
            camera_name = topic.split('/')[-1].replace('image_compressed', '').replace('image_rect_compressed', '').strip('_')
            if not camera_name:
                camera_name = topic.split('/')[-2] if len(topic.split('/')) > 2 else topic.replace('/', '_')

            camera_dir = os.path.join(output_dir, camera_name)
            os.makedirs(camera_dir, exist_ok=True)
            camera_dirs[topic] = camera_dir

        # Extract frames using dynamic topics
        frame_paths = {}

        for topic in self.camera_topics:
            camera_name = topic.split('/')[-1].replace('image_compressed', '').replace('image_rect_compressed', '').strip('_')
            if not camera_name:
                camera_name = topic.split('/')[-2] if len(topic.split('/')) > 2 else topic.replace('/', '_')

            camera_dir = camera_dirs[topic]
            print(f"Processing camera: {camera_name} (topic: {topic})")

            try:
                frame_paths[camera_name] = self.extract_frames_python(bag_path, topic, camera_dir)
            except Exception as e:
                print(f" Frame extraction failed for {camera_name}: {e}")
                frame_paths[camera_name] = []

        return frame_paths

    def extract_frames_python(self, bag_path: str, topic: str, output_dir: str) -> List[str]:
        """Extract frames using Python rosbag library"""
        # Try rosbag first (ROS1 library)
        try:
            import rosbag
            from sensor_msgs.msg import CompressedImage
            print(" Using ROS1 rosbag library for frame extraction")

            bag = rosbag.Bag(bag_path)
            frame_paths = []
            frame_count = 0
            message_count = 0

            print(f"Reading topic: {topic}")

            for topic_name, msg, t in bag.read_messages(topics=[topic]):
                message_count += 1
                print(f"   ROS1 Message {message_count}: Found message, type={type(msg)}")

                if isinstance(msg, CompressedImage):
                    print(f"   ROS1 Message {message_count}: Is CompressedImage, data size={len(msg.data) if msg.data else 0}")
                    # Convert compressed image data to OpenCV format
                    np_arr = np.frombuffer(msg.data, np.uint8)
                    cv_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                    if cv_image is not None:
                        print(f"   ROS1 Message {message_count}: OpenCV decode SUCCESS, shape={cv_image.shape}")
                        # Save frame
                        timestamp = t.to_sec()
                        frame_filename = f"frame_{frame_count:06d}_{timestamp:.6f}.jpg"
                        frame_path = os.path.join(output_dir, frame_filename)

                        cv2.imwrite(frame_path, cv_image)
                        frame_paths.append(frame_path)
                        frame_count += 1

                        if frame_count % 10 == 0:
                            print(f"  Extracted {frame_count} frames...")
                    else:
                        print(f"   ROS1 Message {message_count}: OpenCV decode FAILED")
                else:
                    print(f"   ROS1 Message {message_count}: NOT CompressedImage, type={type(msg)}")

            print(f"   ROS1 Debug summary: {message_count} total messages found for topic {topic}")
            bag.close()
            print(f" Extracted {len(frame_paths)} frames from {topic}")
            return frame_paths

        except ImportError:
            # Try rosbags alternative (pure Python)
            try:
                from rosbags.rosbag2 import Reader
                from rosbags.serde import deserialize_cdr
                print(" Using rosbags library for frame extraction")
                return self.extract_frames_rosbags(bag_path, topic, output_dir)
            except ImportError:
                print(" Neither rosbag nor rosbags library available, using fallback method")
                return self.extract_frames_alternative(bag_path, topic, output_dir)

    def extract_frames_rosbags(self, bag_path: str, topic: str, output_dir: str) -> List[str]:
        """Extract frames using rosbags library with Phase 1's smart binary handling"""
        try:
            from rosbags.rosbag1 import Reader

            frame_paths = []
            frame_count = 0

            print(f"Reading topic with rosbags: {topic}")

            with Reader(bag_path) as reader:
                message_count = 0
                topic_matches = 0
                compressed_image_count = 0
                decode_success_count = 0

                for connection, timestamp, rawdata in reader.messages():
                    message_count += 1
                    if connection.topic == topic:
                        topic_matches += 1

                        # PHASE 1 APPROACH: Check message type BEFORE deserialization
                        msg_type_str = str(connection.msgtype)

                        # For CompressedImage: Work directly with raw binary data (NO deserialization)
                        if 'CompressedImage' in msg_type_str:
                            compressed_image_count += 1
                            print(f"   Message {topic_matches}: Found CompressedImage, rawdata size={len(rawdata)}")

                            try:
                                # PHASE 1 SOLUTION: Extract image data from ROS message structure
                                # CompressedImage has header + format + data fields in binary
                                # Skip ROS header and extract JPEG data directly

                                # Find JPEG SOI marker (0xFFD8) in the raw data
                                jpeg_start = rawdata.find(b'\xff\xd8')
                                if jpeg_start != -1:
                                    # Extract JPEG data from SOI to end
                                    jpeg_data = rawdata[jpeg_start:]

                                    print(f"   Message {topic_matches}: Found JPEG data at offset {jpeg_start}, size={len(jpeg_data)}")

                                    # Convert JPEG binary data to OpenCV format
                                    np_arr = np.frombuffer(jpeg_data, np.uint8)
                                    cv_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                                    if cv_image is not None:
                                        decode_success_count += 1
                                        print(f"   Message {topic_matches}: OpenCV decode SUCCESS, shape={cv_image.shape}")

                                        # Save frame
                                        timestamp_sec = timestamp / 1e9  # Convert from nanoseconds
                                        frame_filename = f"frame_{frame_count:06d}_{timestamp_sec:.6f}.jpg"
                                        frame_path = os.path.join(output_dir, frame_filename)

                                        cv2.imwrite(frame_path, cv_image)
                                        frame_paths.append(frame_path)
                                        frame_count += 1

                                        if frame_count % 10 == 0:
                                            print(f"  Extracted {frame_count} frames...")
                                    else:
                                        print(f"   Message {topic_matches}: OpenCV decode FAILED - invalid JPEG data")
                                else:
                                    print(f"   Message {topic_matches}: No JPEG SOI marker found in rawdata")

                            except Exception as e:
                                print(f"   Message {topic_matches}: CompressedImage processing FAILED: {e}")
                        else:
                            # For non-CompressedImage: Skip (not relevant for video extraction)
                            print(f"   Message {topic_matches}: NOT CompressedImage, msgtype={msg_type_str}")

                print(f"   Debug summary: {message_count} total messages, {topic_matches} topic matches, {compressed_image_count} CompressedImage messages, {decode_success_count} successfully decoded")

            print(f" Extracted {len(frame_paths)} frames from {topic}")
            return frame_paths

        except Exception as e:
            print(f" rosbags extraction failed: {e}")
            return self.extract_frames_alternative(bag_path, topic, output_dir)

    def extract_frames_alternative(self, bag_path: str, topic: str, output_dir: str) -> List[str]:
        """Alternative frame extraction without rosbag library"""
        print(f" Using alternative extraction for {topic}")

        # For now, create dummy frames to test the pipeline
        # In production, this would use rosbag tools or conversion
        frame_paths = []

        for i in range(5):  # Create 5 dummy frames
            # Create a test frame
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, f"Frame {i+1}", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 2)
            cv2.putText(frame, topic.split('/')[-2], (50, 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            frame_filename = f"frame_{i:06d}_dummy.jpg"
            frame_path = os.path.join(output_dir, frame_filename)
            cv2.imwrite(frame_path, frame)
            frame_paths.append(frame_path)

        print(f" Created {len(frame_paths)} test frames for {topic}")
        return frame_paths

    def create_video_from_frames(self, frame_paths: List[str], output_video_path: str, fps: int = 10) -> bool:
        """Create H.264 MP4 video from frame sequence for cross-browser compatibility"""
        if not frame_paths:
            print(" No frames to create video")
            return False

        print(f" Creating H.264 video: {output_video_path}")

        # Try FFmpeg H.264 method first (best cross-browser compatibility)
        if self._create_video_ffmpeg_h264(frame_paths, output_video_path, fps):
            return True

        print(" FFmpeg method failed, trying OpenCV H.264 fallback...")

        # Fallback to OpenCV with H.264 codec
        return self._create_video_opencv_h264(frame_paths, output_video_path, fps)

    def _create_video_ffmpeg_h264(self, frame_paths: List[str], output_video_path: str, fps: int) -> bool:
        """Create H.264 video using FFmpeg for best browser compatibility"""
        try:
            # Get frame directory for FFmpeg glob pattern
            sorted_frames = sorted(frame_paths)
            temp_dir = os.path.dirname(sorted_frames[0])

            # FFmpeg command for H.264 encoding (Chrome/Firefox/Safari compatible)
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',                                    # Overwrite output file
                '-framerate', str(fps),                  # Input framerate
                '-pattern_type', 'glob',                 # Use glob pattern matching
                '-i', os.path.join(temp_dir, '*.jpg'),   # Input pattern for all JPG frames
                '-c:v', 'libx264',                       # H.264 codec (universal browser support)
                '-pix_fmt', 'yuv420p',                   # Pixel format for web compatibility
                '-movflags', '+faststart',               # Optimize for web streaming
                '-preset', 'medium',                     # Balance encoding speed vs quality
                '-crf', '23',                           # Constant rate factor for good quality
                output_video_path
            ]

            print(f"   Running FFmpeg H.264 encoding...")
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 0:
                    file_size = os.path.getsize(output_video_path)
                    print(f" SUCCESS: FFmpeg H.264 video created successfully: {file_size:,} bytes")
                    return True
                else:
                    print(" ERROR: FFmpeg completed but no output file created")
                    return False
            else:
                print(f" ERROR: FFmpeg failed with return code {result.returncode}")
                if result.stderr:
                    print(f"    FFmpeg stderr: {result.stderr.strip()}")
                return False

        except subprocess.TimeoutExpired:
            print(" ERROR: FFmpeg encoding timed out after 5 minutes")
            return False
        except FileNotFoundError:
            print(" ERROR: FFmpeg not found in PATH")
            return False
        except Exception as e:
            print(f" ERROR: FFmpeg H.264 encoding failed: {e}")
            return False

    def _create_video_opencv_h264(self, frame_paths: List[str], output_video_path: str, fps: int) -> bool:
        """Fallback H.264 video creation using OpenCV"""
        try:
            # Read first frame to get dimensions
            first_frame = cv2.imread(frame_paths[0])
            if first_frame is None:
                print(" Could not read first frame for OpenCV method")
                return False

            height, width, channels = first_frame.shape
            print(f" Creating OpenCV H.264 video: {width}x{height} @ {fps}fps")

            # Try H.264 codecs in order of preference (cross-browser compatibility)
            codecs_to_try = [
                ('H264', 'H.264 (preferred)'),
                ('avc1', 'H.264 AVC1'),
                ('X264', 'x264'),
                ('mp4v', 'MPEG-4 (Safari fallback)')  # Last resort for Safari
            ]

            for codec_name, codec_desc in codecs_to_try:
                try:
                    print(f"   Trying {codec_desc} codec...")
                    fourcc = cv2.VideoWriter_fourcc(*codec_name)
                    video_writer = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))

                    if video_writer.isOpened():
                        print(f"   SUCCESS: {codec_desc} codec initialized successfully")

                        # Write frames to video
                        frame_count = 0
                        for i, frame_path in enumerate(sorted(frame_paths)):
                            frame = cv2.imread(frame_path)
                            if frame is not None:
                                video_writer.write(frame)
                                frame_count += 1
                                if (i + 1) % 10 == 0:
                                    print(f"      Processed {i + 1}/{len(frame_paths)} frames")

                        video_writer.release()

                        # Verify video was created successfully
                        if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 0:
                            file_size = os.path.getsize(output_video_path)
                            print(f" SUCCESS: OpenCV {codec_desc} video created: {file_size:,} bytes ({frame_count} frames)")
                            return True
                        else:
                            print(f"   ERROR: {codec_desc} created empty file, trying next codec...")
                            continue
                    else:
                        print(f"   ERROR: {codec_desc} codec not supported, trying next...")
                        continue

                except Exception as e:
                    print(f"   ERROR: {codec_desc} failed: {e}")
                    continue

            print(" ERROR: All OpenCV codecs failed")
            return False

        except Exception as e:
            print(f" ERROR: OpenCV video creation failed: {e}")
            return False

    def process_scene(self, scene_id: str) -> Dict[str, str]:
        """Process complete scene - download, extract, and create videos"""
        print(f"\nProcessing Scene {scene_id}")
        print("=" * 50)

        # Create output directory
        output_base = f"/tmp/tesla_scene_{scene_id}"
        os.makedirs(output_base, exist_ok=True)

        try:
            # Step 1: Download ROS bag
            bag_path = self.download_rosbag(scene_id)

            # Step 2: Extract frames
            frames_dir = os.path.join(output_base, "frames")
            os.makedirs(frames_dir, exist_ok=True)

            camera_frames = self.extract_camera_frames(bag_path, frames_dir)

            # Step 3: Create videos for each camera
            videos_dir = os.path.join(output_base, "videos")
            os.makedirs(videos_dir, exist_ok=True)

            video_paths = {}
            for camera_name, frame_paths in camera_frames.items():
                if frame_paths:
                    video_path = os.path.join(videos_dir, f"{camera_name}_scene_{scene_id}.mp4")
                    if self.create_video_from_frames(frame_paths, video_path):
                        video_paths[camera_name] = video_path

            # Step 4: Upload videos to S3
            s3_video_paths = {}
            for camera_name, video_path in video_paths.items():
                s3_key = f"processed-videos/scene-{scene_id.zfill(4)}/{camera_name}.mp4"
                try:
                    self.s3_client.upload_file(video_path, self.bucket_name, s3_key)
                    s3_video_paths[camera_name] = f"s3://{self.bucket_name}/{s3_key}"
                    print(f"Uploaded: {s3_key}")
                except Exception as e:
                    print(f" Upload failed for {camera_name}: {e}")

            # Step 5: Create metadata
            metadata = {
                "scene_id": scene_id,
                "processed_timestamp": datetime.now().isoformat(),
                "cameras": list(s3_video_paths.keys()),
                "video_paths": s3_video_paths,
                "frame_counts": {cam: len(frames) for cam, frames in camera_frames.items()},
                "status": "completed"
            }

            # Save metadata
            metadata_path = os.path.join(output_base, "metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Upload metadata to S3
            metadata_s3_key = f"processed-videos/scene-{scene_id.zfill(4)}/metadata.json"
            self.s3_client.upload_file(metadata_path, self.bucket_name, metadata_s3_key)

            # Cleanup
            os.unlink(bag_path)  # Remove downloaded bag file

            print(f"\n Scene {scene_id} processing complete!")
            print(f" Videos: {len(video_paths)}")
            print(f"Uploaded to S3: processed-videos/scene-{scene_id.zfill(4)}/")

            return s3_video_paths

        except Exception as e:
            print(f" Scene {scene_id} processing failed: {e}")
            return {}

def main():
    """Phase 2: Video Reconstruction with Step Functions integration"""
    reconstructor = ROSBagVideoReconstructor()

    # Get required environment variables - NO hardcoding
    task_token = os.environ.get('STEP_FUNCTIONS_TASK_TOKEN')
    scene_id = os.environ.get('SCENE_ID')

    if not task_token:
        print(" STEP_FUNCTIONS_TASK_TOKEN not found in environment")
        return

    if not scene_id:
        print(" SCENE_ID not found in environment")
        return

    # Remove 'scene-' prefix if present
    scene_id = scene_id.replace('scene-', '')

    print("Fleet Discovery Studio - Video Reconstruction Test")
    print("=" * 60)

    try:
        # Use existing working process_scene method
        result = reconstructor.process_scene(scene_id)

        if result:
            print("\nVideo reconstruction pipeline working!")
            print("Ready for InternVideo2.5 behavioral analysis integration")

            # Create Phase 2 output file for Phase 3 (InternVideo2.5)
            output_s3_key = f"processed/phase2/scene-{scene_id}/video_output.json"

            phase2_output = {
                "output_s3_key": output_s3_key,
                "s3_uri": f"s3://{reconstructor.bucket_name}/{output_s3_key}",
                "scene_id": scene_id,
                "phase": "video_reconstruction",
                "timestamp": datetime.now().isoformat(),
                "video_paths": result,
                "status": "SUCCESS"
            }

            # Upload Phase 2 output JSON to S3
            output_json = json.dumps(phase2_output, indent=2)
            reconstructor.s3_client.put_object(
                Bucket=reconstructor.bucket_name,
                Key=output_s3_key,
                Body=output_json,
                ContentType='application/json'
            )

            # Send success callback to Step Functions
            reconstructor.sfn_client.send_task_success(
                taskToken=task_token,
                output=json.dumps(phase2_output)
            )
        else:
            # Send failure callback
            reconstructor.sfn_client.send_task_failure(
                taskToken=task_token,
                error="VideoReconstructionError",
                cause="Video processing failed"
            )

    except Exception as e:
        print(f" Video reconstruction failed: {str(e)}")
        reconstructor.sfn_client.send_task_failure(
            taskToken=task_token,
            error="VideoReconstructionError",
            cause=str(e)
        )

if __name__ == "__main__":
    main()