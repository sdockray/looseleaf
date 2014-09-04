import cyst
import gs

from numm3 import image2np, np2image
import seatbelt.seatbelt as seatbelt # ...internals

import os
import numpy as np

from twisted.web.resource import Resource
from twisted.internet import reactor

class PdfPage(cyst.Insist):
    def __init__(self, H, pdf, pageno, cachedir):
        self.H = H
        self.pdf = pdf
        self.pageno = pageno
        cyst.Insist.__init__(self, os.path.join(cachedir, "x%d-%d.jpg" % (H, pageno)))

    def serialize_computation(self, outpath):
        fname = self.pdf.dump_to_height(h=self.H, start=self.pageno, end=self.pageno+1)[0]
        os.rename(fname, outpath)

class PdfMosaic(cyst.Insist):
    def __init__(self, pdf, cachedir, W=50, H=72, N_COLS=20):
        self.W = W
        self.H = H
        self.N_COLS = N_COLS
        self.pdf = pdf
        cyst.Insist.__init__(self, os.path.join(cachedir, "50x72.jpg"))

    def serialize_computation(self, outpath):
        # Blank output image
        out = 255 * np.ones((self.H * int(np.ceil((self.pdf.npages / float(self.N_COLS)))),
                             min(self.N_COLS, self.pdf.npages) * self.W,
                             3), dtype=np.uint8)

        for idx, fpath in enumerate(self.pdf.dump_to_height(h=self.H)):
            arr = image2np(fpath)
            if arr.shape[1] > self.W:
                # Crop horizontally
                dw = arr.shape[1] - self.W
                arr = arr[:,(dw/2):(dw/2)+self.W]

            row = idx / self.N_COLS
            col = idx % self.N_COLS

            out[row*self.H:(row+1)*self.H,
                col*self.W:col*self.W + arr.shape[1]] = arr

        np2image(out, outpath)

class PdfDerivatives(Resource):
    def __init__(self, pdfpath, cacheroot):
        self.pdf = gs.Pdf(pdfpath)
        self.cacheroot = cacheroot
        if not os.path.exists(cacheroot):
            os.makedirs(cacheroot)

        Resource.__init__(self)

        # Create lazy resources for derivatives
        mos_page = PdfMosaic(self.pdf, self.cacheroot)
        self.putChild("50x72.jpg", mos_page)
        for sz_name, h in [("small", 128), ("med", 1024), ("large", 2048)]:
            for p_no in range(self.pdf.npages):
                pp = PdfPage(h, self.pdf, p_no, self.cacheroot)
                self.putChild("%s-%d.jpg" % (sz_name, p_no), pp)

class LibraryDatabase(seatbelt.Database):
    def __init__(self, *a, **kw):
        self._derivs = {}       # id -> PdfDerivatives
        self._deriv_resource = Resource()

        seatbelt.Database.__init__(self, *a, **kw)

        self.putChild("_pdf_derivs", self._deriv_resource)

    def _create_derivative_resource_async(self, docid, pdfname):
        self._derivs[docid] = PdfDerivatives(
            os.path.join(self.dbpath, docid, pdfname),
            os.path.join(CACHEROOT, self.dbname, docid))

        reactor.callFromThread(
            self._with_derivative_resource_sync, docid)

    def _with_derivative_resource_sync(self, docid):
        self._deriv_resource.putChild(docid, self._derivs[docid])

        # Add PDF metadata to document
        change = False
        doc = self._all_docs[docid]
        for k,v in self._derivs[docid].pdf.meta.items():
            if doc.get(k) != v:
                doc[k] = v
                change = True
        if change:
            # Push a notification out
            self._change(doc)

    def _serve_doc(self, docid):
        seatbelt.Database._serve_doc(self, docid)

        doc = self._all_docs[docid]
        if doc.get("type", "pdf"):
            pdfs = [X for X in doc.get("_attachments", {}).keys() if X.endswith(".pdf")]
            if len(pdfs) > 0:
                pdfname = pdfs[0]

                if docid not in self._derivs:
                    reactor.callInThread(
                        self._create_derivative_resource_async,
                        docid, pdfname)

seatbelt.PARTS_BIN["Database"] = LibraryDatabase

if __name__=='__main__':
    import sys

    CACHEROOT = "/tmp/looseleaf"

    PORT = 6989
    WEB_SRC = "www/loose"
    dbdir  = sys.argv[1]

    seatbelt.serve(dbdir, port=PORT, defaultdb="looseleaf", defaultddocs=WEB_SRC)
