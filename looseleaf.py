from freud.psychotherapist import CouchTherapy, log, init, get_psychotherapist_creds

from couchcruft import _really_put_file_attachment, _really_set_field
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

            _fd, upload_path = tempfile.mkstemp(".pdf")
            open(upload_path, 'w').write(
                db.get_attachment(doc, "upload").read())

            for idx, path in enumerate(do_scan(upload_path)):
                _really_put_file_attachment(db, doc, path)
                _really_set_field(db, doc, "npages", idx+1)
                os.unlink(path)
            os.unlink(upload_path)

            _really_set_field(db, doc, "type", "pdf")

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
        from freud.gui import Office
        
        # standalone
        app = QtGui.QApplication(sys.argv)
        app.setApplicationName(APPNAME)

        print "BASEDIR", basedir

        p = init(basedir, exepath, name=APPNAME, port=PORT)
        creds = get_psychotherapist_creds(os.path.join(os.getenv("HOME"), ".freud", APPNAME, "conf"))
        main = Office(creds, port=PORT)
        main.show()

        app.exec_()

        # Kill couch on-quit
        print "KILL"
        p.kill()
        p.wait()
