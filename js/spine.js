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
};
Line.prototype.render = function(ctx, start_page, npages)  {
    for(var p=start_page; p<start_page+npages; p++) {
        var that = this;
        (function(spec, dp) {
            if(spec) {
                that.loadMosaic(spec.text, spec.page, function($img) {
                    var sx = W * (spec.page % 20);
                    var sy = H * Math.floor(spec.page / 20);
                    var dx = W * (dp - start_page)
                    console.log(spec.text._id, spec.page, sx, sy, dx);
                    ctx.fillStyle = "red";
                    ctx.fillRect(dx, 0, W, H);
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
Line.prototype.loadMosaic = function(text, page, cb) {
    if(text._id in this._mosaics) {
        cb(this._mosaics[text._id]);
    }
    else if(text._id in this._loading) {
        this._loading[text._id][page] = cb;
    }
    else {
        // load!
        console.log("load", text._id);
        this._loading[text._id] = {};
        var $img = document.createElement("img");
        $img.src = idpath(text._id) + "50x72.png";
        // $img.src = idpath(text._id) + "50x72-s.png";
        var that = this;
        $img.onload = function() {
            that._mosaics[text._id] = this;
            cb($img);
            for(var page in that._loading[text._id]) {
                that._loading[text._id][page]($img);
            };
            delete that._loading[text._id];
        };
    }
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

        (function(l_idx) {
            $can.onclick = function(ev) {
                var x_off = ev.clientX - this.offsetLeft;
                that.onclick(
                    that.line.pageToText(
                        l_idx * that.ncols + Math.floor(x_off / W)),
                    [W * Math.floor(x_off / W), l_idx * H]);
            };
        })(i);
    }
};
Flow.prototype.onclick = function(x) {console.log("click", x);};

var Focus = function() {
    this.$el = document.createElement("div");
    this.$el.className = "focus";
    this.$img = document.createElement("img");
    this.$el.appendChild(this.$img);
};
Focus.prototype.set_page = function(p) {
    this.$img.src = idpath(p.text._id) + "1024x-"+p.page+".png";
};
