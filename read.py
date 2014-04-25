# "ocr"
import dissect
import hocr
from scan import pdf_info

import cv2
import Image
import os
import subprocess
import sys
import tempfile


SCALE = 0.33
QUALITY = 75

def get_hocr(im):
    _fd, path = tempfile.mkstemp(".png")
    #np2image(im, path)
    cv2.imwrite(path, (255-im))

    _f2, hocrconf = tempfile.mkstemp(".tconf")
    open(hocrconf, "w").write("tessedit_create_hocr 1")

    _f3, h_out = tempfile.mkstemp()

    cmd = ['tesseract', path, h_out, "-l", "eng", "+%s" % (hocrconf)]
    print cmd
    subprocess.call(cmd)
    payload = open(h_out + ".html").read()

    os.unlink(hocrconf)
    os.unlink(path)
    os.unlink(h_out)

    return payload

def process_page(im, pdfpath):
    "image 2 ocr'ed pdf page"
    _im, _th, _sm, _pr, boxes = dissect.find_columns(im)
    page = hocr.Page()
    for b in boxes:
        print "BOX", b
        c_im = im[max(0,b[1]):b[3],max(0,b[0]):b[2]]
        c_text = hocr.parse_hocr(get_hocr(c_im))
        if(len(c_text) > 0):
            page.addColumn(c_text, b[0], b[1])
        else:
            print "0"

    page.scale(SCALE)
    h_text = page.toHocr()
    # open("PAGE.HTML", 'w').write(h_text)

    _f2, jpgpath = tempfile.mkstemp(".jpg")

    im = Image.fromstring('L', (im.shape[1], im.shape[0]), im.tostring())
    im = im.resize((int(im.size[0]*SCALE), int(im.size[1]*SCALE)), 1)
    im.save(jpgpath, quality=QUALITY)

    p = subprocess.Popen(["hocr2pdf", 
                          "-r", "150",
                          "-i", jpgpath,
                          "-o", pdfpath],
                         stdin=subprocess.PIPE)
    p.stdin.write(h_text)
    p.stdin.close()
    p.wait()

def preprocess_page(im, white_threshold=None, crop=None):
    if white_threshold is not None:
        im[im > white_threshold] = 255
    if crop is not None:
        w = im.shape[1]
        h = im.shape[0]
        im = im[int(h*crop[1]):int(h*crop[3]),
                int(w*crop[0]):int(w*crop[2])]
    return im

def process_pdf(inpath, outpath, pre_opts={}):
    pages = []
    for idx, page in enumerate(pdf_info(inpath)):
        _fd, p_png = tempfile.mkstemp(".png")
        _fd, p_pdf = tempfile.mkstemp(".pdf")

        cmd = ["convert", 
               "-background", "white",
               "-alpha", "remove",
               "-alpha", "off",
               "-density", "450",
               page, p_png]
        print cmd
        subprocess.call(cmd)

        im = cv2.imread(p_png, 0) # greyscale
        im = preprocess_page(im, **pre_opts)
        process_page(im, p_pdf)
        pages.append(p_pdf)

    subprocess.call(["pdfunite"] + pages + [outpath])

if __name__=='__main__':
    process_pdf(sys.argv[1], sys.argv[2], pre_opts={
        "white_threshold": 150,
        "crop": [0.15, 0.07,
                 0.85, 0.8]})
