var thW=50;
var thH=72;
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
        (function(spec, dp) {
            if(spec) {
                that.loadMosaic(spec.text, function($img) {
                        var sx = thW * (spec.page % 20);
                        var sy = thH * Math.floor(spec.page / 20);
                        var dx = thW * (dp - start_page)
                        ctx.drawImage($img,
                                      sx, sy, thW, thH,
                                      dx, 0, thW, thH);
                });
            }
        })(this.pageToText(p), p);
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
LooseLine.prototype.pageToText = function(p) {
    // XXX: B-Tree?
    var cur_p = 0;
    for(var i=0; i<this.texts.length; i++) {
        if(cur_p + this.texts[i].npages > p) {
            return {
                absolute_page: p,
                text: this.texts[i],
                page: p - cur_p};
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


var LooseFocus = function(flow) {
    Focus.call(this, flow);
    this.flow = flow;

    // The box will scroll through one line at a time, plus a page on
    // either end that triggers adjustment to the next line.

    this.cur_line = -1;         // Start on a page?

    // XXX: keep in sync with a changing flow...
    this.pagesperline = Math.floor(flow.getWidth() / thW);

    this.box.$el.onscroll = function() {
        var rel_p = this.box.$el.scrollTop / fuH;
        this.setTime(this.cur_line*this.pagesperline + rel_p - 1);
    }.bind(this);
}
LooseFocus.prototype = new Focus;
LooseFocus.prototype.setTime = function(p) {
    // `Page' is in absolute coordinates.
    // XXX: Should use "srctime" convention

    var p_idx = Math.floor(p / this.pagesperline);
    this.setLine(p_idx);
    
    // Scroll to appropriate place
    // +1 is because we have some space reserved to get to the previous line.
    var page_offset = p - (p_idx * this.pagesperline) + 1;
    this.box.$el.scrollTop = page_offset * fuH;

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
};
LooseFocus.prototype.drawvisible = function() {
    var p = this.box.$el.scrollTop / fuH;
    var p_num = Math.floor(p);
    this.drawpage(p_num);
    this.drawpage(p_num+1);
}
LooseFocus.prototype.drawpage = function(p_num) {
    if(this.visible[p_num]) {
        return;
    }
    this.visible[p_num] = true;

    var p = this.flow.line.pageToText(this.cur_line*this.pagesperline + p_num - 1);
    var $img = document.createElement("img");
    $img.src = idpath(p.text._id) + "1024x-"+p.page+".jpg";
    this.pages[p_num].appendChild($img);
};
LooseFocus.prototype.onscroll = function(x) {console.log("scroll", x);};
