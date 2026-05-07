"""
Generate AUTHENTIC PS1-style procedural textures.

PS1 hallmark: Visible Bayer dithering between a SMALL number of color bands.
The trick: use only 4-8 colors and manually perturb pixels with Bayer matrix
to create obvious checkerboard/dot patterns at band boundaries.
"""
import os
import random
import math
from PIL import Image

# ── Bayer 4x4 Matrix (PS1 standard) ──
# Values 0-15, scaled to perturbation range
BAYER_4X4 = [
    [ 0,  8,  2, 10],
    [12,  4, 14,  6],
    [ 3, 11,  1,  9],
    [15,  7, 13,  5]
]

def bayer_value(x, y):
    """Get Bayer threshold at position (0-15 range)."""
    return BAYER_4X4[y % 4][x % 4]

def save_ps1_texture(img, path, num_colors=8):
    """Save with aggressive posterization."""
    indexed = img.quantize(
        colors=num_colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.ORDERED
    )
    indexed.save(path)
    print(f"  Saved: {path} ({num_colors}-color, ordered dither)")

def discretize_with_dither(value, thresholds, x, y, dither_strength=12):
    """
    Map a continuous value to discrete bands with Bayer dithering.
    
    value: 0-255 continuous input
    thresholds: list of band boundaries (e.g., [60, 120, 180])
    x, y: pixel position for Bayer pattern
    dither_strength: how much the dither can shift the boundary
    
    Returns: discrete band index + dither offset
    """
    # Apply Bayer dither to the value
    bayer = (bayer_value(x, y) / 15.0 - 0.5) * dither_strength
    adjusted = value + bayer
    
    # Find which band it falls into
    for i, t in enumerate(thresholds):
        if adjusted < t:
            return i
    return len(thresholds)

def generate_grass(size=128, variant=1):
    """PS1 grass: 4 discrete green shades with Bayer dithered transitions."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    # 4-color palette
    colors = [
        (20, 80, 10),    # Dark
        (35, 120, 18),   # Mid-dark
        (50, 160, 25),   # Mid-bright
        (65, 200, 35),   # Bright
    ]
    thresholds = [85, 140, 195]  # Band boundaries
    
    for y in range(size):
        for x in range(size):
            # Smooth base value
            base = (math.sin(x * 0.15 + variant) * 40 +
                    math.cos(y * 0.2 + variant * 0.7) * 35 +
                    math.sin((x + y) * 0.1) * 20 +
                    128)  # Center around 128
            
            # Discretize with Bayer dither
            band = discretize_with_dither(base, thresholds, x, y, dither_strength=18)
            band = max(0, min(len(colors) - 1, band))
            pixels[x, y] = colors[band]
    
    return img

def generate_water(size=128, variant=1):
    """PS1 water: 4 discrete blue shades with Bayer dither."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    colors = [
        (10, 40, 100),   # Deep
        (15, 70, 140),   # Mid
        (25, 110, 180),  # Light
        (40, 150, 220),  # Crest
    ]
    thresholds = [90, 150, 210]
    
    for y in range(size):
        for x in range(size):
            base = (math.sin(x * 0.25 + variant) * 45 +
                    math.cos(y * 0.18 + variant * 1.3) * 40 +
                    math.sin((x - y) * 0.12) * 25 +
                    128)
            
            band = discretize_with_dither(base, thresholds, x, y, dither_strength=16)
            band = max(0, min(len(colors) - 1, band))
            pixels[x, y] = colors[band]
    
    return img

def generate_lava(size=128, variant=1):
    """PS1 lava: 5 discrete red/orange shades with Bayer dither."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    colors = [
        (40, 10, 5),     # Crust
        (100, 20, 5),    # Dark
        (160, 50, 10),   # Mid
        (210, 90, 15),   # Hot
        (255, 150, 30),  # White-hot
    ]
    thresholds = [70, 115, 160, 205]
    
    for y in range(size):
        for x in range(size):
            base = (math.sin(x * 0.12 + variant) * 50 +
                    math.cos(y * 0.15 + variant * 0.9) * 45 +
                    math.sin((x + y * 0.5) * 0.08) * 30 +
                    128)
            
            band = discretize_with_dither(base, thresholds, x, y, dither_strength=20)
            band = max(0, min(len(colors) - 1, band))
            pixels[x, y] = colors[band]
    
    return img

def generate_rock(size=128, variant=1):
    """PS1 rock: 4 discrete grey-brown shades + crack lines."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    colors = [
        (50, 42, 35),    # Deep shadow
        (75, 68, 55),    # Dark
        (100, 92, 78),   # Mid
        (125, 118, 102), # Light
    ]
    thresholds = [80, 130, 180]
    
    for y in range(size):
        for x in range(size):
            base = (math.sin(x * 0.08 + variant) * 35 +
                    math.cos(y * 0.1 + variant * 1.1) * 30 +
                    128)
            
            # Crack lines
            crack1 = abs(math.sin(x * 0.35 + y * 0.2 + variant)) < 0.035
            crack2 = abs(math.cos(x * 0.2 - y * 0.3 + variant * 2)) < 0.025
            
            if crack1 or crack2:
                pixels[x, y] = (25, 20, 15)
            else:
                band = discretize_with_dither(base, thresholds, x, y, dither_strength=14)
                band = max(0, min(len(colors) - 1, band))
                pixels[x, y] = colors[band]
    
    return img

def generate_sand(size=128, variant=1):
    """PS1 sand: 3 discrete tan shades with Bayer dither."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    colors = [
        (140, 125, 60),   # Dark
        (175, 155, 85),   # Mid
        (210, 190, 110),  # Light
    ]
    thresholds = [110, 170]
    
    for y in range(size):
        for x in range(size):
            base = (math.sin(x * 0.2 + variant) * 30 +
                    math.cos(y * 0.15 + variant * 0.8) * 25 +
                    128)
            
            # Pebbles
            if random.random() < 0.05:
                pixels[x, y] = (125, 105, 50)
            else:
                band = discretize_with_dither(base, thresholds, x, y, dither_strength=16)
                band = max(0, min(len(colors) - 1, band))
                pixels[x, y] = colors[band]
    
    return img

def generate_snow(size=128, variant=1):
    """PS1 snow: 3 discrete white-blue shades."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    colors = [
        (180, 185, 210),  # Shadow
        (215, 220, 235),  # Mid
        (245, 248, 255),  # Bright
    ]
    thresholds = [120, 190]
    
    for y in range(size):
        for x in range(size):
            base = (math.sin(x * 0.1 + variant) * 25 +
                    math.cos(y * 0.12 + variant * 1.5) * 20 +
                    128)
            
            band = discretize_with_dither(base, thresholds, x, y, dither_strength=12)
            band = max(0, min(len(colors) - 1, band))
            pixels[x, y] = colors[band]
    
    return img

def generate_metal(size=128, variant=1):
    """PS1 metal: 3 grey shades + grid lines."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    colors = [
        (80, 80, 90),    # Dark
        (110, 110, 120), # Mid
        (140, 140, 150), # Light
    ]
    thresholds = [110, 170]
    
    for y in range(size):
        for x in range(size):
            base = (math.sin(x * 0.15 + variant) * 25 +
                    math.cos(y * 0.2 + variant * 0.6) * 20 +
                    128)
            
            # Grid lines
            grid = size // 8
            if x % grid == 0 or y % grid == 0:
                pixels[x, y] = (55, 55, 65)
            else:
                band = discretize_with_dither(base, thresholds, x, y, dither_strength=10)
                band = max(0, min(len(colors) - 1, band))
                pixels[x, y] = colors[band]
    
    return img

def generate_wood(size=128, variant=1):
    """PS1 wood: 3 brown shades + grain bands."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    colors = [
        (90, 55, 18),   # Dark
        (120, 75, 28),  # Mid
        (150, 95, 38),  # Light
    ]
    thresholds = [100, 165]
    
    for y in range(size):
        for x in range(size):
            # Grain bands
            band_offset = math.sin(y * 0.4 + variant) * 20
            base = (band_offset +
                    math.sin(x * 0.1 + variant * 2) * 15 +
                    128)
            
            # Knots
            if random.random() < 0.015:
                pixels[x, y] = (65, 38, 12)
            else:
                band = discretize_with_dither(base, thresholds, x, y, dither_strength=14)
                band = max(0, min(len(colors) - 1, band))
                pixels[x, y] = colors[band]
    
    return img

def generate_dirt(size=128, variant=1):
    """PS1 dirt: 3 brown shades + pebbles."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    colors = [
        (65, 42, 18),   # Dark
        (85, 58, 28),   # Mid
        (110, 75, 38),  # Light
    ]
    thresholds = [105, 170]
    
    for y in range(size):
        for x in range(size):
            base = (math.sin(x * 0.18 + variant) * 25 +
                    math.cos(y * 0.14 + variant * 1.2) * 20 +
                    128)
            
            # Pebbles
            if random.random() < 0.04:
                pixels[x, y] = (130, 110, 70)
            else:
                band = discretize_with_dither(base, thresholds, x, y, dither_strength=16)
                band = max(0, min(len(colors) - 1, band))
                pixels[x, y] = colors[band]
    
    return img

def generate_stone_platform(size=128, variant=1):
    """PS1 stone bricks: brick pattern with 2 shades."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    brick_w = size // 4
    brick_h = size // 8
    
    colors = [
        (100, 95, 90),   # Brick dark
        (125, 120, 115), # Brick light
    ]
    thresholds = [128]
    
    for y in range(size):
        for x in range(size):
            bx = (x + (y // brick_h % 2) * (brick_w // 2)) % brick_w
            by = y % brick_h
            
            # Mortar
            if bx == 0 or by == 0:
                pixels[x, y] = (60, 58, 55)
            else:
                # Brick shade with variation
                base = (math.sin(x * 0.3 + variant) * 20 + 128)
                band = discretize_with_dither(base, thresholds, x, y, dither_strength=12)
                band = max(0, min(len(colors) - 1, band))
                pixels[x, y] = colors[band]
    
    return img

def generate_checkerboard_alt(size=128, variant=1):
    """PS1 checkerboard: 2 high-contrast shades for lava areas."""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    
    colors = [
        (145, 30, 10),   # Dark red
        (200, 200, 190), # Light grey
    ]
    thresholds = [128]
    
    check = size // 8
    
    for y in range(size):
        for x in range(size):
            cx = x // check
            cy = y // check
            
            if (cx + cy) % 2 == 0:
                base = (math.sin(x * 0.2 + variant) * 10 + 80)
            else:
                base = (math.sin(x * 0.2 + variant) * 10 + 180)
            
            band = discretize_with_dither(base, thresholds, x, y, dither_strength=8)
            band = max(0, min(len(colors) - 1, band))
            pixels[x, y] = colors[band]
    
    return img

# ── Main ──

def main():
    output_dir = "/root/.openclaw/workspace/bubsy_texture_injector/packs/tiny_texture_pack_2/textures"
    os.makedirs(output_dir, exist_ok=True)
    
    print("🔥 Generating AUTHENTIC PS1-style textures...")
    print("   (Discrete color bands + manual Bayer dither at boundaries)")
    
    texture_defs = {
        "grass_01.png": (generate_grass, 1),
        "grass_02.png": (generate_grass, 2),
        "grass_03.png": (generate_grass, 3),
        "grass_04.png": (generate_grass, 4),
        "water_01.png": (generate_water, 1),
        "water_02.png": (generate_water, 2),
        "water_03.png": (generate_water, 3),
        "lava_01.png": (generate_lava, 1),
        "lava_02.png": (generate_lava, 2),
        "lava_03.png": (generate_lava, 3),
        "rock_01.png": (generate_rock, 1),
        "rock_02.png": (generate_rock, 2),
        "rock_03.png": (generate_rock, 3),
        "rock_04.png": (generate_rock, 4),
        "sand_01.png": (generate_sand, 1),
        "sand_02.png": (generate_sand, 2),
        "sand_03.png": (generate_sand, 3),
        "snow_01.png": (generate_snow, 1),
        "snow_02.png": (generate_snow, 2),
        "metal_01.png": (generate_metal, 1),
        "metal_02.png": (generate_metal, 2),
        "metal_03.png": (generate_metal, 3),
        "wood_01.png": (generate_wood, 1),
        "wood_02.png": (generate_wood, 2),
        "dirt_01.png": (generate_dirt, 1),
        "dirt_02.png": (generate_dirt, 2),
        "dirt_03.png": (generate_dirt, 3),
        "checker_alt_01.png": (generate_checkerboard_alt, 1),
    }
    
    for filename, (gen_fn, variant) in texture_defs.items():
        img = gen_fn(128, variant)
        png_path = os.path.join(output_dir, filename)
        save_ps1_texture(img, png_path, num_colors=8)
    
    print(f"\n✅ Done! Generated {len(texture_defs)} authentic PS1-style textures")
    print(f"   Location: {output_dir}/")
    print("\n💡 PS1 authenticity achieved via:")
    print("   • Manually discretizing to 3-5 color bands per texture")
    print("   • Applying Bayer 4x4 matrix at band boundaries")
    print("   • Visible checkerboard/dot dither patterns")
    print("   • Harsh posterization with dithered transitions")

if __name__ == "__main__":
    main()
