# Thumbnails & metadata

import glob
import math
from PIL import Image
import numpy as np
import os
import subprocess
import tempfile

def image2np(path):
    "Load an image file into an array."
    im = Image.open(path)
    im = im.convert('RGB')
    arr = np.asarray(im, dtype=np.uint8)
    return arr

def np2image(arr, path):
    "Save an image array to a file."
    assert arr.dtype == np.uint8, "nparr must be uint8"
    if len(arr.shape) > 2 and arr.shape[2] == 3:
        mode = 'RGB'
    else:
        mode = 'L'
    im = Image.fromstring(
        mode, (arr.shape[1], arr.shape[0]), arr.tostring())
    im.save(path, **p)


def mosaic(inpaths, outpath):
    npages = len(inpaths)
    out_width = min(npages, 20) * 50
    out_height = math.ceil(npages / 20.0) * 72
    out = 255*np.ones((out_height, out_width, 3), dtype=np.uint8)
    payloads = [image2np(X) for X in inpaths]
    for i, p in enumerate(payloads):
        out[(i/20)*72:((i/20)+1)*72, (i%20)*50:((i%20)+1)*50] = p
    np2image(out, outpath)

def pdf_info(path):
    cmd = ["identify", path]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    stdout, stderr = p.communicate()
    out = []
    for line in stdout.split('\n'):
        if " PDF " in line:
            out.append(line.split(" PDF ")[0])
    return out

def do_scan(path):
    outdir = tempfile.mkdtemp()

    info = pdf_info(path)

    for idx, page in enumerate(info):
        # hi-res
        outfile = os.path.join(outdir, "1024x-%d.jpg" % idx)
        cmd = ["convert", 
               "-background", "white",
               "-alpha", "remove",
               "-alpha", "off",
               "-density", "150",
               "-resize", "1024x",
               "-quality", "75",
               page, outfile]
        subprocess.call(cmd)

        # thumbs
        cmd = ["convert",
               # "-resize", "x80",
               # "-liquid-rescale", "50x72!",
               "-resize", "50x72!",
               outfile, os.path.join(outdir, "50x72-%06d.png" % idx)]
        # print cmd
        subprocess.call(cmd)

        yield outfile

    # generate thumbnails from rendered pages

    t1 = sorted(glob.glob(os.path.join(outdir, "50x72-*.png")))
    mosaic(t1, os.path.join(outdir, "50x72.jpg"))

    for t in t1:
        os.unlink(t)

    yield os.path.join(outdir, "50x72.jpg")

if __name__=='__main__':
    import shutil, sys
    PATH = sys.argv[1]
    OUTDIR=sys.argv[2]
    for filename in do_scan(PATH):
        shutil.move(filename, OUTDIR)
