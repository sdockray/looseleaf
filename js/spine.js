var W=50;
var H=72;
var DATA_DIR = "data/txt/";

function idpath(id) {
    return DATA_DIR + id.slice(0, 2) + "/" + id.slice(2) + "/";
}

var Text = function(id, npages) {
    this._id = id;
    this.npages = npages;
};

var Line = function(texts) {
    this.texts = texts;
    this.npages = texts.reduce(function(x,y) {
        return x+y.npages;
    }, 0);

    this._loading = {};         // text._id -> page -> cb
    this._mosaics = {};         // text._id -> $img

    this._hovers  = {};         // text._id -> $img
    this._hoverback = {};         // text._id -> page -> cb
};
Line.prototype.render = function(ctx, start_page, npages)  {
    for(var p=start_page; p<start_page+npages; p++) {
        var that = this;
        (function(spec, dp) {
            if(spec) {
                var load_fn = that.loadMosaic.bind(that);
                if(p === that.hover) {
                    load_fn = that.loadHoverMosaic.bind(that);
                }
                load_fn(spec.text, spec.page, function($img) {
                        var sx = W * (spec.page % 20);
                        var sy = H * Math.floor(spec.page / 20);
                        var dx = W * (dp - start_page)
                        ctx.drawImage($img,
                                      sx, sy, W, H,
                                      dx, 0, W, H);
                });
            }
        })(this.pageToText(p), p);
    }
};
Line.prototype.pageToText = function(p) {
    // XXX: B-Tree?
    var cur_p = 0;
    for(var i=0; i<this.texts.length; i++) {
        if(cur_p + this.texts[i].npages > p) {
            return {text: this.texts[i],
                    page: p - cur_p};
        }
        cur_p += this.texts[i].npages;
    }
};
Line.prototype._load_img = function(path, cb) {
    var $img = document.createElement("img");
    $img.src = path;
    $img.onload = function() {
        cb($img);
    };
};
Line.prototype._lazy_loader = function(id, page, path, loading, loaded, cb) {
    if(id in loaded) {
        cb(loaded[id]);
    }
    else if(id in loading) {
        loading[id][page] = cb;
    }
    else {
        loading[id] = {};
        loading[id][page] = cb;
        this._load_img(path, function($img) {
            loaded[id] = $img;
            for(var p in loading[id]) {
                loading[id][p]($img);
            }
            delete loading[id];
        });
    }
}
Line.prototype.loadMosaic = function(text, page, cb) {
    this._lazy_loader(text._id, page, idpath(text._id) + "50x72-r.png",
                 this._loading,
                 this._mosaics, cb);
}
Line.prototype.loadHoverMosaic = function(text, _p, cb) {
    this._lazy_loader(text._id, -1, idpath(text._id) + "50x72-s.png",
                 this._hovers,
                 this._hoverback, cb);
}
Line.prototype.setHover = function(page) {
    this.hover = page;
};

var Flow = function(line, width) {
    var that = this;

    this.line = line;
    this.width = width;
    this.ncols = Math.floor(width / W);
    this.nrows = Math.ceil(this.line.npages / this.ncols);

    this.$el = document.createElement("div");
    for(var i=0; i<this.nrows; i++) {
        var $can = document.createElement("canvas");
        $can.setAttribute("width", width);
        $can.setAttribute("height", H);
        var ctx = $can.getContext("2d");
        this.line.render(ctx, i*this.ncols, this.ncols);
        this.$el.appendChild($can);

        (function(l_idx, ctx) {
            $can.onclick = function(ev) {
                var x_off = ev.clientX - this.offsetLeft;
                that.onclick(
                    that.line.pageToText(
                        l_idx * that.ncols + Math.floor(x_off / W)),
                    [W * Math.floor(x_off / W), l_idx * H]);
            };

            $can.onmousemove = function(ev) {
                var x_off = ev.clientX - this.offsetLeft;
                var l_page = l_idx * that.ncols + Math.floor(x_off / W);
                that.line.setHover(l_page);
                that.line.render(ctx, l_idx*that.ncols, that.ncols);
            };

            $can.onmouseout = function(ev) {
                var x_off = ev.clientX - this.offsetLeft;
                var l_page = l_idx * that.ncols + Math.floor(x_off / W);
                that.line.setHover();
                that.line.render(ctx, l_idx*that.ncols, that.ncols);
            };
        })(i, ctx);
    }
};
Flow.prototype.onclick = function(x) {console.log("click", x);};

var Focus = function() {
    this.$el = document.createElement("div");
    this.$el.className = "focus";
    this.$img = document.createElement("img");
    this.$el.appendChild(this.$img);
};
Focus.prototype.setPage = function(p) {
    this.$img.src = idpath(p.text._id) + "1024x-"+p.page+".jpg";
};
