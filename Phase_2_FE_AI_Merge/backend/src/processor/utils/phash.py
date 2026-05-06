import numpy as np
from PIL import Image, ImageFilter
from scipy.fftpack import dct
from typing import Union

# ─────────────────────────────────────────────
# Core: pHash
# ─────────────────────────────────────────────

def phash(
    image: Image.Image,
    hash_size: int = 8,
    highfreq_factor: int = 8
) -> np.ndarray:
    """
    Compute the perceptual hash (pHash) of a PIL Image.

    Args:
        image           : PIL Image object (any mode)
        hash_size       : Output hash grid size (default 8 → 64-bit hash)
        highfreq_factor : Resize multiplier for DCT input (default 4 → 32x32)

    Returns:
        np.ndarray of shape (hash_size, hash_size), dtype=bool
    """
    # Step 1: Resize to (32x32) and convert to grayscale
    img_size = hash_size * highfreq_factor          # 8 * 4 = 32
    image = image.convert("L").resize(
        (img_size, img_size), Image.LANCZOS
    )
 

    # Step 2: Convert to float numpy array
    pixels = np.array(image, dtype=np.float32)

    # Step 3: Apply 2D DCT (row-wise then column-wise)
    dct_coeffs = dct(dct(pixels, axis=0, norm="ortho"), axis=1, norm="ortho")

    # Step 4: Crop top-left (8x8) — low-frequency components only
    dct_low = dct_coeffs[:hash_size, :hash_size]

    # Step 5: Compute median and binarize
    median = np.median(dct_low)
    hash_bits = dct_low > median                    # shape: (8, 8), dtype=bool

    return hash_bits


# ─────────────────────────────────────────────
# Utility: Hash → Hex string
# ─────────────────────────────────────────────

def hash_to_hex(hash_bits: np.ndarray) -> str:
    """Convert a boolean hash array to a hex string."""
    flat = hash_bits.flatten()
    bit_str = "".join("1" if b else "0" for b in flat)
    hex_digits = len(flat) // 4
    return f"{int(bit_str, 2):0{hex_digits}x}"


def hex_to_hash(hex_str: str, hash_size: int = 8) -> np.ndarray:
    """Convert a hex string back to a boolean hash array."""
    n_bits = hash_size * hash_size
    bit_str = f"{int(hex_str, 16):0{n_bits}b}"
    return np.arrayw([b == "1" for b in bit_str], dtype=bool).reshape(hash_size, hash_size)


# ─────────────────────────────────────────────
# Utility: Hamming distance
# ─────────────────────────────────────────────

def hamming_distance(
    hash1: Union[np.ndarray, str],
    hash2: Union[np.ndarray, str],
    hash_size: int = 8
) -> int:
    """
    Compute Hamming distance between two hashes.

    Accepts either np.ndarray (bool) or hex string.
    Lower distance = more similar images.

    Interpretation guide:
        0        → Identical or nearly identical
        1 – 10   → Very similar (minor edits, compression, resize)
        11 – 20  → Possibly related
        > 20     → Likely different images
    """
    if isinstance(hash1, str):
        hash1 = hex_to_hash(hash1, hash_size)
    if isinstance(hash2, str):
        hash2 = hex_to_hash(hash2, hash_size)

    return int(np.count_nonzero(hash1.flatten() != hash2.flatten()))


# ─────────────────────────────────────────────
# Utility: Similarity score (0.0 – 1.0)
# ─────────────────────────────────────────────

def similarity(
    hash1: Union[np.ndarray, str],
    hash2: Union[np.ndarray, str],
    hash_size: int = 8
) -> float:
    """
    Return similarity score between 0.0 (different) and 1.0 (identical).
    """
    dist = hamming_distance(hash1, hash2, hash_size)
    total_bits = hash_size * hash_size
    return 1.0 - dist / total_bits


# ─────────────────────────────────────────────
# Batch hashing
# ─────────────────────────────────────────────

def phash_from_path(image_path: str, hash_size: int = 8) -> np.ndarray:
    """Convenience wrapper: load from file path and hash."""
    with Image.open(image_path) as img:
        return phash(img, hash_size=hash_size)


def batch_phash(image_paths: list[str], hash_size: int = 8) -> dict[str, str]:
    """
    Hash multiple images at once.

    Returns:
        dict mapping image path → hex hash string
    """
    results = {}
    for path in image_paths:
        try:
            h = phash_from_path(path, hash_size=hash_size)
            results[path] = hash_to_hex(h)
        except Exception as e:
            results[path] = f"ERROR: {e}"
    return results


# image1 = Image.open('/home/namvt27/image1.png')
# image2 = Image.open('/home/namvt27/image2.png')



# h1 = phash(image1)
# h2 = phash(image2)

# # dist = hamming_distance(h1, h2)
# score = similarity(h1, h2)
 
# print(f"Similarity score between two image : {score}")

