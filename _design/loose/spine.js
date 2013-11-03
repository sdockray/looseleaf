var thW=50;
var thH=72;
var boxW=700;
var boxH=350;
var fuW=700;
var fuH=1150;

function idpath(id) {
    return "db/" + id + "/";
}

var LooseLine = function(texts) {
    Line.call(this, thH);

    this.texts = texts;
    this.npages = texts.reduce(function(x,y) {
        return x+y.npages;
    }, 0);

    this._loader = new ImageLoader();
};
LooseLine.prototype = new Line;
LooseLine.prototype.render = function($can, px_start)  {
    var ctx = $can.getContext("2d");
    var start_page = Math.floor(this.px2time(px_start)); // XXX: allow starting out of phase?
    var npages = Math.ceil($can.width / thW);

    for(var p=start_page; p<start_page+npages; p++) {
        var that = this;
        (function(bookpage, dp) {
            if(bookpage) {
                that.loadMosaic(bookpage[0], function($img) {
                        var sx = thW * (bookpage[1] % 20);
                        var sy = thH * Math.floor(bookpage[1] / 20);
                        var dx = thW * (dp - start_page)
                        ctx.drawImage($img,
                                      sx, sy, thW, thH,
                                      dx, 0, thW, thH);
                });
            }
        })(this.getLeafAt(p), p);
    }
};
// `time,' in this case, is pages through all of the documents
LooseLine.prototype.time2px = function(t) {
    return t * thW;
};
LooseLine.prototype.px2time = function(x) {
    return x / thW;
};
LooseLine.prototype.getWidth = function() {
    return this.time2px(this.npages);
};
LooseLine.prototype.getLeafNodes = function() {
    return this.texts;
}
LooseLine.prototype.getLeafAt = function(p) {
    // XXX: B-Tree?
    var cur_p = 0;
    for(var i=0; i<this.texts.length; i++) {
        if(cur_p + this.texts[i].npages > p) {
            return [this.texts[i], p - cur_p];
        }
        cur_p += this.texts[i].npages;
    }
};
// Get start page of book
LooseLine.prototype.bookToPage = function(book) {
    var cur_p = 0;
    for(var i=0; i<this.texts.length; i++) {
        if(book === this.texts[i]) {
            return cur_p;
        }
        cur_p += this.texts[i].npages;
    }
};
LooseLine.prototype.loadMosaic = function(text, cb) {
    this._loader.loadImage(idpath(text._id) + "50x72.jpg", cb);
}

var LooseFlow = function(line, width) {
    Flow.call(this, line, width);
};
LooseFlow.prototype = new Flow;
LooseFlow.prototype.getWidth = function() {
    // round down to even number of pages
    return thW * Math.floor(this._width / thW);
}
// Overwrite to account for y-meaning
LooseFlow.prototype.pt2time = function(pt) {
    var abs_x = Math.floor(pt[1]/thH)*this.getWidth() + thW*Math.floor(pt[0] / thW);
    return this.line.px2time(abs_x) + (pt[1]%thH)/thH;
}
LooseFlow.prototype.book_time2pt = function(t) {
    var x = this.line.time2px(t);
    return [thW * Math.floor((x % this.getWidth()) / thW),
            this.line.getHeight() * Math.floor(x / this.getWidth()) + thH * (t % 1)];
}

var PageRange = function(flow, start_t, duration_t) {
    Marker.call(this, flow, start_t);
    this.$el.style.position = "inherit";
    this.duration_t = duration_t || (boxH / fuH);
    this.position();
}
PageRange.prototype = new Marker;
PageRange.prototype.makeBox = function(start, height) {
    var $box = document.createElement("div");
    $box.className = "selbox";
    var boxpos = this.flow.book_time2pt(start);
    $box.style.left = boxpos[0];
    $box.style.top = boxpos[1];
    $box.style.width = thW;
    $box.style.height = height * thH;
    return $box;
}
PageRange.prototype.position = function() {
    this.$el.innerHTML = "";
    // Make rectangles to cover the range.
    var end = this.t + this.duration_t;
    var cur_book = this.t;
    while(cur_book < end) {
        var box_height = Math.min(1 - (cur_book % 1), end - cur_book);
        this.$el.appendChild(
            this.makeBox(cur_book, box_height));
        cur_book += box_height;
    }
}

var LooseFocus = function(flow) {
    Focus.call(this, flow);
    this.flow = flow;

    // Sloppy inheritence mutation!
    this.$el.removeChild(this.sel.$el);
    this.sel = new PageRange(flow, 0, 0);
    this.sel.$el.className = "boxsel";
    this.$el.appendChild(this.sel.$el);

    // The box will scroll through one line at a time, plus a page on
    // either end that triggers adjustment to the next line.

    this.cur_line = -1;         // Start on a page?

    // XXX: keep in sync with a changing flow...
    this.pagesperline = Math.floor(flow.getWidth() / thW);

    this.box.$el.onscroll = function() {
        var rel_p = this.box.$el.scrollTop / fuH;
        this.setTime(this.cur_line*this.pagesperline + rel_p - 1, true);
    }.bind(this);
}
LooseFocus.prototype = new Focus;
LooseFocus.prototype.setTime = function(p, effect) {
    // `Page' is in absolute coordinates.
    // XXX: Should use "srctime" convention

    var p_idx = Math.floor(p / this.pagesperline);
    var did_set = this.setLine(p_idx);
    
    if(did_set || !effect) {
        // Scroll to appropriate place
        // +1 is because we have some space reserved to get to the previous line.
        var page_offset = p - (p_idx * this.pagesperline) + 1;
        this.box.$el.scrollTop = page_offset * fuH;
    }

    this.drawvisible();

    Focus.prototype.setTime.call(this, p);
}
LooseFocus.prototype.setLine = function(line) {
    if(line == this.cur_line) {
        return;
    }
    this.cur_line = line;

    // RESET
    this.pages = [];            // 0 is previous page
    this.visible = {};          // idx -> bool
    this.box.$el.innerHTML = "";

    for(var i=0; i<(this.pagesperline + 2); i++) {
        var $p = document.createElement("div");
        $p.className = "pageframe";
        this.pages.push($p);
        this.box.$el.appendChild($p);
    }

    return true;
};
LooseFocus.prototype.drawvisible = function() {
    var p = this.box.$el.scrollTop / fuH;
    var p_num = Math.floor(p);
    this.drawpage(p_num);
    this.drawpage(p_num+1);
}
LooseFocus.prototype.drawpage = function(p_num) {
    if(this.visible[p_num] || !this.pages[p_num]) {
        return;
    }
    this.visible[p_num] = true;

    var bookpage = this.flow.line.getLeafAt(this.cur_line*this.pagesperline + p_num - 1);
    var $img = document.createElement("img");
    $img.src = idpath(bookpage[0]._id) + "1024x-"+Math.floor(bookpage[1])+".jpg";
    this.pages[p_num].appendChild($img);
};


// (borrowed & tweaked from unwind)
var Capture = function(onword, onstart, onupdate, onabort) {
    // Create a hidden input that insists on focus
    this.$el = document.createElement("input");
    this.$el.className = "hiddeninput";
    document.body.appendChild(this.$el);

    this._inprogress = false;

    this.$el.focus();
    this.$el.onblur = function(ev) {
        ev.preventDefault();
        window.setTimeout(function() {
            this.$el.focus();
        }.bind(this), 50);
    }.bind(this);
    if (onupdate) {
        this.$el.oninput = function(ev) {
            if(this._inprogress) {
                onupdate(this.$el.value);
            }
        }.bind(this);
    }
    this.$el.onkeydown = function(ev) {
        // console.log(ev.keyCode);
        // if(ev.keyCode == 32 || ev.keyCode == 9 || ev.keyCode == 13) { // space, tab, enter
        if(ev.keyCode == 13) { // enter
            ev.preventDefault()
            onword(this.$el.value);
            this.abort();
        }
        else if(ev.keyCode == 27) { // Escape
            ev.preventDefault();
            this.abort();
            if(onabort) {
                onabort();
            }
        }
        else if(!this._inprogress) {
            this._inprogress = true;
            if(onstart) {
                onstart();
            }
        }
    }.bind(this)
}
Capture.prototype.abort = function() {
    this.$el.value = "";
    this._inprogress = false;
}
