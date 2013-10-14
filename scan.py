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

def pdf_info(path):
    cmd = ["identify", path]
    # print cmd
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    stdout, stderr = p.communicate()
    out = []
    for line in stdout.split('\n'):
        if " PDF " in line:
            out.append(line.split(" PDF ")[0])
    return out

def scan(path, basedir):
    md5 = get_hash(path)
    outdir = os.path.join(basedir, md5[:2], md5[2:])
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    data = do_scan(path, outdir)

    json.dump(data, open(os.path.join(outdir, "meta.json"), "w"))

    return outdir

def do_scan(path, outdir):
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
        # print cmd
        subprocess.call(cmd)

        # thumbs
        cmd = ["convert",
               "-resize", "x80",
               "-liquid-rescale", "50x72!",
               outfile, os.path.join(outdir, "50x72-r-%d.png" % idx)]
        # print cmd
        subprocess.call(cmd)

        cmd = ["convert", 
               "-resize", "x200",
               "-liquid-rescale", "50x72!",
               outfile, os.path.join(outdir, "50x72-s-%d.png" % idx)]
        # print cmd
        subprocess.call(cmd)


    # generate thumbnails from rendered pages

    t1 = sorted(glob.glob(os.path.join(outdir, "50x72-r-*.png")), key=sort_key)
    mosaic(t1, os.path.join(outdir, "50x72-r.png"))
    for t in t1:
        os.unlink(t)

    t2 = sorted(glob.glob(os.path.join(outdir, "50x72-s-*.png")), key=sort_key)
    mosaic(t2, os.path.join(outdir, "50x72-s.png"))
    for t in t2:
        os.unlink(t)

    data = {"filename": os.path.basename(path),
            "npages": len(info)}

    return data

if __name__=='__main__':
    import sys
    scan(sys.argv[1], sys.argv[2])
