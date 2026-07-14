import os
import glob
import torch
import json

# --- PYTORCH BACKWARD COMPATIBILITY OVERRIDE ---
# This forces modern PyTorch to accept older, non-restricted serialization structures
import builtins
orig_torch_load = torch.load
def patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return orig_torch_load(*args, **kwargs)
torch.load = patched_torch_load
# -----------------------------------------------

import sys
import huggingface_hub

# --- ENHANCED HUGGINGFACE_HUB PATCH FOR FLAIR ---
if not hasattr(huggingface_hub, "cached_download"):
    from huggingface_hub import hf_hub_download
    
    def patched_cached_download(*args, **kwargs):
        if 'url' in kwargs:
            url_str = kwargs.pop('url')
            if "huggingface.co/" in url_str:
                try:
                    parts = url_str.split("huggingface.co/")[1].split("/resolve/")
                    repo_id = parts[0]
                    filename = parts[1].split("/", 1)[1] if "/" in parts[1] else parts[1]
                    kwargs['repo_id'] = repo_id
                    kwargs['filename'] = filename
                except Exception:
                    pass
        return hf_hub_download(*args, **kwargs)
        
    huggingface_hub.cached_download = patched_cached_download

if not hasattr(huggingface_hub, "hf_hub_url"):
    from huggingface_hub.file_download import hf_hub_url
    huggingface_hub.hf_hub_url = hf_hub_url
# -------------------------------------------------

from parcv import parcv

def main():
    INPUT_DIR = "input"
    OUTPUT_DIR = "output"
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_files = glob.glob(os.path.join(INPUT_DIR, "*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in the '{INPUT_DIR}' directory.")
        return
    print("Initializing Models...")
    parser = parcv.Parser(pickle=True, load_pickled=False)
    print(f"Found {len(pdf_files)} CV(s) to parse.")
    print("-" * 30)

    for pdf_path in pdf_files:
        file_name = os.path.basename(pdf_path)
        base_name = os.path.splitext(file_name)[0]
        output_file = os.path.join(OUTPUT_DIR, f"{base_name}.json")
        print(f"Parsing: {file_name}...")
        try:
            json_output = parser.parse(pdf_path)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, indent=4)
            print(f"  -> Successfully saved to: {output_file}")
        except Exception as e:
            print(f"  -> Error parsing {file_name}: {e}")
    print("-" * 30)
    print("Batch processing complete.")

if __name__ == "__main__":
    main()