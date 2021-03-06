(function($) {

    var SCANR = {n_cols: 20,
                 th_w: 50,
                 th_h: 72,
                 page_w: 700,
                 page_h: 1000,
                 box_h: 300
                }
    $.Figleaf = function($el, basepath) {
        this.basepath = basepath;

        this.$el = $el;
        this.$el.style.position = "relative";
        this.$pdf = $el.querySelector("img");

        // Cover the mosaic with a canvas to visualize position
        this.$canvas = document.createElement("canvas");
        this.$canvas.style.position = "absolute";
        this.$canvas.style.left = 0;
        this.$canvas.style.top = 0;
        this.$canvas.style.zIndex = "5";
        this.$el.appendChild(this.$canvas);

        this.$pdf.onmousedown = this._handle_seek.bind(this);
        this.$canvas.onmousedown = this._handle_seek.bind(this);

        // Create a frame for focus
        this.$focus = document.createElement("div");
        this.$focus.style.position = "absolute";
        this.$focus.style.width = SCANR.page_w;
        this.$focus.style.height = SCANR.box_h;
        this.$focus.style.overflowX = "hidden";
        this.$focus.style.overflowY = "auto";
        this.$focus.style.border = "1px solid red";
        this.$focus.style.backgroundColor = "white";
        this.$focus.style.display = "none";
        this.$focus.style.zIndex = "10";
        this.$focus.onscroll = this._handle_scroll.bind(this);
        this.$el.appendChild(this.$focus);

        this._has_focus = false;

        // Make container <divs> for each page that get lazily filled with images
        this.page_containers = [];
    }
    $.Figleaf.prototype._populate_pages = function() {
        // Use width and height of this.$pdf to set height of focus window
        // (assumes thumbnail image is loaded)

        this.width = this.$pdf.width;
        this.height = this.$pdf.height;

        var npages = (this.height / SCANR.th_h) * SCANR.n_cols; // may overshoot
        for(var i=0; i<npages; i++) {
            var $div = document.createElement("div");
            $div.style.width = SCANR.page_w;
            $div.style.height = SCANR.page_h;
            $div.style.overflow = "hidden";
            this.page_containers[i] = $div;
            this.$focus.appendChild($div);
        }
    }
    $.Figleaf.prototype._handle_seek = function(ev) {
        ev.preventDefault();
        var pdf_pos = _el_offset(this.$pdf);
        var rel_x = ev.clientX - pdf_pos.left;
        var rel_y = ev.clientY - pdf_pos.top;

        var row = Math.floor(rel_y / SCANR.th_h);
        var col = Math.floor(rel_x / SCANR.th_w);

        var page = row * SCANR.n_cols + col;
        // Where in the page are we?
        var th_start = ((rel_y / SCANR.th_h) % 1.0);

        // Allow dragging the mouse here
        window.onmousemove = this._handle_seek.bind(this);
        window.onmouseup = function() {
            console.log("up");
            window.onmousemove = undefined;
            window.onmouseup = undefined;
        }

        console.log("page", page, "start", th_start);
        this.seek(page + th_start);
    }
    $.Figleaf.prototype.pageToPos = function(page) {
        return [SCANR.th_w * (Math.floor(page) % SCANR.n_cols),
                SCANR.th_h * Math.floor(Math.floor(page) / SCANR.n_cols) + SCANR.th_h * (page % 1.0)]
    }
    $.Figleaf.prototype.pageToBoxPos = function(page) {
        // Where should the box go?
        var x_percent = (page % SCANR.n_cols) / SCANR.n_cols;
        
        return [(this.width - SCANR.page_w) * x_percent,
                SCANR.th_h * Math.floor(Math.floor(page) / SCANR.n_cols) + SCANR.th_h]
    }
    $.Figleaf.prototype.seek = function(page) {
        if(!this._has_focus) {
            this.$focus.style.display = "block";
            this._populate_pages();
            this._has_focus = true;
        }

        this.$focus.scrollTop = page * SCANR.page_h;
    }
    $.Figleaf.prototype._handle_scroll = function(ev) {
        var page = this.$focus.scrollTop / SCANR.page_h;

        // Clear & draw position on canvas 
        this.$canvas.setAttribute("width", this.width);
        this.$canvas.setAttribute("height", this.height);
        var ctx= this.$canvas.getContext("2d");
        ctx.strokeStyle = "red";
        ctx.lineWidth = 4;
        ctx.beginPath();

        var page_pos = this.pageToPos(page);
        var box_pos = this.pageToBoxPos(page);
        ctx.moveTo(page_pos[0], page_pos[1]);
        ctx.lineTo(page_pos[0]+SCANR.th_w, page_pos[1]);
        ctx.stroke();

        ctx.strokeStyle = "red";
        ctx.lineWidth = 0.5;
        ctx.globalAlpha = 0.3;
        ctx.lineTo(box_pos[0]+SCANR.page_w, box_pos[1]);
        ctx.lineTo(box_pos[0], box_pos[1]);
        ctx.lineTo(page_pos[0], page_pos[1]);
        ctx.stroke();

        // Move box
        this.$focus.style.left = box_pos[0];
        this.$focus.style.top = box_pos[1];

        // Fill in images
        var page_start = Math.floor(page);
        [page_start, page_start+1].forEach(function(p) {
            var $div = this.page_containers[p];
            if($div.children.length == 0) {
                var $img = document.createElement("img");
                $img.src = this.basepath + "x1024-" + p + ".jpg";
                $img.style.width = "700";
                $div.appendChild($img);
            }
        }.bind(this));
    }

    // util
    var _el_offset = function( el, fixed ) {
        // http://stackoverflow.com/questions/442404/dynamically-retrieve-html-element-x-y-position-with-javascript
        var _x = 0;
        var _y = 0;
        while( el && !isNaN( el.offsetLeft ) && !isNaN( el.offsetTop ) ) {
            _x += el.offsetLeft - el.scrollLeft;
            _y += el.offsetTop - el.scrollTop;
            if(!fixed) {
                el = el.offsetParent;
            }
            else {
                el = null;
            }
        }
        return { top: _y, left: _x };
    }

})(window);
