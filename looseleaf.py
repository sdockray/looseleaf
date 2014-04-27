import cyst
import gs

from freud.carousel import Carousel, HobbyHorse, valid_id
from freud.grease import valid_filename, get_ddocname

import os

from twisted.web.resource import Resource
from twisted.internet import reactor
from twisted.web.server import Site

class PdfPage(cyst.Insist):
    def __init__(self, H, pdf, pageno, cachedir):
        self.H = H
        self.pdf = pdf
        self.pageno = pageno
        cyst.Insist.__init__(self, os.path.join(cachedir, "x%d-%d.jpg" % (H, pageno)))

    def serialize_computation(self, outpath):
        fname = self.pdf.dump_to_height(h=self.H, start=self.pageno, end=self.pageno+1)[0]
        os.rename(fname, outpath)

class PdfDerivatives(Resource):
    def __init__(self, pdfpath, cacheroot):
        self.pdf = gs.Pdf(pdfpath)
        self.cacheroot = cacheroot
        if not os.path.exists(cacheroot):
            os.makedirs(cacheroot)

        Resource.__init__(self)

        # Create lazy resources for derivatives
        for sz_name, h in [("small", 128), ("med", 1024), ("large", 2048)]:
            for p_no in range(self.pdf.npages):
                pp = PdfPage(h, self.pdf, p_no, self.cacheroot)
                self.putChild("%s-%d.jpg" % (sz_name, p_no), pp)

class LibraryHorse(HobbyHorse):
    def __init__(self, srcdir, *a, **kw):
        self._derivs = {}       # id -> PdfDerivatives
        self._deriv_resource = Resource()

        HobbyHorse.__init__(self, *a, **kw)

        self.putChild("_pdf_derivs", self._deriv_resource)

        self.link_code(srcdir)

    def link_code(self, srcdir):
        ddocname = get_ddocname(srcdir)
        if ddocname in self.docs:
            ddoc = self.docs[ddocname]
        else:
            ddoc = self.create_doc({"_id": ddocname})

        for fname in os.listdir(srcdir):
            if valid_filename(fname) and fname not in ddoc.doc.get("_attachments", {}):
                ddoc.link_attachment(os.path.join(srcdir, fname))

    def _create_derivative_resource_async(self, docid, pdfname):
        self._derivs[docid] = PdfDerivatives(
            os.path.join(self.dbpath, docid, pdfname),
            os.path.join(self.carousel.CACHEROOT, self.dbname, docid))

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
        HobbyHorse._serve_doc(self, docid)

        doc = self._all_docs[docid]
        if doc.get("type", "pdf"):
            pdfs = [X for X in doc.get("_attachments", {}).keys() if X.endswith(".pdf")]
            if len(pdfs) > 0:
                pdfname = pdfs[0]

                if docid not in self._derivs:
                    reactor.callInThread(
                        self._create_derivative_resource_async,
                        docid, pdfname)

class LooseCarousel(Carousel):
    def __init__(self, dbdir, srcdir):
        self.CACHEROOT = os.path.join(dbdir, "_cache")
        self.SRCDIR = srcdir
        Carousel.__init__(self, dbdir)

    def _serve_db(self, dbname):
        # TODO: Better Carousel hooks for overridden subclasses
        self.dbs[dbname] = LibraryHorse(self.SRCDIR, self, os.path.join(self.datadir, dbname))
        self.putChild(dbname, self.dbs[dbname])

    @classmethod
    def fromdirectory(cls, indir, dbdir, srcdir, copy=False):
        care = cls(dbdir, srcdir)
        dbname = os.path.basename(os.path.normpath(indir))
        db = care.create_db(dbname)
        for fname in [X for X in os.listdir(indir) if X.endswith(".pdf") and valid_id(X)]:
            print "adding pdf", fname
            fullpath = os.path.join(indir, fname)
            if not os.path.isdir(fullpath) and fname not in db.docs:
                doc = {"_id": fname,
                       "type": "pdf"}
                doc = db.create_doc(doc)
                if copy:
                    doc.put_attachment(open(fullpath))#, filename=fname)
                else:
                    doc.link_attachment(fullpath)
        return care

if __name__=='__main__':
    import sys

    WEB_SRC = "_design/loose"

    dbdir  = sys.argv[1]

    if len(sys.argv) == 3:
        pdfdir = sys.argv[2]
        care = LooseCarousel.fromdirectory(pdfdir, dbdir, WEB_SRC)
    else:
        care = LooseCarousel(dbdir, WEB_SRC)

    subdbs = care.dbs.values()
    if len(subdbs) == 0:
        defaultdb = care.create_db("looseleaf")
    else:
        defaultdb = subdbs[0]
    root = defaultdb.docs[WEB_SRC].rewrite_resource

    site = Site(root)
    PORT = 5989
    reactor.listenTCP(PORT, site, interface="0.0.0.0")
    print "http://localhost:%d" % (PORT)
    # import webbrowser
    # webbrowser.open_new_tab("http://localhost:%d" % (PORT))
    reactor.run()
