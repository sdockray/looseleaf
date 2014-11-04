import mimetypes
import os

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
    def __init__(self, pdf, cachedir, W=50, H=72, N_COLS=20):
        self.W = W
        self.H = H
        self.N_COLS = N_COLS
        self.pdf = pdf
        Insist.__init__(self, os.path.join(cachedir, "%dx%d.jpg" % (W,H)))

    def serialize_computation(self, outpath):
        # Blank output image
        out = 255 * np.ones((self.H * int(np.ceil((self.pdf.npages / float(self.N_COLS)))),
                             min(self.N_COLS, self.pdf.npages) * self.W,
                             3), dtype=np.uint8)

        for idx, fpath in enumerate(self.pdf.dump_to_height(h=self.H, codec="png")):
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

        # Create lazy resources for derivatives
        mos_page = PdfMosaic(self.pdf, self.cacheroot)
        gpu_mos_page = PdfMosaic(self.pdf, self.cacheroot, W=128, H=128, N_COLS=32)
        self.putChild("50x72.jpg", mos_page)
        self.putChild("128x128.jpg", gpu_mos_page)
        for h in [128, 1024, 2048]:
            for p_no in range(self.pdf.npages):
                pp = PdfPage(h, self.pdf, p_no, self.cacheroot)
                self.putChild("x%d-%d.jpg" % (h, p_no), pp)

class PdfDirectory(Resource):
    def __init__(self, pdfdir, cachedir):
        self.pdfdir = pdfdir
        self.cachedir = cachedir

        Resource.__init__(self)

        # Find all children up-front
        # Commented out--we will add children as needed
        # for path in os.listdir(self.pdfdir):
        #     self.add_child(path)

    def add_child(self, path):
        if os.path.isdir(path):
            c = PdfDirectory(os.path.join(self.pdfdir, path), os.path.join(self.cachedir, path))
        elif path.endswith(".pdf"):
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
