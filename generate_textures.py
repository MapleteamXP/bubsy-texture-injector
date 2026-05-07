"""
Generate PS1-style procedural textures for the Bubsy 3D Texture Injector.
These textures are designed to look like real PS1-era pixel art textures.
"""
import os
import random
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

def save_ps1_texture(img, path, dither=True):
    """Save with PS1-style limited color palette"""
    if dither:
        # Reduce to 16-bit color depth (PS1 style)
        img = img.quantize(colors=256, method=2).convert('RGB')
    img.save(path)
    print(f"  Saved: {path}")

def generate_grass(size=128):
    """Green grass with pixel noise"""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            base = random.randint(40, 80)
            noise = random.randint(-20, 20)
            g = min(255, max(0, base + 80 + noise))
            r = min(255, max(0, base // 2 + noise))
            b = min(255, max(0, base // 3 + noise))
            # Add some "blade" lines
            if random.random() < 0.1:
                g = min(255, g + 30)
            pixels[x, y] = (r, g, b)
    return img

def generate_water(size=128):
    """Blue water with subtle wave-like patterns"""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            base = 40 + int(20 * np.sin(x * 0.3) * np.cos(y * 0.2))
            noise = random.randint(-15, 15)
            b = min(255, max(0, base + 120 + noise))
            g = min(255, max(0, base + 40 + noise))
            r = min(255, max(0, base // 4 + noise))
            pixels[x, y] = (r, g, b)
    return img

def generate_lava(size=128):
    """Red/orange lava with hot spots"""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            base = random.randint(100, 200)
            noise = random.randint(-40, 40)
            r = min(255, max(0, base + noise))
            g = min(255, max(0, base // 3 + noise // 2))
            b = min(255, max(0, base // 6 + noise // 3))
            # Hot spots
            if random.random() < 0.05:
                r = min(255, r + 55)
                g = min(255, g + 30)
            pixels[x, y] = (r, g, b)
    return img

def generate_rock(size=128):
    """Grey/brown rocky texture"""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            base = random.randint(60, 120)
            noise = random.randint(-25, 25)
            r = min(255, max(0, base + noise))
            g = min(255, max(0, base - 10 + noise))
            b = min(255, max(0, base - 20 + noise))
            # Crack lines
            if random.random() < 0.03:
                r, g, b = max(0, r - 30), max(0, g - 30), max(0, b - 30)
            pixels[x, y] = (r, g, b)
    return img

def generate_sand(size=128):
    """Yellow/tan sand"""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            base = random.randint(140, 200)
            noise = random.randint(-20, 20)
            r = min(255, max(0, base + noise))
            g = min(255, max(0, base - 20 + noise))
            b = min(255, max(0, base - 80 + noise))
            pixels[x, y] = (r, g, b)
    return img

def generate_snow(size=128):
    """White snow with subtle grey noise"""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            val = random.randint(220, 255)
            noise = random.randint(-15, 5)
            v = min(255, max(200, val + noise))
            pixels[x, y] = (v, v, v + 5)
    return img

def generate_metal(size=128):
    """Grey metal with grid lines"""
    img = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(img)
    # Base grey
    for y in range(size):
        for x in range(size):
            val = random.randint(100, 160)
            img.putpixel((x, y), (val, val, val))
    # Grid lines
    grid_size = size // 8
    for i in range(0, size, grid_size):
        draw.line([(i, 0), (i, size)], fill=(80, 80, 90), width=1)
        draw.line([(0, i), (size, i)], fill=(80, 80, 90), width=1)
    return img

def generate_wood(size=128):
    """Brown wood with grain lines"""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            base = random.randint(80, 140)
            noise = random.randint(-15, 15)
            r = min(255, max(0, base + 20 + noise))
            g = min(255, max(0, base - 10 + noise))
            b = min(255, max(0, base - 40 + noise))
            # Grain lines
            if (y % 8) == 0:
                r = max(0, r - 20)
                g = max(0, g - 20)
            pixels[x, y] = (r, g, b)
    return img

def generate_dirt(size=128):
    """Brown dirt with pebbles"""
    img = Image.new('RGB', (size, size))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            base = random.randint(60, 110)
            noise = random.randint(-20, 20)
            r = min(255, max(0, base + 30 + noise))
            g = min(255, max(0, base + 10 + noise))
            b = min(255, max(0, base - 20 + noise))
            # Pebbles
            if random.random() < 0.08:
                r = min(255, r + 40)
                g = min(255, g + 40)
                b = min(255, b + 30)
            pixels[x, y] = (r, g, b)
    return img

def generate_stone_platform(size=128):
    """Grey stone with brick-like pattern"""
    img = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(img)
    brick_w = size // 4
    brick_h = size // 8
    for y in range(0, size, brick_h):
        offset = (y // brick_h % 2) * (brick_w // 2)
        for x in range(-offset, size, brick_w):
            grey = random.randint(100, 140)
            draw.rectangle([x, y, x + brick_w - 2, y + brick_h - 2], fill=(grey, grey, grey - 5))
    return img

def generate_checkerboard_alt(size=128):
    """Checkerboard for lava areas"""
    img = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(img)
    check_size = size // 8
    for y in range(0, size, check_size):
        for x in range(0, size, check_size):
            if ((x // check_size) + (y // check_size)) % 2 == 0:
                draw.rectangle([x, y, x + check_size, y + check_size], fill=(180, 60, 20))
            else:
                draw.rectangle([x, y, x + check_size, y + check_size], fill=(220, 220, 200))
    return img

def main():
    output_dir = "/root/.openclaw/workspace/bubsy_texture_injector/packs/tiny_texture_pack_2/textures"
    os.makedirs(output_dir, exist_ok=True)
    
    print("🔥 Generating PS1-style procedural textures...")
    
    textures = {
        "grass_01.png": generate_grass(),
        "grass_02.png": generate_grass(),
        "grass_03.png": generate_grass(),
        "grass_04.png": generate_grass(),
        "water_01.png": generate_water(),
        "water_02.png": generate_water(),
        "water_03.png": generate_water(),
        "lava_01.png": generate_lava(),
        "lava_02.png": generate_lava(),
        "lava_03.png": generate_lava(),
        "rock_01.png": generate_rock(),
        "rock_02.png": generate_rock(),
        "rock_03.png": generate_rock(),
        "rock_04.png": generate_rock(),
        "sand_01.png": generate_sand(),
        "sand_02.png": generate_sand(),
        "sand_03.png": generate_sand(),
        "snow_01.png": generate_snow(),
        "snow_02.png": generate_snow(),
        "metal_01.png": generate_metal(),
        "metal_02.png": generate_metal(),
        "metal_03.png": generate_metal(),
        "wood_01.png": generate_wood(),
        "wood_02.png": generate_wood(),
        "dirt_01.png": generate_dirt(),
        "dirt_02.png": generate_dirt(),
        "dirt_03.png": generate_dirt(),
        "checker_alt_01.png": generate_checkerboard_alt(),
    }
    
    for filename, img in textures.items():
        path = os.path.join(output_dir, filename)
        save_ps1_texture(img, path)
    
    print(f"\n✅ Done! Generated {len(textures)} PS1-style textures in {output_dir}/")

if __name__ == "__main__":
    main()
