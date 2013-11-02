# Thumbnails & metadata

import glob
import math
import numm
import numpy as np
import os
import subprocess
import tempfile

def mosaic(inpaths, outpath):
    npages = len(inpaths)
    out_width = min(npages, 20) * 50
    out_height = math.ceil(npages / 20.0) * 72
    out = np.zeros((out_height, out_width, 3), dtype=np.uint8)
    payloads = [numm.image2np(X) for X in inpaths]
    for i, p in enumerate(payloads):
        out[(i/20)*72:((i/20)+1)*72, (i%20)*50:((i%20)+1)*50] = p
    numm.np2image(out, outpath)

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
               "-resize", "x80",
               "-liquid-rescale", "50x72!",
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
