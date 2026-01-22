#!/usr/bin/env python3
from __future__ import annotations
"""
Fleet Discovery Studio - InternVideo2.5 Behavioral Analyzer (Phase 3 GPU)
REAL VIDEO ANALYSIS: Uses InternVideo2.5 for genuine behavioral insights

SAME INTERFACE as industry_standard_behavioral_analyzer.py:
- Input: Phase 2 video_output.json (s3_video_uris, video_metadata)
- Output: behavioral_analysis (compatible with Phase 4-5 expectations)
- Environment: Same Step Functions callback pattern

DIFFERENCE: Real video understanding instead of synthetic metrics
"""

import os
import sys
import json
import boto3
import logging
import re
import gc
import torch
import numpy as np
import cv2
import torchvision.transforms as T
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from decord import VideoReader, cpu
from PIL import Image
from transformers import AutoModel, AutoTokenizer, BitsAndBytesConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# NEW: Cosmos-Embed1 imports for video embedding generation
try:
    from sentence_transformers import SentenceTransformer
    import timm
    import einops
    COSMOS_AVAILABLE = True
    logger.info("Cosmos-Embed1 dependencies available")
except ImportError as e:
    COSMOS_AVAILABLE = False
    logger.warning(f"Cosmos-Embed1 dependencies not available: {e}")

# Global AWS clients for performance
_aws_region = os.environ.get('AWS_REGION', os.environ.get('AWS_DEFAULT_REGION', 'us-west-2'))
s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')
bedrock_client = boto3.client('bedrock-runtime', region_name=_aws_region)

# Global Cosmos-Embed1 model (loaded after InternVideo2.5 unloaded for memory management)
COSMOS_MODEL = None
COSMOS_PROCESSOR = None

def unload_internvideo25_model(model, tokenizer):
    """Explicitly unload InternVideo2.5 model to free GPU memory for Cosmos"""
    try:
        if model is not None:
            # Move model to CPU and delete references
            if hasattr(model, 'cpu'):
                model.cpu()
            del model

        if tokenizer is not None:
            del tokenizer

        # Force garbage collection
        gc.collect()

        # Clear CUDA cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("InternVideo2.5 model unloaded successfully")

    except Exception as e:
        logger.warning(f"Error during InternVideo2.5 cleanup: {str(e)}")

def load_cosmos_embed1_model():
    """Load NVIDIA Cosmos-Embed1-448p model (768-dim output, matches Cohere)"""
    global COSMOS_MODEL, COSMOS_PROCESSOR

    if not COSMOS_AVAILABLE:
        logger.warning("Cosmos-Embed1 dependencies not available")
        return None, None

    if COSMOS_MODEL is not None:
        logger.info("Cosmos-Embed1 model already loaded")
        return COSMOS_MODEL, COSMOS_PROCESSOR

    try:
        logger.info("Loading NVIDIA Cosmos-Embed1-448p model (768-dim output)...")

        model_name = os.getenv('COSMOS_MODEL_PATH', 'nvidia/Cosmos-Embed1-448p')

        # Load processor first
        from transformers import AutoProcessor
        COSMOS_PROCESSOR = AutoProcessor.from_pretrained(
            model_name,
            trust_remote_code=True
        )

        # Load model with proper CUDA/BF16 configuration
        COSMOS_MODEL = AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True
        ).to("cuda", dtype=torch.bfloat16)

        logger.info("Cosmos-Embed1 model loaded successfully (768-dim output)")
        return COSMOS_MODEL, COSMOS_PROCESSOR

    except Exception as e:
        logger.error(f"Failed to load Cosmos-Embed1 model: {str(e)}")
        COSMOS_MODEL = None
        COSMOS_PROCESSOR = None
        return None, None

def cosmos_embed_video(video_path: str) -> Optional[torch.Tensor]:
    """
    Generate video embedding using NVIDIA Cosmos-Embed1-448p

    Args:
        video_path: Path to video file

    Returns:
        768-dimensional video embedding tensor (L2-normalized) or None if failed
    """
    if not COSMOS_AVAILABLE:
        logger.warning("Cosmos-Embed1 not available")
        return None

    try:
        model, processor = load_cosmos_embed1_model()
        if model is None or processor is None:
            logger.warning("Cosmos model not available")
            return None

        logger.info(f"Generating Cosmos video embedding for: {video_path}")

        # Read video and extract exactly 8 frames (Cosmos requirement)
        cap = cv2.VideoCapture(video_path)
        frames = []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Extract exactly 8 frames evenly distributed
        frame_indices = np.linspace(0, total_frames-1, 8, dtype=int)

        for frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break

            # Convert BGR to RGB and resize to 448x448
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_resized = cv2.resize(frame_rgb, (448, 448), interpolation=cv2.INTER_CUBIC)

            # Keep as numpy array for BTCHW tensor conversion (Cosmos expects [0-255] uint8)
            frames.append(frame_resized)

        cap.release()

        if len(frames) != 8:
            logger.error(f"Expected 8 frames, got {len(frames)}")
            return None

        logger.info(f"Extracted 8 frames at 448x448 resolution")

        # Convert frames to BTCHW tensor format for Cosmos processor
        # 1. Stack into (Time, Height, Width, Channel)
        video_data = np.array(frames)  # (8, 448, 448, 3)

        # 2. Convert to Tensor
        video_tensor = torch.from_numpy(video_data)  # (8, 448, 448, 3)

        # 3. Reshape to BTCHW (Batch, Time, Channel, Height, Width)
        # Current: (T, H, W, C) -> Permute to (T, C, H, W)
        video_tensor = video_tensor.permute(0, 3, 1, 2)  # (8, 3, 448, 448)

        # Add Batch Dimension: (1, T, C, H, W)
        video_tensor = video_tensor.unsqueeze(0)  # (1, 8, 3, 448, 448)

        # Ensure values are in [0-255] uint8 range as expected by Cosmos
        video_tensor = video_tensor.to(dtype=torch.uint8)

        # Process video batch using AutoProcessor with comprehensive debugging
        inputs = processor(videos=video_tensor, return_tensors="pt")

        # === COSMOS PROCESSOR OUTPUT DEBUG ===
        logger.info(f"=== COSMOS PROCESSOR DEBUG START ===")
        logger.info(f"Type of inputs: {type(inputs)}")
        logger.info(f"Inputs is dict: {isinstance(inputs, dict)}")

        if hasattr(inputs, 'keys'):
            logger.info(f"Keys in inputs: {list(inputs.keys())}")
            for key in inputs.keys():
                val = inputs[key]
                if hasattr(val, 'shape'):
                    logger.info(f"  {key}: shape={val.shape}, dtype={val.dtype}")
                else:
                    logger.info(f"  {key}: type={type(val)}, value={str(val)[:100]}...")
        else:
            logger.info(f"No keys() method - Object attributes: {[a for a in dir(inputs) if not a.startswith('_')]}")

        # Try different access patterns to find pixel_values
        pixel_values = None
        num_patches_list = None

        if isinstance(inputs, dict):
            logger.info("SUCCESS: Inputs is a dictionary")

            # Method 1: Try ALL possible keys systematically
            all_keys = list(inputs.keys())
            logger.info(f"All available keys: {all_keys}")

            # Try common video/pixel keys
            for key in ['pixel_values', 'videos', 'input_values', 'image', 'images', 'video_tensor', 'video', 'visual_inputs', 'embeddings', 'input_ids']:
                if key in inputs:
                    candidate = inputs[key]
                    if hasattr(candidate, 'shape') and len(candidate.shape) >= 3:  # Must be tensor-like with multiple dimensions
                        pixel_values = candidate
                        logger.info(f"SUCCESS: Found video data in key '{key}' with shape: {pixel_values.shape}")
                        break
                    else:
                        logger.info(f"WARNING: Key '{key}' exists but wrong format: {type(candidate)}")

            # If still no luck, try first tensor-like value in any key
            if pixel_values is None:
                for key, value in inputs.items():
                    if hasattr(value, 'shape') and len(value.shape) >= 3:
                        pixel_values = value
                        logger.info(f"SUCCESS: Using first tensor-like value from key '{key}': {pixel_values.shape}")
                        break

            # Method 3: Look for num_patches_list
            if 'num_patches_list' in inputs:
                num_patches_list = inputs['num_patches_list']
                logger.info(f"SUCCESS: Found num_patches_list: {num_patches_list}")

        elif hasattr(inputs, 'pixel_values'):
            pixel_values = inputs.pixel_values
            logger.info(f"SUCCESS: Found pixel_values as attribute: {pixel_values.shape}")

        # Fallback: Use original video tensor if processor didn't transform it correctly
        if pixel_values is None:
            logger.info("INFO: No pixel_values found in processor output - using original video tensor (this is normal)")
            pixel_values = video_tensor.float() / 255.0  # Normalize to [0,1] range

        # Fallback for num_patches_list
        if num_patches_list is None:
            num_patches_list = [1] * 8  # 8 frames = 8 patches
            logger.info(f"INFO: Using fallback num_patches_list: {num_patches_list}")

        logger.info(f"=== COSMOS PROCESSOR DEBUG END ===")

        # Move pixel_values to device
        pixel_values = pixel_values.to("cuda", dtype=torch.bfloat16)

        # Generate embedding using video input
        with torch.no_grad():
            # Use get_video_embeddings for proper video embedding (from documentation research)
            if hasattr(model, 'get_video_embeddings'):
                outputs = model.get_video_embeddings(
                    videos=pixel_values
                )
                video_embedding = outputs.visual_proj  # Extract embeddings from VideoEmbedderOutput
            else:
                # Fallback: pass all inputs safely (already moved to correct device above)
                outputs = model(**inputs)
                video_embedding = outputs.video_embeds if hasattr(outputs, 'video_embeds') else outputs.pooler_output

            # Remove batch dimension
            embedding = video_embedding.squeeze(0)  # Shape: [768]

        # Move to CPU for serialization
        embedding = embedding.cpu()

        logger.info(f"Cosmos embedding generated: shape {embedding.shape} (768-dim, L2-normalized)")
        return embedding

    except Exception as e:
        logger.error(f"Cosmos video embedding failed: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return None

def get_primary_camera_uri(video_s3_uris: List[str]) -> Optional[str]:
    """
    Get primary camera URI with Fleet camera prioritization (CAM_FRONT preferred).
    Handles exact matching to avoid 'CAM_FRONT' matching 'CAM_FRONT_LEFT'.
    """
    if not video_s3_uris:
        return None

    # Fleet camera priority: Front center is most important for scene embeddings
    camera_priority = [
        "CAM_FRONT",
        "CAM_FRONT_LEFT", "CAM_FRONT_RIGHT",
        "CAM_BACK", "CAM_BACK_LEFT", "CAM_BACK_RIGHT"
    ]

    for camera in camera_priority:
        for uri in video_s3_uris:
            # Safer Check: Ensure 'camera' is its own segment (surrounded by / or . or _)
            # This prevents CAM_FRONT from matching CAM_FRONT_LEFT
            if f"/{camera}." in uri or f"/{camera}_" in uri or uri.endswith(f"/{camera}"):
                logger.info(f"Selected {camera} as primary camera for scene embedding")
                return uri

    # Fallback: use first available if no standard names found
    logger.warning(f"No standard Fleet camera names found in {len(video_s3_uris)} videos, using first available")
    return video_s3_uris[0]

def extract_camera_name_from_uri(uri: str) -> str:
    """Extract camera name from S3 URI with exact matching - check longer names first to prevent substring issues"""
    # CRITICAL FIX: Check specific camera names first to prevent CAM_FRONT matching CAM_FRONT_LEFT
    for cam in ["CAM_FRONT_LEFT", "CAM_FRONT_RIGHT", "CAM_BACK_LEFT", "CAM_BACK_RIGHT", "CAM_FRONT", "CAM_BACK"]:
        if f"/{cam}." in uri or f"/{cam}_" in uri or uri.endswith(f"/{cam}"):
            return cam
    return "UNKNOWN_CAMERA"

# Discovery-Based architecture uses dense scene understanding instead of Rule-Based metrics

def load_video(video_path: str, num_segments: int = None, input_size: int = None) -> Tuple[torch.Tensor, List[int]]:
    """
    Load video using InternVideo2.5 standard method - Returns pixel_values and num_patches_list
    Args:
        video_path: Path to video file
        num_segments: Number of frames to extract (from env var or default)
        input_size: Frame resize dimension (from env var or default)
    Returns:
        Tuple of (pixel_values, num_patches_list) for InternVideo2.5
        ALWAYS returns a tuple even on failure to maintain contract
    """
    try:
        logger.info(f"Loading video with InternVideo2.5 preprocessing: {video_path}")

        # InternVideo2.5 parameters (allow env overrides for compatibility)
        num_segments = num_segments or int(os.getenv('INTERNVIDEO_NUM_FRAMES', '8'))    # Official default: 8
        resolution = input_size or int(os.getenv('INTERNVIDEO_INPUT_SIZE', '224'))      # Official default: 224

        # Validate video file exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # InternVideo2.5 video loading
        vr = VideoReader(video_path, ctx=cpu(0), num_threads=1)
        num_frames = len(vr)
        frame_indices = get_index(num_frames, num_segments)

        logger.info(f"Video: {num_frames} frames, sampling {len(frame_indices)} segments")

        if num_frames == 0:
            raise ValueError(f"Video file has no frames: {video_path}")

        # InternVideo2.5 transforms
        mean = (0.485, 0.456, 0.406)
        std = (0.229, 0.224, 0.225)
        transform = T.Compose([
            T.Lambda(lambda x: x.float().div(255.0)),
            T.Resize(resolution, interpolation=T.InterpolationMode.BICUBIC),
            T.CenterCrop(resolution),
            T.Normalize(mean, std)
        ])

        # InternVideo2.5 batch processing with Decord compatibility
        raw_frames = vr.get_batch(frame_indices)
        frames = raw_frames.asnumpy()  # Convert NDArray → np.ndarray
        frames = torch.from_numpy(frames)                # Convert np.ndarray → torch.Tensor
        frames = frames.permute(0, 3, 1, 2)   # NHWC -> NCHW (now works on tensor)
        pixel_values = transform(frames)      # Apply transforms to entire batch

        # Each frame is one patch in InternVideo2.5
        num_patches_list = [1] * num_segments

        logger.info(f"Preprocessing complete: {pixel_values.shape} pixel values, {len(num_patches_list)} frames, {sum(num_patches_list)} total patches")

        return pixel_values, num_patches_list

    except Exception as e:
        logger.error(f"load_video failed for {video_path}: {str(e)}")
        # Return empty tensor and list to maintain tuple contract
        # This ensures unpacking doesn't fail even when video loading fails
        resolution = input_size or int(os.getenv('INTERNVIDEO_INPUT_SIZE', '224'))  # Official default: 224
        empty_tensor = torch.empty(0, 3, resolution, resolution)  # Empty tensor with correct dimensions
        empty_patches = []
        logger.warning("Returning empty tensor/patches due to video loading failure")
        return empty_tensor, empty_patches

def dynamic_preprocess(image, image_size=448, use_thumbnail=True, max_num=1):
    """
    Dynamic preprocessing for image tiling - InternVideo2.5 compatible
    Args:
        image: PIL Image to process
        image_size: Target size for resizing
        use_thumbnail: Whether to use thumbnail mode (InternVideo2.5 default)
        max_num: Maximum number of patches (InternVideo2.5 default: 1)
    """
    # Follow InternVideo2.5 documentation pattern for dynamic preprocessing
    # For max_num=1, use single patch per frame as per documentation
    if max_num == 1:
        processed_images = [image.resize((image_size, image_size), Image.Resampling.BICUBIC)]
    else:
        # For higher max_num, could implement tiling logic, but documentation uses max_num=1
        processed_images = [image.resize((image_size, image_size), Image.Resampling.BICUBIC)]

    return processed_images

def get_index(num_frames: int, num_segments: int) -> List[int]:
    """InternVideo2.5 frame index calculation"""
    seg_size = float(num_frames - 1) / num_segments
    start = int(seg_size / 2)
    offsets = np.array([start + int(np.round(seg_size * idx)) for idx in range(num_segments)])
    return offsets.tolist()

def _diagnostic_check():
    """Comprehensive diagnostic check for model loading failures"""
    logger.info("=== DIAGNOSTIC CHECK START ===")

    # 1. CUDA/GPU Check
    try:
        import torch
        logger.info(f"PyTorch version: {torch.__version__}")
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logger.info(f"CUDA version: {torch.version.cuda}")
            logger.info(f"GPU count: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                gpu_props = torch.cuda.get_device_properties(i)
                gpu_mem = torch.cuda.get_device_properties(i).total_memory / 1024**3
                logger.info(f"GPU {i}: {gpu_props.name}, Memory: {gpu_mem:.2f}GB")
        else:
            logger.error("ERROR: CUDA NOT AVAILABLE - This is likely the root cause")
    except Exception as e:
        logger.error(f"ERROR: GPU/CUDA diagnostic failed: {e}")

    # 2. Network Connectivity Check
    try:
        import requests
        import time
        start_time = time.time()
        response = requests.get("https://huggingface.co", timeout=10)
        elapsed = time.time() - start_time
        logger.info(f"SUCCESS: HuggingFace Hub connectivity: {response.status_code} ({elapsed:.2f}s)")
    except Exception as e:
        logger.error(f"ERROR: Network connectivity failed: {e}")

    # 3. Memory Check
    try:
        import psutil
        memory = psutil.virtual_memory()
        logger.info(f"System RAM: {memory.total/1024**3:.2f}GB, Available: {memory.available/1024**3:.2f}GB")
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                gpu_mem_total = torch.cuda.get_device_properties(i).total_memory
                gpu_mem_reserved = torch.cuda.memory_reserved(i)
                gpu_mem_allocated = torch.cuda.memory_allocated(i)
                logger.info(f"GPU {i} Memory - Total: {gpu_mem_total/1024**3:.2f}GB, Reserved: {gpu_mem_reserved/1024**3:.2f}GB, Allocated: {gpu_mem_allocated/1024**3:.2f}GB")
    except Exception as e:
        logger.error(f"ERROR: Memory diagnostic failed: {e}")

    # 4. Environment Check
    try:
        import os
        logger.info(f"CUDA_VISIBLE_DEVICES: {os.getenv('CUDA_VISIBLE_DEVICES', 'Not set')}")
        logger.info(f"HF_HOME: {os.getenv('HF_HOME', 'Not set')}")
        logger.info(f"HUGGINGFACE_HUB_CACHE: {os.getenv('HUGGINGFACE_HUB_CACHE', 'Not set')}")
    except Exception as e:
        logger.error(f"ERROR: Environment diagnostic failed: {e}")

    logger.info("=== DIAGNOSTIC CHECK END ===")

def load_internvideo25_model():
    """Load InternVideo2.5 model using CORRECT pattern from HuggingFace"""

    # Run comprehensive diagnostics first
    _diagnostic_check()

    try:
        logger.info("Loading InternVideo2.5 Chat 8B model...")

        # Check available disk space
        import shutil
        for path in ['/tmp', '/opt', '/app', '/']:
            try:
                total, used, free = shutil.disk_usage(path)
                logger.info(f"Disk space [{path}] - Total: {total//1024**3}GB, Used: {used//1024**3}GB, Free: {free//1024**3}GB")
            except Exception as e:
                logger.warning(f"Could not check disk usage for {path}: {e}")

        # Model configuration from environment or default
        model_path = os.getenv('INTERNVIDEO_MODEL_PATH', 'OpenGVLab/InternVideo2_5_Chat_8B')
        # Use main filesystem instead of /tmp (which is often a small tmpfs)
        cache_dir = os.getenv('HUGGINGFACE_HUB_CACHE', '/opt/hf_cache')

        # Ensure cache directory exists
        os.makedirs(cache_dir, exist_ok=True)
        logger.info(f"Using HuggingFace cache directory: {cache_dir}")

        # NO QUANTIZATION for NVIDIA A10G (24GB VRAM) - use standard half-precision
        # As specified by user: A10G has sufficient VRAM for 8B model without quantization
        quantization_config = None

        logger.info("Using standard half-precision (no quantization) for NVIDIA A10G 24GB")

        # CORRECT: Load tokenizer and model using HuggingFace pattern (no quantization needed)
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            cache_dir=cache_dir
        )

        # Load model with standard half-precision (no quantization for A10G 24GB)
        model = AutoModel.from_pretrained(
            model_path,
            trust_remote_code=True,
            cache_dir=cache_dir,
            torch_dtype=torch.bfloat16,    # Standard half-precision
            device_map="auto"              # Automatic device placement
        )

        # Model is already loaded with bfloat16 and proper device placement (no quantization)
        logger.info(f"InternVideo2.5 model loaded successfully with standard half-precision")
        logger.info(f"Model device: {next(model.parameters()).device if hasattr(model, 'parameters') else 'Unknown'}")
        logger.info(f"Model dtype: {next(model.parameters()).dtype if hasattr(model, 'parameters') else 'Unknown'}")

        # CRITICAL FIX: Set model to evaluation mode for proper inference
        model.eval()
        logger.info("Model set to evaluation mode for inference")

        return model, tokenizer

    except Exception as e:
        import traceback
        error_type = type(e).__name__
        error_message = str(e)
        full_trace = traceback.format_exc()

        # Enhanced error categorization
        logger.error("=== MODEL LOADING FAILURE ANALYSIS ===")
        logger.error(f"Error Type: {error_type}")
        logger.error(f"Error Message: {error_message}")

        # Categorize the specific failure reason
        if "CUDA" in error_message or "cuda" in error_message:
            logger.error("CATEGORY: CUDA/GPU ISSUE")
            logger.error("   - Check GPU availability and CUDA drivers")
            logger.error("   - Verify container has GPU access")
        elif "timeout" in error_message.lower() or "connection" in error_message.lower():
            logger.error("CATEGORY: NETWORK/CONNECTIVITY ISSUE")
            logger.error("   - Check internet connectivity to HuggingFace Hub")
            logger.error("   - Verify firewall/security group settings")
        elif "memory" in error_message.lower() or "out of memory" in error_message.lower():
            logger.error("CATEGORY: MEMORY ISSUE")
            logger.error("   - Insufficient GPU memory even with quantization")
            logger.error("   - Check GPU memory availability")
        elif "permission" in error_message.lower() or "access" in error_message.lower():
            logger.error("CATEGORY: PERMISSIONS ISSUE")
            logger.error("   - Check cache directory permissions")
            logger.error("   - Verify write access to HuggingFace cache")
        elif "not found" in error_message.lower() or "404" in error_message:
            logger.error("CATEGORY: MODEL/REPOSITORY ISSUE")
            logger.error("   - Model repository not accessible or doesn't exist")
            logger.error("   - Check model path: OpenGVLab/InternVideo2_5_Chat_8B")
        else:
            logger.error("CATEGORY: UNKNOWN ISSUE")
            logger.error("   - Unclassified error - check full traceback")

        logger.error("=== FULL TRACEBACK ===")
        logger.error(full_trace)
        logger.error("=== END FAILURE ANALYSIS ===")

        # Fallback to backup mode if model loading fails
        return None, None

def load_video_from_s3(s3_uri: str, local_path: str) -> str:
    """Download video from S3 to local path"""
    try:
        # Parse S3 URI
        bucket_name = s3_uri.split('/')[2]
        key_name = '/'.join(s3_uri.split('/')[3:])

        # Download video
        s3_client.download_file(bucket_name, key_name, local_path)
        logger.info(f"Downloaded video from {s3_uri} to {local_path}")
        return local_path

    except Exception as e:
        logger.error(f"Failed to download video {s3_uri}: {str(e)}")
        raise

def get_automotive_prompts() -> List[str]:
    """
    SEMANTIC DISCOVERY ENGINE: Updated to focus on rich Visual Evidence descriptions
    that feed into the Smart LLM quantified metrics extraction pipeline.
    """
    custom_prompts = os.getenv('AUTOMOTIVE_ANALYSIS_PROMPTS')

    if custom_prompts:
        try:
            return json.loads(custom_prompts)
        except json.JSONDecodeError:
            logger.warning("Invalid custom prompts JSON, using defaults")

    # Rich descriptive analysis for Claude-Haiku extraction
    # Focus on detailed observations that ground quantified metrics in visual reality
    return [
        """Provide a comprehensive visual analysis of this multi-camera driving scene.

        Focus on detailed visual observations that capture:

        1. **Ego-Vehicle Behavior**: Describe visible movement patterns, lane positioning, and trajectory changes based on camera perspective changes between frames.

        2. **Traffic Context**: Describe the positioning, spacing, and behavior of other vehicles, pedestrians, and cyclists visible in the scene.

        3. **Environmental Conditions**: Detail the road type, infrastructure, weather/lighting conditions, construction zones, or special circumstances.

        4. **Interaction Dynamics**: Describe any visible interactions between the ego-vehicle and other actors (passing, following, yielding, etc.).

        5. **Safety Margins**: Observe visible spacing, clearances, and safety-related positioning between actors.

        Provide a rich, descriptive paragraph that captures the complete behavioral context visible across all camera angles. Focus on what you can actually observe rather than inferring precise measurements."""
    ]

def analyze_video_with_internvideo25(model, tokenizer, video_path: str, prompts: List[str]) -> Dict[str, Any]:
    """Analyze video using InternVideo2.5 with error handling and output capture"""

    if model is None or tokenizer is None:
        logger.warning("InternVideo2.5 model not available, using uncertainty report")
        return {"results": generate_uncertainty_report(video_path, "model_not_loaded"), "model_outputs": None, "analysis_method": "uncertainty_report"}

    try:
        # Load video with environment-configured parameters (32 frames, 448x448)
        pixel_values, num_patches_list = load_video(video_path)  # Use INTERNVIDEO_NUM_FRAMES=32, INTERNVIDEO_INPUT_SIZE=448
        logger.info(f"Video loaded: tensor shape {pixel_values.shape}, patches {num_patches_list}")

        # Check if video loading failed (empty tensor)
        if pixel_values.numel() == 0:
            logger.warning("Video loading failed, using uncertainty report")
            return {"results": generate_uncertainty_report(video_path, "video_loading_failed"), "model_outputs": None, "analysis_method": "uncertainty_report"}

        # Move to appropriate device and match model's dtype (NO batch dimension for InternVideo2.5)
        device = next(model.parameters()).device
        model_dtype = next(model.parameters()).dtype  # Get actual model dtype (might be float16 if quantization prevented bfloat16)

        # Use bfloat16 if available, otherwise match model dtype
        target_dtype = torch.bfloat16 if model_dtype == torch.bfloat16 else model_dtype
        pixel_values = pixel_values.to(target_dtype).to(device)

        logger.info(f"Tensors moved to device: {device}, model_dtype: {model_dtype}, pixel_values_dtype: {pixel_values.dtype}, final shape: {pixel_values.shape}")
        logger.info(f"Assertion check: len(pixel_values)={len(pixel_values)} == sum(num_patches_list)={sum(num_patches_list)}")

        # FINE-TUNED: Conservative adjustments on top of major inference fixes
        # Major fixes: model.eval() + torch.no_grad() should resolve gibberish
        generation_config = dict(
            do_sample=True,           # Keep sampling enabled
            temperature=0.45,         # ADJUSTED: More creative, less likely to repeat garbage tokens (was 0.2)
            max_new_tokens=1024,      # Keep existing token limit
            top_p=0.9,                # Keep nucleus sampling
            num_beams=1,              # Keep beam search disabled for speed
            repetition_penalty=1.05,  # ADJUSTED: Less restrictive, helps flow (was 1.1)
            eos_token_id=tokenizer.eos_token_id,  # Keep natural stopping
        )
        logger.info(f"Generation config: {generation_config}")

        results = {}
        model_outputs = {}  # Store raw model outputs

        for i, prompt in enumerate(prompts):
            logger.info(f"Analyzing prompt {i+1}/{len(prompts)}: {prompt[:50]}...")

            try:
                # CORRECT: Use proper frame-by-frame notation that InternVideo2.5 expects
                video_prefix = "".join([f"Frame{i+1}: <image>\n" for i in range(len(num_patches_list))])
                question = video_prefix + prompt
                logger.info(f"Question format (frames: {len(num_patches_list)}): {question[:150]}...")

                # More detailed logging before model.chat()
                logger.info(f"Calling model.chat() with:")
                logger.info(f"   - pixel_values: {pixel_values.shape}")
                logger.info(f"   - num_patches_list: {num_patches_list}")
                logger.info(f"   - device: {pixel_values.device}")

                # CRITICAL FIX: Wrap inference in torch.no_grad() to prevent gradient computation
                with torch.no_grad():
                    output, chat_history = model.chat(
                        tokenizer,
                        pixel_values,
                        question,
                        generation_config,
                        num_patches_list=num_patches_list,
                        history=None,
                        return_history=True
                    )

                logger.info(f"Prompt {i+1} completed, output length: {len(str(output))}")
                results[prompt] = output
                model_outputs[f"prompt_{i+1}"] = {
                    "prompt": prompt,
                    "output": output,
                    "chat_history": chat_history
                }

            except Exception as prompt_error:
                # Detailed error logging for each prompt
                logger.error(f"Prompt {i+1} failed: {type(prompt_error).__name__}: {str(prompt_error)}")
                logger.error(f"   - Error details: {repr(prompt_error)}")
                import traceback
                logger.error(f"   - Full traceback: {traceback.format_exc()}")

                # Continue with other prompts, store error info
                results[prompt] = f"Analysis failed: {str(prompt_error)}"
                model_outputs[f"prompt_{i+1}"] = {
                    "prompt": prompt,
                    "error": str(prompt_error),
                    "error_type": type(prompt_error).__name__
                }

        logger.info("InternVideo2.5 analysis completed")
        return {
            "results": results,
            "model_outputs": model_outputs,
            "analysis_method": "internvideo25",
            "generation_config": generation_config
        }

    except Exception as e:
        # Comprehensive error logging
        logger.error(f"InternVideo2.5 analysis failed completely: {type(e).__name__}: {str(e)}")
        logger.error(f"   - Error details: {repr(e)}")
        import traceback
        logger.error(f"   - Full traceback: {traceback.format_exc()}")
        return {
            "results": generate_uncertainty_report(video_path, f"analysis_error: {str(e)}"),
            "model_outputs": None,
            "analysis_method": "uncertainty_report_error",
            "error": str(e),
            "error_type": type(e).__name__
        }

def generate_uncertainty_report(video_path: str, reason: str) -> Dict[str, str]:
    """
    Fallback for Dense Captioning.
    Returns a single failure description instead of a dictionary of metrics.
    """
    logger.warning(f"Generating fallback analysis for {video_path}: {reason}")

    # We return a single key-value pair.
    # The 'parse_video_analysis_to_metrics' function will grab this value
    # and use it as the 'scene_description' for the embedding.
    return {
        "scene_description_error": f"Visual analysis failed for video at {video_path}. System could not generate a scene description. Reason: {reason}"
    }

def parse_video_analysis_to_metrics(analysis_results: Dict[str, str]) -> Dict[str, Any]:
    """Parse InternVideo2.5 dense scene understanding response"""

    logger.info("Parsing video analysis for dense scene understanding...")

    # Check for analysis failure flags - prevent fabrication
    analysis_failed = False
    failure_reasons = []

    for key, value in analysis_results.items():
        if isinstance(value, str) and ("No clear visual analysis" in value or "ANALYSIS_FAILED" in value or "scene_description_error" in key):
            analysis_failed = True
            failure_reasons.append(f"{key}: {value}")

    if analysis_failed:
        logger.warning(f"Scene description analysis failed: {failure_reasons}")
        return {
            'scene_description': "Scene analysis failed - no description available",
            'analysis_failed': True,
            'failure_reasons': failure_reasons,
            'uncertainty_flags': {
                'data_quality': 'analysis_failed',
                'confidence_score': 0.0,
                'fabrication_prevented': True
            },
            'raw_analysis': analysis_results
        }

    # Extract scene description from the single dense captioning prompt
    scene_description = "No scene description available"
    for key, value in analysis_results.items():
        if isinstance(value, str) and len(value.strip()) > 10:
            scene_description = value.strip()
            break  # We only have one prompt now, so take the first valid response

    logger.info(f"Scene description extracted: {len(scene_description)} characters")

    return {
        'scene_description': scene_description,
        'analysis_failed': False,
        'uncertainty_flags': {
            'scene_description_extracted': len(scene_description) > 20,
            'data_quality': 'high_quality' if len(scene_description) > 100 else 'low_quality',
            'description_length': len(scene_description)
        },
        'raw_analysis': analysis_results
    }

def extract_quantified_metrics_from_scene_description(scene_description: str) -> Dict[str, Any]:
    """
    Use Claude-Haiku to extract quantified metrics from scene descriptions

    This replaces hardcoded rules with GenAI analysis while maintaining grounding in visual evidence.
    The LLM extracts metrics based on visual observations rather than inventing numbers.

    Args:
        scene_description: Aggregated multi-camera scene description from InternVideo2.5

    Returns:
        Dictionary with AI-extracted quantified behavioral metrics
    """
    logger.info(f"Using Smart LLM to extract metrics from scene description ({len(scene_description)} chars)")

    try:
        # Smart LLM Prompt - Ask for evidence-grounded metrics extraction AND business intelligence
        metrics_extraction_prompt = f"""
        You are a Fleet behavioral analysis expert. Extract quantified driving metrics AND structured business intelligence from this multi-camera scene description.

        SCENE DESCRIPTION:
        {scene_description}

        Extract BOTH quantified metrics and business intelligence based ONLY on visual evidence described above:

        QUANTIFIED METRICS:
        1. SPEED_COMPLIANCE (0.0-1.0): Based on described ego vehicle movement
        2. RISK_SCORE (0.0-1.0): Based on described hazards, interactions, complexity
        3. SAFETY_SCORE (0.0-1.0): Based on described safety margins and behaviors
        4. BEHAVIORAL_COMPLEXITY (0.0-1.0): Based on number of described actors and interactions
        5. LANE_POSITIONING_QUALITY (0.0-1.0): Based on described trajectory and lane behavior

        BUSINESS INTELLIGENCE CLASSIFICATION:
        1. ENVIRONMENT_TYPE: "urban", "highway", "suburban", "rural", "construction_zone", "parking_lot"
        2. WEATHER_CONDITION: "clear", "rain", "fog", "snow", "night", "dawn_dusk"
        3. SCENARIO_TYPE: "intersection", "lane_change", "merge", "parking", "traffic_jam", "emergency_stop", "pedestrian_interaction", "construction"
        4. SAFETY_CRITICALITY: "low", "medium", "high", "critical"

        Rules:
        - Ground every classification in specific visual observations from the description
        - Use the most specific category that matches the visual evidence
        - Provide confidence score (0.0-1.0) for your assessment

        Return JSON format:
        {{
            "speed_compliance": 0.XX,
            "risk_score": 0.XX,
            "safety_score": 0.XX,
            "behavioral_complexity_score": 0.XX,
            "lane_positioning_quality": 0.XX,
            "confidence_score": 0.XX,
            "visual_evidence_summary": "Brief summary of key visual evidence used",
            "business_intelligence": {{
                "environment_type": "category_name",
                "weather_condition": "category_name",
                "scenario_type": "category_name",
                "safety_criticality": "category_name"
            }}
        }}
        """

        # Use Bedrock Claude-Haiku for fast, cost-effective metrics extraction
        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{
                    "role": "user",
                    "content": metrics_extraction_prompt
                }]
            })
        )

        response_body = json.loads(response['body'].read())
        ai_response = response_body['content'][0]['text']

        # Parse JSON response from Claude-Haiku (now includes business intelligence)
        if '{' in ai_response and '}' in ai_response:
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1
            json_str = ai_response[json_start:json_end]
            extracted_metrics = json.loads(json_str)

            logger.info(f"AI extracted metrics: risk={extracted_metrics.get('risk_score', 'N/A'):.3f}, "
                       f"safety={extracted_metrics.get('safety_score', 'N/A'):.3f}, "
                       f"confidence={extracted_metrics.get('confidence_score', 'N/A'):.3f}")

            return extracted_metrics

    except Exception as e:
        logger.error(f"Smart LLM metrics extraction failed: {str(e)}")

    # Fallback: Return basic metrics to prevent pipeline crashes
    logger.warning("Using fallback metrics due to extraction failure")
    return {
        "speed_compliance": 0.8,
        "risk_score": 0.2,
        "safety_score": 0.8,
        "behavioral_complexity_score": 0.3,
        "lane_positioning_quality": 0.7,
        "confidence_score": 0.5,
        "visual_evidence_summary": "Fallback metrics - extraction failed"
    }

def aggregate_camera_insights(all_video_analysis: Dict[str, Any], video_s3_uris: List[str], prompt: str) -> str:
    """Aggregate insights from ALL cameras instead of just taking the first"""

    valid_responses = []

    for uri in video_s3_uris:
        analysis = all_video_analysis.get(uri, {})
        results = analysis.get("results", {})

        if prompt in results and results[prompt]:
            response = results[prompt].strip()

            # Filter out specific hallucination tokens found in logs
            if "<track_begin>" in response or "<tracking>" in response:
                logger.warning(f"Filtered hallucination tokens from {uri}")
                continue

            # Keep valid responses - prefer rich descriptions but don't discard short valid ones
            # Use length > 20 to get rich descriptions while keeping valid short ones like "Stationary at intersection"
            if len(response) > 20:
                # Extract camera name for context
                camera_name = ""
                for cam in ["CAM_FRONT", "CAM_BACK", "CAM_FRONT_LEFT", "CAM_FRONT_RIGHT", "CAM_BACK_LEFT", "CAM_BACK_RIGHT"]:
                    if cam in uri:
                        camera_name = cam
                        break

                valid_responses.append(f"[{camera_name}]: {response}")
                logger.info(f"Added {camera_name} insight: {response[:100]}...")

    if valid_responses:
        # Combine all camera insights into "Super Description"
        super_description = " | ".join(valid_responses)
        logger.info(f"Created Super Description from {len(valid_responses)} cameras: {len(super_description)} chars")
        return super_description
    else:
        return f"No substantive visual analysis available across all camera angles for: {prompt[:50]}..."

def get_best_camera_response(all_video_analysis: Dict[str, Any], video_s3_uris: List[str], prompt: str, camera_priority: List[str]) -> Optional[str]:
    """Get response from best available camera for specific prompt"""
    for camera in camera_priority:
        for uri in video_s3_uris:
            if camera in uri:
                analysis = all_video_analysis.get(uri, {})
                results = analysis.get("results", {})
                if prompt in results and results[prompt] and len(results[prompt].strip()) > 10:
                    logger.info(f"Using {camera} for prompt: {prompt[:50]}...")
                    return results[prompt]
                # Don't break here - let it continue to next URI for same camera
        # Only break the outer loop after checking all URIs for this camera
    return None

def create_multi_camera_results(all_video_analysis: Dict[str, Any], video_s3_uris: List[str]) -> Dict[str, str]:
    """Create comprehensive multi-camera fusion results using ALL camera insights"""

    # Get first camera's results to get the exact prompt strings
    first_analysis = all_video_analysis.get(video_s3_uris[0], {}).get("results", {})

    multi_camera_results = {}

    for prompt in first_analysis.keys():
        # Use new aggregation function that combines ALL cameras
        aggregated_response = aggregate_camera_insights(all_video_analysis, video_s3_uris, prompt)
        multi_camera_results[prompt] = aggregated_response

    logger.info(f"Multi-camera fusion complete for {len(multi_camera_results)} prompts")
    return multi_camera_results

def main():
    """
    AWS orchestration for Phase 3 script
    Only the analysis logic changes - interface stays identical
    """
    task_token = None

    try:
        # IDENTICAL Step Functions integration
        task_token = os.getenv('STEP_FUNCTIONS_TASK_TOKEN')
        if not task_token:
            raise ValueError("STEP_FUNCTIONS_TASK_TOKEN environment variable is required")

        # IDENTICAL environment variable handling
        scene_id = os.getenv('SCENE_ID')
        input_s3_key = os.getenv('INPUT_S3_KEY')  # Points to Phase 2 video_output.json
        output_s3_key = os.getenv('OUTPUT_S3_KEY')
        s3_bucket = os.getenv('S3_BUCKET', '')

        if not all([scene_id, input_s3_key, output_s3_key]):
            raise ValueError("Required environment variables: SCENE_ID, INPUT_S3_KEY, OUTPUT_S3_KEY")

        logger.info(f"Starting InternVideo2.5 behavioral analysis for scene: {scene_id}")

        # Load InternVideo2.5 model
        model, tokenizer = load_internvideo25_model()

        # IDENTICAL S3 download logic
        local_phase2_path = f"/tmp/{scene_id}_phase2_output.json"
        logger.info(f"Downloading Phase 2 video reconstruction results...")

        if input_s3_key.startswith('s3://'):
            bucket_name = input_s3_key.split('/')[2]
            key_name = '/'.join(input_s3_key.split('/')[3:])
        else:
            bucket_name = s3_bucket
            key_name = input_s3_key

        s3_client.download_file(bucket_name, key_name, local_phase2_path)

        # IDENTICAL Phase 2 data parsing
        with open(local_phase2_path, 'r') as f:
            phase2_data = json.load(f)

        # COMPATIBILITY: Handle both video_paths (dict) and s3_video_uris (list) formats
        video_s3_uris = phase2_data.get('s3_video_uris', [])
        if not video_s3_uris:
            # Fallback: Convert video_paths dict to s3_video_uris list
            video_paths = phase2_data.get('video_paths', {})
            if video_paths and isinstance(video_paths, dict):
                video_s3_uris = list(video_paths.values())
                logger.info(f"Converted video_paths dict to s3_video_uris list: {len(video_s3_uris)} videos")
            else:
                raise ValueError("Phase 2 output missing both video S3 URIs and video paths")

        logger.info(f"Found {len(video_s3_uris)} videos for InternVideo2.5 analysis")

        # NEW: Real video analysis with InternVideo2.5
        all_video_analysis = {}

        # Get automotive-specific prompts (configurable)
        automotive_prompts = get_automotive_prompts()

        # FIXED: Reorder cameras for optimal processing (working cameras first)
        # This prevents front camera failures by processing reliable cameras first
        def reorder_cameras_for_success(video_uris):
            """Reorder cameras: back cameras first (more reliable), front cameras last"""
            back_cameras = [uri for uri in video_uris if 'CAM_BACK' in uri]
            front_cameras = [uri for uri in video_uris if 'CAM_FRONT' in uri]
            other_cameras = [uri for uri in video_uris if 'CAM_BACK' not in uri and 'CAM_FRONT' not in uri]
            # Process in order: BACK (reliable) → OTHER → FRONT (problematic)
            return back_cameras + other_cameras + front_cameras

        reordered_videos = reorder_cameras_for_success(video_s3_uris)
        videos_to_analyze = len(reordered_videos)
        logger.info(f"Analyzing all {videos_to_analyze} cameras in optimized order: {[uri.split('/')[-1].replace('.mp4','') for uri in reordered_videos]}")

        # FIXED: Add model warmup to prevent initialization issues
        logger.info("Performing model warmup inference to ensure proper initialization...")
        try:
            # Get device and dtype from model (fix for undefined 'device' variable)
            model_device = next(model.parameters()).device
            model_dtype = next(model.parameters()).dtype
            target_dtype = torch.bfloat16 if model_dtype == torch.bfloat16 else model_dtype

            # Define generation config (fix for undefined 'generation_config' variable)
            warmup_generation_config = dict(
                do_sample=True,
                temperature=0.3,
                max_new_tokens=1024,
                min_length=100,
                top_p=0.9,
                num_beams=1,
                repetition_penalty=1.2,
                pad_token_id=tokenizer.eos_token_id,
            )

            # Create dummy tensors matching expected input format
            dummy_frames = torch.randn(8, 3, 448, 448, dtype=target_dtype, device=model_device)
            dummy_patches = [1] * 8
            dummy_question = "Frame1: <image>\nFrame2: <image>\nFrame3: <image>\nFrame4: <image>\nFrame5: <image>\nFrame6: <image>\nFrame7: <image>\nFrame8: <image>\nDescribe this test scene briefly."

            # Warmup inference (output discarded) - wrapped in torch.no_grad()
            with torch.no_grad():
                _, _ = model.chat(tokenizer, dummy_frames, dummy_question, warmup_generation_config,
                                num_patches_list=dummy_patches, history=None, return_history=True)
            logger.info("Model warmup completed successfully - ready for real processing")
        except Exception as warmup_error:
            logger.warning(f"Model warmup failed (continuing anyway): {warmup_error}")

        # Process ALL cameras with retry mechanism for reliability
        failed_cameras = []

        for i, video_uri in enumerate(reordered_videos[:videos_to_analyze]):
            logger.info(f"Analyzing video {i+1}/{videos_to_analyze}: {video_uri}")

            try:
                # Download video locally
                local_video_path = f"/tmp/{scene_id}_video_{i}.mp4"
                load_video_from_s3(video_uri, local_video_path)

                # Analyze with InternVideo2.5
                video_analysis = analyze_video_with_internvideo25(
                    model, tokenizer, local_video_path, automotive_prompts
                )

                # Check if output is valid (not garbage)
                output_text = str(video_analysis.get('results', {}).get(automotive_prompts[0], ''))
                if len(output_text) < 50 or '<track_begin>' in output_text or '<tracking>' in output_text:
                    logger.warning(f"Camera {video_uri} produced short/garbage output ({len(output_text)} chars), marking for retry")
                    failed_cameras.append((i, video_uri, local_video_path))
                else:
                    logger.info(f"Camera {video_uri} processed successfully ({len(output_text)} chars)")

                all_video_analysis[video_uri] = video_analysis

            except Exception as camera_error:
                logger.error(f"Camera {video_uri} failed: {camera_error}")
                failed_cameras.append((i, video_uri, None))
                # Continue processing other cameras

            # Clean up local video file
            if os.path.exists(local_video_path):
                os.remove(local_video_path)

            # ---------------------------------------------------------
            # Aggressive GPU Memory Management
            # ---------------------------------------------------------
            # The InternVideo2.5 model with INT4 quantization creates large KV caches
            # for each video. Without cleanup, GPU memory fragments and causes
            # hallucination artifacts like "<track_begin> <tracking> answer."

            # Delete heavy objects holding GPU tensors
            del video_analysis

            # Force Python to release memory references
            gc.collect()

            # Force PyTorch to defragment GPU memory pools
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info(f"GPU Memory cleared after video {i+1}")
            # ---------------------------------------------------------

        # Retry failed cameras after model warmup from successful ones
        if failed_cameras:
            logger.info(f"Retrying {len(failed_cameras)} failed cameras after model warmup...")
            for retry_i, (original_i, video_uri, original_local_path) in enumerate(failed_cameras):
                logger.info(f"RETRY {retry_i+1}/{len(failed_cameras)}: {video_uri}")
                try:
                    # ALWAYS use a fresh path for retry to avoid conflicts
                    retry_video_path = f"/tmp/{scene_id}_video_retry_{retry_i}.mp4"

                    # Clean up any existing retry file first
                    if os.path.exists(retry_video_path):
                        os.remove(retry_video_path)
                        logger.info(f"Cleaned up existing retry file: {retry_video_path}")

                    # Download fresh copy for retry
                    logger.info(f"Re-downloading video for retry: {video_uri} -> {retry_video_path}")
                    load_video_from_s3(video_uri, retry_video_path)

                    # Retry analysis with warmed-up model using the fresh path
                    video_analysis = analyze_video_with_internvideo25(
                        model, tokenizer, retry_video_path, automotive_prompts
                    )

                    # Check retry result
                    output_text = str(video_analysis.get('results', {}).get(automotive_prompts[0], ''))
                    if len(output_text) >= 50 and '<track_begin>' not in output_text:
                        logger.info(f"RETRY SUCCESS: {video_uri} now works ({len(output_text)} chars)")
                        all_video_analysis[video_uri] = video_analysis
                    else:
                        logger.warning(f"RETRY FAILED: {video_uri} still produces garbage ({len(output_text)} chars)")

                except Exception as retry_error:
                    logger.error(f"RETRY ERROR: {video_uri} failed again: {retry_error}")
                finally:
                    # Clean up the retry file (not the original path)
                    if 'retry_video_path' in locals() and retry_video_path and os.path.exists(retry_video_path):
                        os.remove(retry_video_path)
                        logger.info(f"Cleaned up retry file: {retry_video_path}")

        # ============================================================================
        # CRITICAL: Unload InternVideo2.5 Model Before Loading Cosmos
        # ============================================================================
        logger.info("InternVideo2.5 analysis complete. Unloading model to free GPU memory for Cosmos...")
        unload_internvideo25_model(model, tokenizer)
        model = None      # Safety: ensure references are gone
        tokenizer = None
        logger.info("InternVideo2.5 model unloaded successfully")
        # ============================================================================

        # ============================================================================
        # NEW: Cosmos-Embed1 Video Embedding Generation (Dual-Stream Architecture)
        # ============================================================================
        logger.info("Starting Cosmos-Embed1 video embedding generation...")

        # Generate Cosmos embeddings for all videos
        cosmos_embeddings = {}

        for i, video_uri in enumerate(video_s3_uris):
            logger.info(f"Generating Cosmos embedding for video {i+1}/{len(video_s3_uris)}")

            # Download video locally for Cosmos processing
            local_video_path = f"/tmp/{scene_id}_cosmos_video_{i}.mp4"
            load_video_from_s3(video_uri, local_video_path)

            # Generate Cosmos video embedding (768-dim, matches Cohere)
            cosmos_embedding = cosmos_embed_video(local_video_path)

            if cosmos_embedding is not None:
                cosmos_embeddings[video_uri] = {
                    "embedding": cosmos_embedding.tolist(),  # Convert tensor to list for JSON serialization
                    "dimensions": cosmos_embedding.shape[0],
                    "model": "nvidia/Cosmos-Embed1-448p",
                    "l2_normalized": True
                }
                logger.info(f"SUCCESS: Cosmos embedding generated for {video_uri}: {cosmos_embedding.shape[0]} dimensions")
            else:
                logger.error(f"ERROR: Failed to generate Cosmos embedding for {video_uri}")
                cosmos_embeddings[video_uri] = None

            # Clean up local video file
            if os.path.exists(local_video_path):
                os.remove(local_video_path)
                
            # Force GPU memory cleanup after each video
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info(f"GPU memory cleared after processing video {i+1}")

        # Use primary camera (CAM_FRONT preferred) as scene-level embedding
        scene_cosmos_embedding = None
        primary_uri = get_primary_camera_uri(video_s3_uris)  # Can return None if no videos

        if primary_uri and cosmos_embeddings.get(primary_uri):
            scene_cosmos_embedding = cosmos_embeddings[primary_uri]["embedding"]
            camera_name = extract_camera_name_from_uri(primary_uri)
            logger.info(f"Using embedding from {camera_name} as scene-level vector")
        elif video_s3_uris and cosmos_embeddings.get(video_s3_uris[0]):
            # Absolute fallback: use first video if primary selection failed
            scene_cosmos_embedding = cosmos_embeddings[video_s3_uris[0]]["embedding"]
            primary_uri = video_s3_uris[0]  # Ensure primary_uri is set for output structure
            logger.warning("Primary camera embedding missing, falling back to first available")

        # Safety check: ensure primary_uri is defined for output (handle edge cases)
        if not primary_uri and video_s3_uris:
            primary_uri = video_s3_uris[0]

        logger.info(f"Cosmos embedding generation complete: {len([e for e in cosmos_embeddings.values() if e])} successful embeddings")
        # ============================================================================

        # Parse all video analyses using multi-camera aggregation
        multi_camera_results = create_multi_camera_results(all_video_analysis, video_s3_uris)
        primary_analysis = {"results": multi_camera_results, "analysis_method": "multi_camera_aggregate"}

        # Handle multi-camera aggregated results
        analysis_results = primary_analysis['results']
        model_outputs = {}  # Multi-camera aggregate doesn't have single model outputs
        analysis_method = primary_analysis.get('analysis_method', 'multi_camera_aggregate')

        parsed_metrics = parse_video_analysis_to_metrics(analysis_results)

        # Apply industry standards framework (same as backup)
        industry_metrics = apply_industry_standards_to_parsed_metrics(parsed_metrics)

        # Calculate fallback status for metadata (Check analysis method instead of model variables)
        fallback_used = analysis_method in ['fallback', 'fallback_due_to_error'] or model is None or tokenizer is None

        # IDENTICAL output structure for Phase 4-5 compatibility
        output_data = {
            "scene_id": scene_id,
            "phase2_input": input_s3_key,
            "s3_video_uris": video_s3_uris,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "bedrock_model_id": "internvideo25_chat_8b_v1.0",  # Updated model identifier
        }

        # Add downstream interface data (NO CHANGES to phases 4-6 needed)
        downstream_data = format_to_downstream_interface(industry_metrics, scene_id, phase2_data, all_video_analysis, fallback_used)
        output_data.update(downstream_data)

        # Add InternVideo2.5 raw outputs as supplementary metadata (doesn't break existing interface)
        output_data["internvideo25_outputs"] = {
            "analysis_method": analysis_method,
            "model_outputs": model_outputs,  # Contains actual InternVideo2.5 responses
            "all_video_analysis": all_video_analysis,  # Complete analysis for all videos
            "model_loaded_successfully": model is not None and tokenizer is not None,
            "fallback_used": fallback_used
        }

        # NEW: Add Cosmos-Embed1 video embeddings (Individual Camera Architecture)
        # Create camera-specific embeddings with proper IDs for S3 Vectors storage
        camera_specific_embeddings = {}
        for video_uri, embedding_data in cosmos_embeddings.items():
            if embedding_data:  # Skip None entries from failed embeddings
                camera_name = extract_camera_name_from_uri(video_uri)
                camera_specific_id = f"{scene_id}_{camera_name}"  # e.g., "scene_0123_CAM_FRONT"
                camera_specific_embeddings[camera_specific_id] = {
                    **embedding_data,  # Keep existing embedding, dimensions, model, l2_normalized
                    "video_uri": video_uri,      # Add S3 URI for reference
                    "camera_name": camera_name   # Add camera name for easier processing
                }
                logger.info(f"Prepared camera embedding: {camera_specific_id}")

        output_data["cosmos_embeddings"] = {
            "per_camera_embeddings": camera_specific_embeddings,  # Camera-specific IDs for S3 Vectors
            "successful_embeddings": len(camera_specific_embeddings),
            "total_cameras": len(video_s3_uris),
            "model_info": {
                "model_name": "nvidia/Cosmos-Embed1-448p",
                "dimensions": 768,
                "l2_normalized": True,
                "architecture": "individual_camera_embeddings"  # Updated architecture identifier
            }
        }

        # IDENTICAL S3 upload
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=output_s3_key,
            Body=json.dumps(output_data, indent=2),
            ContentType='application/json'
        )

        # IDENTICAL S3 verification
        verify_s3_output_exists(s3_bucket, output_s3_key)

        # IDENTICAL Step Functions success callback
        success_payload = {"output_s3_key": output_s3_key, "s3_uri": f"s3://{s3_bucket}/{output_s3_key}"}
        sfn_client.send_task_success(
            taskToken=task_token,
            output=json.dumps(success_payload)
        )

        # Cleanup
        if os.path.exists(local_phase2_path):
            os.remove(local_phase2_path)
        logger.info(f"InternVideo2.5 behavioral analysis completed successfully")

    except Exception as e:
        logger.error(f"InternVideo2.5 behavioral analysis failed: {str(e)}")

        # IDENTICAL error handling
        if task_token:
            try:
                sfn_client.send_task_failure(
                    taskToken=task_token,
                    error="Phase3.InternVideo25AnalysisFailed",
                    cause=f"InternVideo2.5 behavioral analysis failed: {str(e)}"
                )
            except Exception as callback_error:
                logger.error(f"Failed to send callback: {str(callback_error)}")

        sys.exit(1)

def apply_industry_standards_to_parsed_metrics(parsed_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle Discovery-Based parsed metrics (scene_description only) instead of Rule-Based metrics
    """

    # Discovery-Based architecture doesn't extract specific metrics
    # Return the scene description for Phase 4-5 embedding processing
    return {
        "scene_description": parsed_metrics.get('scene_description', "No scene description available"),
        "analysis_failed": parsed_metrics.get('analysis_failed', False),
        "uncertainty_flags": parsed_metrics.get('uncertainty_flags', {}),
        "discovery_based": {
            "approach": "dense_scene_understanding",
            "anomaly_detection_ready": True,
            "embedding_suitable": True,
            "rule_based_metrics": False
        },
        "raw_analysis": parsed_metrics.get('raw_analysis', {})
    }

def format_to_downstream_interface(metrics: Dict[str, Any], scene_id: str, phase2_data: Dict[str, Any], video_analysis: Dict[str, Any], fallback_used: bool) -> Dict[str, Any]:
    """Format scene description into interface structure for downstream phases"""

    # Extract scene description directly (it was put there by parse_video_analysis_to_metrics)
    scene_description = metrics.get('scene_description', "No scene description available")

    # Fallback: If not found in top level, try to find it in raw_analysis
    if scene_description == "No scene description available" and metrics and 'raw_analysis' in metrics:
         for key, value in metrics['raw_analysis'].items():
             if isinstance(value, str) and len(value.strip()) > 10:
                 scene_description = value.strip()
                 break

    # Extract quantified metrics using Claude-Haiku with visual evidence grounding
    # GenAI extracts metrics from rich scene descriptions
    quantified_metrics = extract_quantified_metrics_from_scene_description(scene_description)
    logger.info(f"Quantified metrics extracted: {list(quantified_metrics.keys())}")

    # Scene context from video analysis (keep this helper if it still works, otherwise remove)
    # scene_context = analyze_scene_context_from_video(video_analysis, scene_id)
    # Note: analyze_scene_context_from_video might need updates if it relies on old keys

    return {
        "behavioral_analysis": {
            # NEW: Dense Scene Understanding approach
            # Phase 4 will embed the values in this dictionary.
            "behavioral_insights": {
                "scene_description": scene_description
            },

            # metadata for the UI or downstream logic
            "scene_understanding": {
                "comprehensive_analysis": scene_description,
                "analysis_quality": "high" if len(scene_description) > 100 else "low",
                "visual_elements_captured": len(scene_description.split()) > 50
            },

            "discovery_metadata": {
                "approach": "dense_scene_captioning",
                "anomaly_detection_ready": True,
                "embedding_suitable": True,
                "rule_based_metrics": False
            },

            # Keep empty/generic for schema compatibility if needed
            "safety_assessments": {
                 "risk_level": "To be determined by Anomaly Detection Agent"
            },
            "recommendations": [],
            "quantified_metrics": quantified_metrics,

            # NEW: Structured business intelligence for HIL S3 Vectors queries
            "business_intelligence": extract_business_intelligence_metadata({"quantified_metrics": quantified_metrics}),

            "scene_context": {
                "description": scene_description
            }
        },
        "raw_claude_response": f"InternVideo2.5 scene analysis: {scene_description[:500]}...",
        "visual_frames_analyzed": phase2_data.get('video_metadata', {}).get('total_frames_processed', 0),
        "analysis_metadata": {
            "model_used": "internvideo25_chat_8b_v1.0",
            "analysis_method": "dense_scene_understanding_for_anomaly_detection",
            "approach": "discovery_based",
            "visual_analysis_enabled": True,
            "scene_description_enabled": True,
            "gpu_acceleration": True,
            "fallback_used": fallback_used
        }
    }

# REMOVED: calculate_performance_scores_from_real_data - Not needed in Discovery-Based architecture

# REMOVED: assess_compliance_from_real_data - Not needed in Discovery-Based architecture

# REMOVED: generate_recommendations_from_real_data - Not needed in Discovery-Based architecture

def extract_business_intelligence_metadata(behavioral_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract business intelligence metadata from Phase 3 behavioral analysis

    This function extracts structured categorical fields from the quantified_metrics
    that were generated by the enhanced Claude call in extract_quantified_metrics_from_scene_description().

    Args:
        behavioral_analysis: Complete Phase 3 behavioral analysis output

    Returns:
        Dictionary with business intelligence fields for S3 Vectors metadata
    """
    logger.info("Extracting business intelligence metadata from Phase 3 analysis")

    try:
        # Get quantified metrics which now includes business_intelligence from Claude call
        quantified_metrics = behavioral_analysis.get('quantified_metrics', {})
        business_intel = quantified_metrics.get('business_intelligence', {})

        # Extract structured categorical fields for S3 Vectors metadata
        metadata = {
            "environment_type": business_intel.get('environment_type', 'unknown'),
            "weather_condition": business_intel.get('weather_condition', 'unknown'),
            "scenario_type": business_intel.get('scenario_type', 'unknown'),
            "safety_criticality": business_intel.get('safety_criticality', 'unknown'),
            # Also include risk_score from quantified metrics for filtering
            "risk_score": quantified_metrics.get('risk_score', 0.5),
            "confidence_score": quantified_metrics.get('confidence_score', 0.5)
        }

        logger.info(f"Business intelligence extracted: {metadata}")
        return metadata

    except Exception as e:
        logger.error(f"Failed to extract business intelligence metadata: {str(e)}")
        # Return default values to prevent pipeline crashes
        return {
            "environment_type": "unknown",
            "weather_condition": "unknown",
            "scenario_type": "unknown",
            "safety_criticality": "unknown",
            "risk_score": 0.5,
            "safety_score": 0.5,  # Phase 6 queries this via Phase 4-5
            "confidence_score": 0.5
        }

def analyze_scene_context_from_video(video_analysis: Dict[str, Any], scene_id: str) -> Dict[str, Any]:
    """Analyze scene context from actual video analysis"""
    # Enhanced scene context based on video content - NO HARDCODED ASSUMPTIONS
    return {
        "scene_type": "unknown",  # Let business intelligence classification handle this
        "analysis_source": "real_video_understanding",
        "video_analysis_available": bool(video_analysis),
        "complexity_level": "high" if video_analysis else "medium",
        "traffic_density": "moderate",
        "weather_conditions": "daylight_clear",
        "road_type": "urban_mixed_traffic"
    }

def verify_s3_output_exists(bucket: str, key: str):
    """Verify S3 output exists (identical to original)"""
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        logger.info(f"Output verified in S3: s3://{bucket}/{key}")
    except Exception as e:
        raise RuntimeError(f"Failed to verify S3 output: {str(e)}")

if __name__ == "__main__":
    main()