# Thumbnails & metadata

import hashlib
import glob
import json
import math
import numm
import numpy as np
import os
import subprocess

def get_hash(path):
    fh = open(path)
    hash = hashlib.md5()
    buf = fh.read(65536)

    while buf:
        hash.update(buf)
        buf = fh.read(65536)

    return hash.hexdigest()

def sort_key(x):
    return int(x.split(".")[-2].split("-")[-1])

def mosaic(inpaths, outpath):
    npages = len(inpaths)
    out_width = min(npages, 20) * 50
    out_height = math.ceil(npages / 20.0) * 72
    out = np.zeros((out_height, out_width, 3), dtype=np.uint8)
    payloads = [numm.image2np(X) for X in inpaths]
    for i, p in enumerate(payloads):
        out[(i/20)*72:((i/20)+1)*72, (i%20)*50:((i%20)+1)*50] = p
    numm.np2image(out, outpath)

def scan(path, basedir):
    md5 = get_hash(path)
    outdir = os.path.join(basedir, md5[:2], md5[2:])
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    # hi-res
    cmd = ["convert", 
           "-background", "white",
           "-alpha", "remove",
           "-alpha", "off",
           "-density", "150",
           "-resize", "1024x",
           path, os.path.join(outdir, "1024x.png")]
    print cmd
    subprocess.call(cmd)

    pages = sorted(glob.glob(os.path.join(outdir, "1024x-*.png")), key=sort_key)

    # thumbnails (1)
    cmd = ["convert",
           "-background", "white",
           "-alpha", "remove",
           "-alpha", "off",
           "-resize", "x80",
           "-liquid-rescale", "50x72!",
           path, os.path.join(outdir, "50x72.png")]
    print cmd
    subprocess.call(cmd)

    t1 = sorted(glob.glob(os.path.join(outdir, "50x72-*.png")), key=sort_key)
    mosaic(t1, os.path.join(outdir, "50x72.png"))
    for t in t1:
        os.unlink(t)

    # thumbnails (2)
    cmd = ["convert", 
           "-background", "white",
           "-alpha", "remove",
           "-alpha", "off",
           "-resize", "x200",
           "-liquid-rescale", "50x72!",
           path, os.path.join(outdir, "50x72-s.png")]
    print cmd
    subprocess.call(cmd)

    t2 = sorted(glob.glob(os.path.join(outdir, "50x72-s-*.png")), key=sort_key)
    mosaic(t2, os.path.join(outdir, "50x72-s.png"))
    for t in t2:
        os.unlink(t)

    json.dump({"filename": os.path.basename(path),
               "npages": len(pages)}, 
              open(os.path.join(outdir, "meta.json"), "w"))

    return outdir

if __name__=='__main__':
    import sys
    scan(sys.argv[1], sys.argv[2])
