import os
import re
import shutil
import subprocess
import tempfile
import itertools
import mimetypes
import hashlib
import json
import glob
from ConfigParser import SafeConfigParser

import cherrypy
from cherrypy.lib.static import serve_file

import numpy as np
from PIL import Image


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


class Pdf:
	""" Does the work of actually interfacing with PDF files """
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
		subprocess.call(['pdfseparate', '-f', str((start or 0) + 1), '-l', str((end or start) + 1), self.path, os.path.join(outdir, 'f_%04d.pdf')])
		return sorted(glob.glob(os.path.join(outdir, '*')))


class Cacheable(object):
	""" Allows the various image classes to be cacheable """
	def __init__(self, outpath):
		self.outpath = outpath
	def get(self):
		if os.path.exists(self.outpath):
			return self.outpath
		else:	
			self.serialize_computation(self.outpath)
			if os.path.exists(self.outpath):
				return self.outpath
		return None


class PdfClip(Cacheable):
	""" A clipping from within a PDF """
	def __init__(self, pdf, cachedir, start, end, W=500):
		self.W = W
		self.pdf = pdf
		self.start = start
		self.end = end
		Cacheable.__init__(self, os.path.join(cachedir, "%f-%fx%d.jpg" % (start, end, W)))

	def serialize_computation(self, outpath):
		# Add new to bottom of base
		def concat(base, new):
			return new if base is None else np.concatenate((base,new), axis=0)

		out = None
		for idx, fpath in enumerate(self.pdf.dump_to_width(w=self.W, codec="png", start=int(self.start), end=int(self.end)+1)):
			arr = image2np(fpath)
			top = 0 if out is not None else arr.shape[0] * (self.start - int(self.start))
			bot = arr.shape[0] if not idx == int(self.end) - int(self.start) else arr.shape[0] * (self.end - int(self.end))
			if bot > top and arr.shape[0] > bot:
				arr = arr[:bot]
			if top > 0:
				arr = arr[top:]
			out = concat(out, arr)
		np2image(out, outpath)


class PdfPage(Cacheable):
	""" A page from a PDF rendered as an image """
	def __init__(self, pdf, cachedir, H, pageno):
		self.H = H
		self.pdf = pdf
		self.pageno = pageno
		Cacheable.__init__(self, os.path.join(cachedir, "x%d-%d.jpg" % (H, pageno)))

	def serialize_computation(self, outpath):
		fname = self.pdf.dump_to_height(h=self.H, start=self.pageno, end=self.pageno+1)[0]
		shutil.copy(fname, outpath)


class PdfMosaic(Cacheable):
	""" Mosaic images """
	def __init__(self, pdf, cachedir, W=50, H=72, N_COLS=20, start=None, end=None):
		self.W = W
		self.H = H
		self.N_COLS = N_COLS
		self.pdf = pdf
		self.start = start
		self.end = end
		Cacheable.__init__(self, os.path.join(cachedir, "%dx%dx%d.jpg" % (W,H,N_COLS)))

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
			out[row*self.H:row*self.H + arr.shape[0],
				col*self.W:col*self.W + arr.shape[1]] = arr
		# output
		np2image(out, outpath)


class PdfDerivative(object):
	""" Various images that can be derived from a pdf """
	def __init__(self, pdf_dir, name, pdfroot, cacheroot, cachedir=None):
		self.pdf = Pdf(os.path.join(pdfroot, pdf_dir))
		print "===",self.pdf.path
		# setting cachedir overrides how the cache location is normally derived
		if cachedir:
			self.cachedir = cachedir
		else:
			self.cachedir = os.path.join(cacheroot, pdf_dir)
		if not os.path.exists(self.cachedir):
			os.makedirs(self.cachedir)
		self.name = name

	def get_image(self):
		mosaic_m = re.match('(\d+)x(\d+)(x(\d+))?\.jpg', self.name)
		# mosaic: wxhxN_COLS, N_COLS optional
		if mosaic_m:
			w,h,x,cols = mosaic_m.groups()
			n_cols = 20 if not cols else int(cols)
			return PdfMosaic(self.pdf, self.cachedir, W=int(w), H=int(h), N_COLS=n_cols).get()
		# page: xh-p
		page_m = re.match('x(\d+)-(\d+)\.jpg', self.name)
		if page_m:
			h, p_no = page_m.groups()
			return PdfPage(self.pdf, self.cachedir, int(h), int(p_no)).get()
		# clip: top-botxh, h optional
		clip_m = re.match('(\d+(\.\d+)?)-(\d+(\.\d+)?)(x(\d+))?\.jpg', self.name)
		if clip_m:
			top, x, bot, xx, xxx, w = clip_m.groups()
			w = 800 if not w else int(w)
			return PdfClip(self.pdf, self.cachedir, float(top), float(bot), W=int(w)).get()
		return "image"


class PdfCompilation(object):
	""" Compiles a PDF from assorted different PDFs """
	def __init__(self, pdfroot, cacheroot):
		self.pdfroot = pdfroot
		self.cacheroot = cacheroot
		self.cachedir = None
		self.pdf = None
		self.contents = []
		self.filename = None
		
	def set_contents(self, args):
		""" args will come from a url of alternating filename and pages for the different sections """
		# converts a string of comma separated pages, or ranges of pages, or both to an array of pages
		def pp(s):
			return sum(((list(range(*[int(j) + k for k,j in enumerate(i.split('-'))])) if '-' in i else [int(i)]) for i in s.split(',')), [])
		# is the string a valid filename?
		def ifn(s):
			return True if os.path.exists(os.path.join(self.pdfroot, s)) else False
		# Build contents from arguments
		def pairwise(iterable):
			a = iter(iterable)
			return itertools.izip(a, a)
		# loop through arguments
		for x, y in pairwise(args):
			if ifn(x):
				self.contents.append((x,pp(y)))

	def bind(self):
		""" Binds the pdf sections defined in self.contents into a new pdf """
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
		""" hash contents for caching pdf and static files """
		self.hash = hashlib.md5(str(self.contents)).hexdigest()
		self.cachedir = os.path.join(self.cacheroot, self.hash)
		if not os.path.exists(self.cachedir):
			os.makedirs(self.cachedir)

	def file(self, name):
		""" returns a file derived from the compiled pdf (or the compiled pdf itself) """
		self.compile()
		self.bind()
		if name=='pdf.pdf':
			return self.pdf.path
		else:
			return PdfDerivative(self.pdf.path, name, self.cacheroot, self.cacheroot, cachedir=self.cachedir).get_image()


class PdfServer(object):
	""" CherryPy handlers """
	@cherrypy.expose
	def default(self, pdf, *args, **kwargs):
		if not pdf:
			return "No such file."
		if len(args)>=1:
			return serve_file(PdfDerivative(pdf, args[0], PDF_ROOT, CACHE_DIR).get_image())
			
		return "Something went wrong."

	@cherrypy.expose
	def compile(self, *args, **kwargs):
		c = PdfCompilation(PDF_ROOT, CACHE_DIR)
		c.set_contents(args[:-1])
		return serve_file(c.file(args[-1]))


# UWSGI application
def application(environ, start_response):
	cherrypy.config.update({
		'server.socket_port': SERVER_PORT,
	})
	cherrypy.tree.mount(PdfServer(), '/')
	return cherrypy.tree(environ, start_response)


# Load config
config = SafeConfigParser({
	'pdfroot':'/Users/dddd/Documents/dev/grrrr/uploads/processed',
	'cachedir':'/Users/dddd/Documents/dev/grrrr/uploads/clips-cache',
	'port': 8484,
	'mode':'testing',
})
try:
	config.read('config.ini')
	PDF_ROOT = config.get('config', 'pdfroot')
	CACHE_DIR = config.get('config', 'cachedir')
	SERVER_PORT = int(config.get('config', 'port'))
	SERVER_MODE = config.get('config', 'mode')		
except:
	print "Create a config.ini file to set directories & port"


# Starting things up
if __name__ == '__main__':
	conf = {}
	cherrypy.config.update({
		'server.socket_port': 8484,
	})
	app = cherrypy.tree.mount(PdfServer(), '/')
	cherrypy.quickstart(app,config=conf)