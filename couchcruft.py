# "convenience"

import couchdb

def _really_put_file_attachment(db, doc, filepath):
    doc = db[doc["_id"]]
    try:
        db.put_attachment(doc, open(filepath))
    except:
        doc = db[doc["_id"]]
        return _really_put_file_attachment(db, doc, filepath)

def _really_set_field(db, doc, key, value):
    "returns (_id, _rev) if field was set through our doing, (_id, None) otherwise"
    doc = db[doc["_id"]]
    while doc.get(key) != value:
        doc[key] = value
        try:
            return db.save(doc)
        except couchdb.ResourceConflict:
            log("_really_set_field", "ResourceConflict", key)
            doc = db[doc["_id"]]
    return (doc["_id"], None)

