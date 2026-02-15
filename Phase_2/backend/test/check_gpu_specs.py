#!/usr/bin/env python3
"""
GPU Specifications Checker - Reports SM count, memory, and compute capability
Useful for diagnosing CUDA optimization issues
"""

import torch
import subprocess
import re

def check_gpu_specs():
    """Check GPU Streaming Multiprocessors (SMs) and other specs"""
    
    print("=" * 80)
    print("GPU SPECIFICATIONS & SM COUNT")
    print("=" * 80)
    
    if not torch.cuda.is_available():
        print("❌ CUDA not available!")
        return
    
    device_count = torch.cuda.device_count()
    print(f"\n📊 CUDA Devices: {device_count}")
    
    for i in range(device_count):
        print(f"\n{'─' * 80}")
        print(f"Device {i}: {torch.cuda.get_device_name(i)}")
        print(f"{'─' * 80}")
        
        # Basic properties
        props = torch.cuda.get_device_properties(i)
        
        print(f"Compute Capability: {props.major}.{props.minor}")
        print(f"Total Memory: {props.total_memory / 1e9:.2f} GB")
        print(f"Max Threads per Warp: {props.warp_size}")
        print(f"SM Count (Multi-Processor Count): {props.multi_processor_count}")
        
        # Calculate derived stats
        sm_count = props.multi_processor_count
        warp_size = props.warp_size
        max_warps = sm_count * 32  # Typical: 2 warps per SM * 32 threads/warp
        
        print(f"\n  💡 Max concurrent warps: {max_warps}")
        print(f"  💡 Max theoretical threads: {max_warps * warp_size}")
        
        # CUDA capability mapping to SM types
        cc = f"{props.major}{props.minor}"
        sm_type_map = {
            "35": "Kepler",
            "50": "Maxwell",
            "52": "Maxwell",
            "60": "Pascal",
            "61": "Pascal",
            "70": "Volta",
            "72": "Volta",
            "75": "Turing",
            "80": "Ampere",
            "86": "Ampere",
            "87": "Ampere",
            "89": "Ada",
            "90": "Hopper",
            "91": "Hopper",
        }
        sm_type = sm_type_map.get(cc, "Unknown")
        print(f"  💡 Architecture: {sm_type} (CC {cc})")
        
        # Try to get physical GPU memory info
        try:
            reserved = torch.cuda.memory_reserved(i) / 1e9
            allocated = torch.cuda.memory_allocated(i) / 1e9
            print(f"\nMemory Status:")
            print(f"  Reserved: {reserved:.2f} GB")
            print(f"  Allocated: {allocated:.2f} GB")
            print(f"  Available: {(props.total_memory / 1e9) - reserved:.2f} GB")
        except:
            pass
    
    print(f"\n{'=' * 80}")
    
    # Check if TensorFloat32 is enabled
    print(f"\nTensorFloat32 Settings:")
    print(f"  Current precision: {torch.get_float32_matmul_precision()}")
    print(f"  (Options: 'highest', 'high', 'medium')")
    print(f"  Set to 'high' for Docling: torch.set_float32_matmul_precision('high')")
    
    print(f"\n{'=' * 80}\n")

if __name__ == "__main__":
    check_gpu_specs()
    
    # Optional: Try nvidia-smi if available
    print("\n" + "=" * 80)
    print("NVIDIA-SMI OUTPUT (if available)")
    print("=" * 80 + "\n")
    
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,compute_cap,memory.total,driver_version",
             "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("GPU Index | Name | Compute Capability | Total Memory | Driver Version")
            print("─" * 80)
            print(result.stdout)
        else:
            print("nvidia-smi query failed")
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        print(f"Could not run nvidia-smi: {e}")
