import mimetypes
import os
import re
import itertools
import hashlib
import json

from twisted.web.static import File
from twisted.web.resource import Resource, NoResource
from twisted.web.server import Site, NOT_DONE_YET
from twisted.internet import reactor

import numpy as np
from PIL import Image

import glob
import os
import subprocess
import tempfile

class Pdf:
    def __init__(self, path):
        self.path = path
        self.meta = self.get_info()
    def get_info(self):
        out = subprocess.check_output(["pdfinfo", self.path])
        return dict([(X.split(':')[0].strip(), ':'.join(X.split(':')[1:]).strip()) for X in out.split('\n') if len(X.strip()) > 2])
    @property
    def npages(self):
        return int(self.meta["Pages"])
    def dump_to_height(self, h=72, start=None, end=None, outdir=None, codec="jpeg"):
        outdir = outdir or tempfile.mkdtemp()
        subprocess.call(['pdftocairo', '-%s' % (codec),
               '-scale-to-y', str(h),
               '-scale-to-x', '-1',
               '-cropbox', '-f', str((start or 0) + 1), '-l', str(end or self.npages), self.path, os.path.join(outdir, 'p')])
        return sorted(glob.glob(os.path.join(outdir, '*')))
    def dump_to_width(self, w=50, start=None, end=None, outdir=None, codec="jpeg"):
        outdir = outdir or tempfile.mkdtemp()
        subprocess.call(['pdftocairo', '-%s' % (codec),
               '-scale-to-y', '-1',
               '-scale-to-x', str(w),
               '-cropbox', '-f', str((start or 0) + 1), '-l', str(end or self.npages), self.path, os.path.join(outdir, 'p')])
        return sorted(glob.glob(os.path.join(outdir, '*')))
    def dump_to_pdf(self, start=None, end=None, outdir=None):
        outdir = outdir or tempfile.mkdtemp()  
        subprocess.call(['pdfseparate', '-f', str((start or 0) + 1), '-l', str((end or start) + 1), self.path, os.path.join(outdir, 'f_%d.pdf')])
        return sorted(glob.glob(os.path.join(outdir, '*')))

class Insist(Resource):
    isLeaf = True
    
    def __init__(self, cacheloc):
        self.cacheloc = cacheloc
        self.cachefile = None
        if os.path.exists(cacheloc):
            self.cachefile = File(cacheloc)
        self.reqs_waiting = []
        self.started = False
        Resource.__init__(self)

    def render_GET(self, req):
        # Check if someone else has created the file somehow
        if self.cachefile is None and os.path.exists(self.cacheloc):
            self.cachefile = File(self.cacheloc)
        # Check if someone else has *deleted* the file
        elif self.cachefile is not None and not os.path.exists(self.cacheloc):
            self.cachefile = None

        if self.cachefile is not None:
            return self.cachefile.render_GET(req)
        else:
            self.reqs_waiting.append(req)
            req.notifyFinish().addErrback(
                self._nevermind, req)
            if not self.started:
                self.started = True
                reactor.callInThread(self.desist)
            return NOT_DONE_YET

    def _nevermind(self, _err, req):
        self.reqs_waiting.remove(req)

    def desist(self):
        self.serialize_computation(self.cacheloc)
        reactor.callFromThread(self.resist)

    def _get_mime(self):
        return mimetypes.guess_type(self.cacheloc)[0]

    def resist(self):
        if not os.path.exists(self.cacheloc):
            # Error!
            print "%s does not exist - rendering fail!" % (self.cacheloc)
            for req in self.reqs_waiting:
                req.headers["Content-Type"] = "text/plain"
                req.write("cyst error")
                req.finish()
            return

        self.cachefile = File(self.cacheloc)

        # Send content to all interested parties
        for req in self.reqs_waiting:
            self.cachefile.render(req)

    def serialize_computation(self, outpath):
        raise NotImplemented

def image2np(path):
    "Load an image file into an array."

    im = Image.open(path)
    im = im.convert('RGB')
    arr = np.asarray(im, dtype=np.uint8)
    return arr

def np2image(np, path):
    "Save an image array to a file."
    if len(np.shape) > 2:
        if np.shape[2] == 3:
            mode = 'RGB'
        elif np.shape[2] == 2:
            mode = 'LA'
    else:
        mode = 'L'
    im = Image.fromstring(
        mode, (np.shape[1], np.shape[0]), np.tostring())
    im.save(path)    


class PdfClip(Insist):
    def __init__(self, pdf, start, end, cachedir, W=500):
        self.W = W
        self.pdf = pdf
        self.start = start
        self.end = end
        Insist.__init__(self, os.path.join(cachedir, "%f-%fx%d.jpg" % (start, end, W)))

    def serialize_computation(self, outpath):
        # Add new to bottom of base
        def concat(base, new):
            return new if base is None else np.concatenate((base,new), axis=0)

        out = None
        for idx, fpath in enumerate(self.pdf.dump_to_width(w=self.W, codec="png", start=int(self.start), end=int(self.end)+1)):
            arr = image2np(fpath)
            top = 0 if out is not None else arr.shape[1] * (self.start - int(self.start))
            bot = arr.shape[1] if not idx == int(self.end) - int(self.start) else arr.shape[1] * (self.end - int(self.end))
            if bot > top and arr.shape[1] > bot:
                arr = arr[:bot]
            if top > 0:
                arr = arr[top:]
            out = concat(out, arr)

        np2image(out, outpath)

class PdfPage(Insist):
    def __init__(self, H, pdf, pageno, cachedir):
        self.H = H
        self.pdf = pdf
        self.pageno = pageno
        Insist.__init__(self, os.path.join(cachedir, "x%d-%d.jpg" % (H, pageno)))

    def serialize_computation(self, outpath):
        fname = self.pdf.dump_to_height(h=self.H, start=self.pageno, end=self.pageno+1)[0]
        os.rename(fname, outpath)

class PdfMosaic(Insist):
    def __init__(self, pdf, cachedir, W=50, H=72, N_COLS=20, start=None, end=None):
        self.W = W
        self.H = H
        self.N_COLS = N_COLS
        self.pdf = pdf
        self.start = start
        self.end = end
        Insist.__init__(self, os.path.join(cachedir, "%dx%dx%d.jpg" % (W,H,N_COLS)))

    def serialize_computation(self, outpath):
        # Blank output image
        out = 255 * np.ones((self.H * int(np.ceil((self.pdf.npages / float(self.N_COLS)))),
                             min(self.N_COLS, self.pdf.npages) * self.W,
                             3), dtype=np.uint8)

        for idx, fpath in enumerate(self.pdf.dump_to_height(h=self.H, codec="png", start=self.start, end=self.end)):
            arr = image2np(fpath)
            if arr.shape[1] > self.W:
                # Crop horizontally
                dw = arr.shape[1] - self.W
                arr = arr[:,(dw/2):(dw/2)+self.W]

            if arr.shape[0] > self.H:
                # Crop y
                arr = arr[:self.H]

            row = idx / self.N_COLS
            col = idx % self.N_COLS

            out[row*self.H:(row+1)*self.H,
                col*self.W:col*self.W + arr.shape[1]] = arr

        np2image(out, outpath)


class PdfDerivatives(File):
    def __init__(self, pdfpath, cacheroot):
        self.pdf = Pdf(pdfpath)
        self.cacheroot = cacheroot
        if not os.path.exists(cacheroot):
            os.makedirs(cacheroot)

        File.__init__(self, pdfpath)
    

    def getChild(self, name, request):
        # Fall back to serve the PDF if no matches are found
        c = self
        # mosaic: wxhxN_COLS, N_COLS optional
        mosaic_m = re.match('(\d+)x(\d+)(x(\d+))?\.jpg', name)
        if mosaic_m:
            w,h,x,cols = mosaic_m.groups()
            n_cols = 20 if not cols else int(cols)
            c = PdfMosaic(self.pdf, self.cacheroot, W=int(w), H=int(h), N_COLS=n_cols)
        # page: xh-p
        page_m = re.match('x(\d+)-(\d+)\.jpg', name)
        if page_m:
            h, p_no = page_m.groups()
            c = PdfPage(int(h), self.pdf, int(p_no), self.cacheroot)
        # clip: top-botxh, h optional
        clip_m = re.match('(\d+(\.\d+)?)-(\d+(\.\d+)?)(x(\d+))?\.jpg', name)
        if clip_m:
            top, x, bot, xx, xxx, h = clip_m.groups()
            c = PdfClip(self.pdf, float(top), float(bot), self.cacheroot)
        
        self.putChild(name, c)
        return c 


class PdfCompilation(Resource):
    def __init__(self, pdfroot, cacheroot):
        self.pdfroot = pdfroot
        self.cacheroot = cacheroot
        self.cachedir = None
        self.pdf = None
        Resource.__init__(self)

        self.clear()

    def clear(self):
        self.contents = []
        self.hash = None

    def bind(self):
        # converts the list of all pages to page ranges
        def ranges(i):
            for a, b in itertools.groupby(enumerate(i), lambda (x, y): y - x):
                b = list(b)
                yield b[0][1], b[-1][1]
        # check cache
        pdfpath = os.path.join(self.cachedir, 'pdf.pdf')
        if not os.path.exists(pdfpath):
            # build a new pdf from contents
            parts = []
            for f, p in self.contents:
                pdf = Pdf(os.path.join(self.pdfroot, f))
                p_ranges = ranges(p)
                for start, end in p_ranges:
                    parts.extend(pdf.dump_to_pdf(start=start, end=end))
            cmd = ['pdfunite', pdfpath]
            cmd[1:1] = parts
            subprocess.call(cmd)
        self.pdf = Pdf(pdfpath)

    def compile(self):
        # hash contents for caching pdf and static files 
        self.hash = hashlib.md5(str(self.contents)).hexdigest()
        self.cachedir = os.path.join(self.cacheroot, self.hash)
        if not os.path.exists(self.cachedir):
            os.makedirs(self.cachedir)

    def add_child(self, name):
        # converts a string of comma separated pages, or ranges of pages, or both to an array of pages
        def pp(s):
            return sum(((list(range(*[int(j) + k for k,j in enumerate(i.split('-'))])) if '-' in i else [int(i)]) for i in s.split(',')), [])
        # is the string a valid filename?
        def ifn(s):
            return True if os.path.exists(os.path.join(self.pdfroot, name)) else False
        # is the string a valid page range
        def ipr(s):
            return True # @todo - confirm valid pages pattern, eg "2,11-16,25,28,30-32"

        # reset if there are compiled contents already
        if self.hash is not None:
            self.clear()
        
        is_finalized = False if (self.contents and self.contents[-1][1] is None) else True

        # Add string to the end of contents (either filename or page range)
        if ifn(name):
            if is_finalized:
                self.contents.append((name,None))
            else:
                self.contents[-1] = (name, None)
        elif not is_finalized and ipr(name):
            self.contents[-1] = (self.contents[-1][0], pp(name))


    def getChild(self, name, request):
        # Try all possible patterns
        # mosaic: wxhxN_COLS, N_COLS optional
        mosaic_m = re.match('(\d+)x(\d+)(x(\d+))?\.jpg', name)
        # page: xh-p
        page_m = re.match('x(\d+)-(\d+)\.jpg', name)
        # clip: top-botxh, h optional
        clip_m = re.match('(\d+(\.\d+)?)-(\d+(\.\d+)?)(x(\d+))?\.jpg', name)
        # deliver pdf: pdf
        send_pdf = True if name=='pdf.pdf' else False
        # Still compiling the contents...
        if not mosaic_m and not page_m and not clip_m and not send_pdf:
            self.add_child(name)
            return self
        # Finalize the new compiled PDF
        else:
            self.compile()
            self.bind()
            if not self.pdf:
                return NoResource()
            if mosaic_m:
                w,h,x,cols = mosaic_m.groups()
                n_cols = 20 if not cols else int(cols)
                c = PdfMosaic(self.pdf, self.cachedir, W=int(w), H=int(h), N_COLS=n_cols)
            elif page_m:
                h, p_no = page_m.groups()
                c = PdfPage(int(h), self.pdf, int(p_no), self.cachedir)
            elif clip_m:
                top, x, bot, xx, xxx, h = clip_m.groups()
                c = PdfClip(self.pdf, float(top), float(bot), self.cachedir)
            elif send_pdf:
                c = File(self.pdf.path)
        
        #self.putChild(name, c)
        return c 

class PdfDirectory(Resource):
    def __init__(self, pdfdir, cachedir):
        self.pdfdir = pdfdir
        self.cachedir = cachedir

        Resource.__init__(self)

        c = PdfCompilation(self.pdfdir, self.cachedir)
        self.putChild('compile', c)

        # Find all children up-front
        # Commented out--we will add children as needed
        # for path in os.listdir(self.pdfdir):
        #     self.add_child(path)

    def add_child(self, path):
        if os.path.isdir(path):
            c = PdfDirectory(os.path.join(self.pdfdir, path), os.path.join(self.cachedir, path))
        elif path.lower().endswith(".pdf"):
            c = PdfDerivatives(os.path.join(self.pdfdir, path), os.path.join(self.cachedir, path))
        else:
            c = File(os.path.join(self.pdfdir, path))

        self.putChild(path, c)
        return c

    def getChild(self, name, request):
        out = Resource.getChild(self, name, request)

        if name and out.code == 404 and os.path.exists(os.path.join(self.pdfdir, name)):
            c = self.add_child(name)
            return c
        else:
            return out

if __name__=='__main__':
    import sys
    PDF_ROOT = sys.argv[1]
    CACHE_DIR= sys.argv[2]

    root = PdfDirectory(PDF_ROOT, CACHE_DIR)
    site = Site(root)
    reactor.listenTCP(8484, site, interface='127.0.0.1')
    reactor.run()
