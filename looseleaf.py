from psychotherapist import CouchTherapy, log, init, get_psychotherapist_creds

from scan import do_scan

import os
import sys
import tempfile

APPNAME = "looseleaf"
PORT = 5989

# Grr... boilerplate
# Hard to abstract because of the __file__ crap
# Maybe an `exec` is in order?
if getattr(sys, 'frozen', False):
    # we are running in a |PyInstaller| bundle
    basedir = sys._MEIPASS
    exepath = '"%s"' % (sys.executable)
    execmd = [sys.executable]
else:
    # we are running in a normal Python environment
    basedir = os.path.abspath(os.path.dirname(__file__))
    exepath = '"%s" "%s"' % (sys.executable, os.path.abspath(__file__))
    execmd = [sys.executable, os.path.abspath(__file__)]


class Looseleaf(CouchTherapy):
    def doc_updated_type_uploaded_pdf(self, db, doc):
        log("doc updated")
        if "upload" in doc.get("_attachments", {}):

            # prevent update-loops
            doc["type"] = "processing-pdf"
            db.save(doc)

            subdir = tempfile.mkdtemp()
            inpath = os.path.join(subdir, "upload")
            open(inpath, 'w').write(
                db.get_attachment(doc, "upload").read())

            res = do_scan(inpath, subdir)

            for name in os.listdir(subdir):
                if name != "upload":
                    db.put_attachment(doc, open(os.path.join(subdir, name)))
                os.unlink(os.path.join(subdir, name))
            os.rmdir(subdir)

            # Don't clobber attachments!
            doc = db[doc["_id"]]

            doc["npages"] = res["npages"]
            doc["type"] = "pdf"
            db.save(doc)

if __name__=='__main__':
    if len(sys.argv) == 2 and sys.argv[1] == "sit-down":
        log("looseleaf is running inside of couch")
        ll = Looseleaf()

        try:
            ll.run_forever()
        except Exception, err:
            import traceback
            for line in traceback.format_exc().split('\n'):
                log(line)
            import time
            time.sleep(20)
            sys.exit(1)
    elif len(sys.argv) == 1:
        from PyQt4 import QtGui
        from gui import get_main_window
        
        # standalone
        app = QtGui.QApplication(sys.argv)
        app.setApplicationName(APPNAME)

        print "BASEDIR", basedir

        p = init(basedir, exepath, name=APPNAME, port=PORT)
        creds = get_psychotherapist_creds(os.path.join(os.getenv("HOME"), ".freud", APPNAME, "conf"))

        main = get_main_window(creds, port=PORT)

        app.exec_()

        # Kill couch on-quit
        print "KILL"
        p.kill()
        p.wait()
