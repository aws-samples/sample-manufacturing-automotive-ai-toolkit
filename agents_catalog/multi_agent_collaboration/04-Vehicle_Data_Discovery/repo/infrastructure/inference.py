import subprocess
import sys

# Install all required dependencies
required_packages = ["einops", "torchvision"]

for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

import json
import torch
from transformers import AutoProcessor, AutoModel

def model_fn(model_dir):
    """Load Cosmos model with trust_remote_code=True"""
    model = AutoModel.from_pretrained(model_dir, trust_remote_code=True, torch_dtype=torch.bfloat16)
    processor = AutoProcessor.from_pretrained(model_dir, trust_remote_code=True)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    
    return {"model": model, "processor": processor, "device": device}

def input_fn(request_body, request_content_type):
    """Parse input"""
    if request_content_type == "application/json":
        input_data = json.loads(request_body)
        return input_data.get("inputs", input_data)
    return request_body

def predict_fn(input_data, model_artifacts):
    """Generate text embeddings"""
    model = model_artifacts["model"]
    processor = model_artifacts["processor"] 
    device = model_artifacts["device"]
    
    # Handle string or list input
    if isinstance(input_data, str):
        texts = [input_data]
    else:
        texts = input_data
    
    # Process and generate embeddings
    text_inputs = processor(text=texts).to(device, dtype=torch.bfloat16)
    
    with torch.no_grad():
        text_embeddings = model.get_text_embeddings(**text_inputs)
        embeddings = text_embeddings.text_proj.cpu().float().numpy().tolist()
    
    return embeddings

def output_fn(prediction, accept):
    """Format output"""
    if accept == "application/json":
        return json.dumps(prediction), accept
    return str(prediction)
