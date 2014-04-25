# Thumbnails & metadata

import os
import re
import subprocess
import tempfile

class Pdf:
    def __init__(self, path):
        self.path = path
        self.meta = self.get_info()

    def get_info(self):
        cmd = ["gs",
               "-dNODISPLAY",
               "-q",
               "-sFile=%s" % (self.path),
               "pdf_info.ps"]
        stdout = subprocess.check_output(cmd)
        m = re.search(r"\.pdf has (\d+) page", stdout)

        npages = int(m.groups()[0])

        pnums = re.finditer(r"Page \d+ MediaBox: \[\d+\.?\d* \d+\.?\d* (\d+\.?\d*) (\d+\.?\d*)\]", stdout)
        sizelist = [tuple([float(X) for X in page.groups()]) for page in pnums]

        # Figure out which page sizes are exceptional
        size_counts = {}
        for sz in sizelist:
            size_counts[sz] = size_counts.get(sz, 0) + 1
        size = sorted(size_counts.items(), key=lambda x: x[1], reverse=True)[0][0]
        other_sizes = {}
        for idx,sz in enumerate(sizelist):
            if sz != size:
                other_sizes[idx] = sz

        return {"npages": npages, "size": size, "other_sizes": other_sizes}

    @property
    def npages(self):
        return self.meta["npages"]

    def pagesize(self, idx=0):
        return self.meta["other_sizes"].get(idx, self.meta["size"])

    def _heightranges(self, start=None, end=None):
        # End is exclusive.
        # Yield (h, start, end) tuples
        start = start or 0
        end = end
        if end is None:
            end = self.npages
        end = min(self.npages, end)

        if end-start <= 0:
            return

        cur_idx = start
        cur_start = start
        last_h = None
        while cur_idx <= end:
            cur_h = self.pagesize(cur_idx)[1]
            if last_h is None:
                last_h = cur_h
            if cur_h != last_h or cur_idx == end:
                yield (last_h, cur_start, cur_idx)
                cur_start = cur_idx
            last_h = cur_h
            cur_idx += 1

    def dump_to_height(self, h=72, start=None, end=None):
        ims = []
        # Serialize
        for (p_h, start, end) in self._heightranges(start=start, end=end):
            density = 72 * h / float(p_h)
            ims.extend(self.dump_range(r=density, start=start, end=end))
        return ims

    def dump_range(self, r=72, start=None, end=None, outdir=None, codec="jpeg"):
        # End is exclusive
        outdir = outdir or tempfile.mkdtemp()

        printrange = []
        npages = self.npages
        if start is not None:
            printrange.append("-dFirstPage=%d" % (start+1))
            npages -= start
        if end is not None:
            printrange.append("-dLastPage=%d" % (end))
            npages -= (self.npages-end)

        subprocess.call(["gs", "-q",
                         "-dBATCH", "-dSAFER", "-dNOPAUSE", "-dNOPROMPT",
                         "-dMaxBitmap=500000000",
                         "-dAlignToPixels=0", "-dGridFitTT=2",
                         "-sDEVICE=%s" % (codec), "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
                         "-r%f" % (r)] + printrange + [
                             "-sOutputFile=%s" % (os.path.join(outdir, "%%d.%s" % (codec))), 
                             self.path])
        return [os.path.join(outdir, "%d.%s" % (X, codec)) for X in range(1, npages+1)]
