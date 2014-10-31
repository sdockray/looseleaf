# use cropbox
# scale, &c

#pdftocairo -png -scale-to-y 72 -scale-to-x -1 -cropbox -f 0 -l 5 PATH ROOT
import os
import subprocess
import tempfile

def _c(x):
    #normalize codec
    if x == 'jpeg':
        return 'jpg'
    return x

class Pdf:
    def __init__(self, path):
        self.path = path
        self.meta = self.get_info()
    def get_info(self):
        CMD = ["pdfinfo", self.path]
        #print "CMD", CMD
        out = subprocess.check_output(CMD)
        return dict([(X.split(':')[0].strip(), ':'.join(X.split(':')[1:]).strip()) for X in out.split('\n') if len(X.strip()) > 2])
    @property
    def npages(self):
        return int(self.meta["Pages"])
    def dump_to_height(self, h=72, start=None, end=None, outdir=None, codec="jpeg"):
        outdir = outdir or tempfile.mkdtemp()
        CMD = ['pdftocairo', '-%s' % (codec),
               '-scale-to-y', str(h),
               '-scale-to-x', '-1',
               '-cropbox', '-f', str(start or 1), '-l', str(end or self.npages), self.path, os.path.join(outdir, 'p')]
        #print "CMD", CMD
        subprocess.call(CMD)
        return [os.path.join(outdir, "p-%03d.%s" % (idx, _c(codec))) for idx in range(start or 1, (end or self.npages) + 1)]
