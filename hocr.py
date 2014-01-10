# hocr <-> python
# XXX: Loses paragraph information
import lxml.html

from lxml import etree as ET
from lxml.builder import E

class Word:
    def __init__(self, bb, word):
        self.bb = list(bb)
        self._word = word
    def toString(self):
        return self.word
    def translate(self, x, y):
        self.bb = [self.bb[0]+x,
                   self.bb[1]+y,
                   self.bb[2]+x,
                   self.bb[3]+y]
    def scale(self, val):
        self.bb = [X*val for X in self.bb]
    @property
    def word(self):
        if self._word is None:
            return ""
        return self._word

class Line(list):
    "list of words"
    def toString(self):
        return " ".join([X.toString() for X in self])
    def translate(self, x, y):
        for w in self:
            w.translate(x,y)
    def scale(self, x):
        for w in self:
            w.scale(x)
    @property
    def bb(self):
        return join_bbs([X.bb for X in self])

class Column(list):
    "list of lines"
    def translate(self, x, y):
        for w in self:
            w.translate(x,y)
    def scale(self, x):
        for w in self:
            w.scale(x)
    @property
    def bb(self):
        return join_bbs([X.bb for X in self])

def format_bb(bb):
    return "bbox %s" % (" ".join(["%d" % (X) for X in bb]))

class Page(list):
    "list of columns"
    def addColumn(self, col, x, y):
        col.translate(x,y)
        self.append(col)

    def scale(self, x):
        for w in self:
            w.scale(x)
    @property
    def bb(self):
        return join_bbs([X.bb for X in self])

    def gen_id(self):
        if not hasattr(self, "_count"):
            self._count = 0
        self._count += 1
        return "id_%d" % (self._count)

    def toHocr(self):
        page = E.html(
            E.head(
                E.meta({"http-equiv":"Content-Type",
                        "content":"text/html; charset=utf-8"}),
                E.meta({"name":'ocr-system',
                        "content":'looseleaf 0.0'}),
                E.meta({"name": "ocr-capabilities",
                        "content":'ocr_page ocr_carea ocr_par ocr_line ocrx_word'}),
                ),
            E.body(
                E.div({"class": "ocr_page",
                       "id": "page_1",
                       "title": "%s; pageno 0" % (format_bb(self.bb))},
                      *[
                          E.div({"class": "ocr_carea",
                                 "id": self.gen_id(),
                                 "title": format_bb(COL.bb)},
                                E.p({"class": "ocr_par",
                                     "id": self.gen_id(),
                                       "title": format_bb(COL.bb)},
                                      *[
                                          E.span({"class": "ocr_line",
                                                  "id": self.gen_id(),
                                                 "title": format_bb(LINE.bb)},
                                                *[
                                                    E.span({"class": "ocrx_word",
                                                            "id": self.gen_id(),
                                                           "title": format_bb(WORD.bb)},
                                                          WORD.word)
                                                    for WORD in LINE
                                                ])
                                          for LINE in COL
                                      ]))
                          for COL in self
                      ])))
        # pretty_print=True breaks hocr2pdf's homebrew XML parser.
        return ET.tostring(page, pretty_print=False).replace("<html>",
                                                             """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">""")

def join_bbs(bbs):
    if len(bbs) == 0:
        return []
    elif len(bbs) == 1:
        return bbs[0]
    bb = list(bbs[0])
    for x1,y1,x2,y2 in bbs[1:]:
        bb[0] = min(bb[0], x1)
        bb[1] = min(bb[1], y1)
        bb[2] = max(bb[2], x2)
        bb[3] = max(bb[3], y2)
    return bb

def parse_hocr(hocr_string):
    return Column([Line(
        [Word([int(NUM) for NUM in WORD.get("title").split()[1:]], WORD.text)
         for WORD in LINE.find_class("ocrx_word")])
            for LINE in lxml.html.fromstring(hocr_string).find_class("ocr_line")])
