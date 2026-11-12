"""
build_frames.py: turn your Procreate PNG layers into the finished frames the web page plays.

What it does, in plain terms:
  1. For every frame, it stacks your layers in this order (bottom to top):
        solid navy  ->  Vampirish_bg.png  ->  "base" layer (if the animation has one)
        ->  the numbered frame  ->  "fg" layer (if the animation has one)
  2. Crops the result to the navy square, shrinks it to 768 x 768 and saves it as a small .webp.
  3. Skips duplicates: if two frames are pixel-for-pixel the same (for example blood's last frame and
     gone's first frame) the picture is stored once and both animations point at it.
  4. Writes p2_anims.js: the list of picture files plus each animation's timing, which the page reads.

How to run it (needs Python and the Pillow library: pip install pillow):
    python3 build_frames.py /path/to/your/vampirish/folder
The folder must contain Vampirish_bg.png and one sub-folder per animation (blood/, gone/, held/, neck/, prick/).
Results go into a frames/ folder and p2_anims.js next to this script.

To change the speed, edit the numbers in the TIMING section near the bottom.
"""
import hashlib, json, os, sys
from PIL import Image

# ---------- Where things are ----------
SRC = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads/vampirish/'
SRC = SRC.rstrip('/') + '/'
OUT = 'frames/'
os.makedirs(OUT, exist_ok=True)

BOX = (82, 82, 942, 942)     # the navy square inside your 1024 x 1024 canvas (left, top, right, bottom)
SZ = 768                     # finished size of each frame in pixels
NAVY = (25, 33, 49, 255)     # solid navy underneath everything, so the ragged edge of the background never shows black

bg = Image.open(SRC + 'Vampirish_bg.png').convert('RGBA')

def load(path):
    return Image.open(SRC + path).convert('RGBA')

def composite(frame, base=None, fg=None):
    """Stack the layers for one frame and return the finished, cropped, shrunken picture."""
    im = Image.alpha_composite(Image.new('RGBA', bg.size, NAVY), bg)   # navy + background
    if base:
        im = Image.alpha_composite(im, load(base))                     # base goes BEHIND the frame
    im = Image.alpha_composite(im, load(frame))                        # the frame itself
    if fg:
        im = Image.alpha_composite(im, load(fg))                       # fg goes IN FRONT of the frame
    return im.crop(BOX).convert('RGB').resize((SZ, SZ), Image.LANCZOS)

# ---------- Keeping track of the pictures we've saved ----------
files = []     # the finished picture files, in order
seen = {}      # fingerprint of a picture -> its number in `files` (this is how duplicates are spotted)

def add(img, name):
    """Save a picture unless an identical one already exists. Returns its number in `files`."""
    fingerprint = hashlib.md5(img.tobytes()).hexdigest()
    if fingerprint in seen:
        return seen[fingerprint]
    filename = f'{name}.webp'
    img.save(OUT + filename, 'WEBP', quality=90, method=6)
    files.append(filename)
    seen[fingerprint] = len(files) - 1
    return seen[fingerprint]

def make_animation(name, frames, durations, base=None, fg=None):
    """Build one animation. Returns a list of [picture number, how many milliseconds to show it]."""
    ids = [add(composite(f, base, fg), f'{name}_{i + 1:02d}') for i, f in enumerate(frames)]
    return [[k, d] for k, d in zip(ids, durations)]

# =====================================================================
# TIMING: change the speed here. All numbers are milliseconds.
#   250 ms per frame = 4 frames per second.
#   The first frame is held a little longer (1000) and the last longer still (1250).
# =====================================================================
FIRST, STEP, LAST = 1000, 250, 1250

anims = {}

# prick: 4 frames on top of a base layer
anims['prick'] = make_animation(
    'prick', [f'prick/prick{i}.png' for i in range(1, 5)],
    [FIRST, STEP, STEP, LAST], base='prick/prick_base.png')

# blood: 11 frames, with the figure (fg) in front of the growing pool.
# Frames 1 and 2 are both empty, so the opening hold is a touch longer.
anims['blood'] = make_animation(
    'blood', [f'blood/blood{i}.png' for i in range(1, 12)],
    [FIRST, STEP] + [STEP] * 8 + [LAST], fg='blood/blood_fg.png')

# gone: 7 frames, the pool fading out, with the figure (fg) in front
anims['gone'] = make_animation(
    'gone', [f'gone/gone{i}.png' for i in range(1, 8)],
    [FIRST] + [STEP] * 5 + [LAST], fg='gone/gone_fg.png')

# neck: 7 full frames, nothing stacked
anims['neck'] = make_animation(
    'neck', [f'neck/neck{i}.png' for i in range(1, 8)],
    [FIRST] + [STEP] * 5 + [LAST])

# held: only 2 drawings, so the "twitch" is a custom pattern of which drawing to show and for how long.
# (0 = held1, 1 = held2): rest, flick, back, flick, rest, flick, back, long rest.
held_pictures = make_animation('held', ['held/held1.png', 'held/held2.png'], [0, 0])
twitch = [(0, 1000), (1, 250), (0, 250), (1, 250), (0, 500), (1, 250), (0, 250), (1, 1000)]
anims['held'] = [[held_pictures[which][0], ms] for which, ms in twitch]

# ---------- Write the file the web page reads ----------
with open('p2_anims.js', 'w') as f:
    f.write(
        '/* Generated by build_frames.py from your Procreate frames. Do not edit by hand.\n'
        '   ANIM_FILES = the picture files.\n'
        '   ANIMS_RAW  = for each animation, a list of [number of a picture in ANIM_FILES, milliseconds to show it]. */\n'
        'const ANIM_FILES = ' + json.dumps(['frames/' + f for f in files]) + ';\n'
        'const ANIMS_RAW = ' + json.dumps(anims) + ';\n')

total = sum(os.path.getsize(OUT + f) for f in files)
print(len(files), 'unique frames,', round(total / 1024), 'KB')
for name, seq in anims.items():
    print(name, sum(ms for _, ms in seq), 'ms', seq)
