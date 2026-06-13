/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";

export class SignaturePad extends Component {
    static template = "dosign.SignaturePad";
    static props = {
        title: { type: String, optional: true },
        onConfirm: Function,
        onCancel: Function,
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.state = useState({ mode: "draw", typed: "", hasDrawn: false });
        this._drawing = false;
        this._onMove = this._onMove.bind(this);
        this._onUp = this._onUp.bind(this);
        onMounted(() => this._setupCanvas());
    }

    _setupCanvas() {
        const canvas = this.canvasRef.el;
        // Match the backing store to the displayed size for crisp lines.
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        const ctx = canvas.getContext("2d");
        ctx.lineWidth = 2.2;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.strokeStyle = "#1a2b4a";
        this._ctx = ctx;
    }

    _pos(ev) {
        const rect = this.canvasRef.el.getBoundingClientRect();
        return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
    }

    onPointerDown(ev) {
        ev.preventDefault();
        this._drawing = true;
        this.state.hasDrawn = true;
        const p = this._pos(ev);
        this._ctx.beginPath();
        this._ctx.moveTo(p.x, p.y);
        document.addEventListener("pointermove", this._onMove);
        document.addEventListener("pointerup", this._onUp);
    }

    _onMove(ev) {
        if (!this._drawing) {
            return;
        }
        const p = this._pos(ev);
        this._ctx.lineTo(p.x, p.y);
        this._ctx.stroke();
    }

    _onUp() {
        this._drawing = false;
        document.removeEventListener("pointermove", this._onMove);
        document.removeEventListener("pointerup", this._onUp);
    }

    clear() {
        const canvas = this.canvasRef.el;
        this._ctx.clearRect(0, 0, canvas.width, canvas.height);
        this.state.hasDrawn = false;
        this.state.typed = "";
    }

    setMode(mode) {
        this.clear();
        this.state.mode = mode;
    }

    onTypeInput(ev) {
        this.state.typed = ev.target.value;
        this._renderTyped();
    }

    _renderTyped() {
        const canvas = this.canvasRef.el;
        const ctx = this._ctx;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#1a2b4a";
        ctx.font = "44px 'Brush Script MT', 'Segoe Script', cursive";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(this.state.typed, canvas.width / 2, canvas.height / 2);
    }

    get isEmpty() {
        return this.state.mode === "draw" ? !this.state.hasDrawn : !this.state.typed.trim();
    }

    confirm() {
        if (this.isEmpty) {
            return;
        }
        if (this.state.mode === "type") {
            this._renderTyped();
        }
        this.props.onConfirm(this._exportTrimmed());
    }

    // Crop the canvas to the drawn content so the signature fills the field
    // instead of floating tiny inside a mostly-empty image.
    _exportTrimmed() {
        const canvas = this.canvasRef.el;
        const { width, height } = canvas;
        const data = canvas.getContext("2d").getImageData(0, 0, width, height).data;
        let minX = width, minY = height, maxX = 0, maxY = 0, found = false;
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                if (data[(y * width + x) * 4 + 3] > 12) {
                    found = true;
                    minX = Math.min(minX, x);
                    maxX = Math.max(maxX, x);
                    minY = Math.min(minY, y);
                    maxY = Math.max(maxY, y);
                }
            }
        }
        if (!found) {
            return canvas.toDataURL("image/png");
        }
        const pad = 8;
        minX = Math.max(0, minX - pad);
        minY = Math.max(0, minY - pad);
        maxX = Math.min(width, maxX + pad);
        maxY = Math.min(height, maxY + pad);
        const w = maxX - minX;
        const h = maxY - minY;
        const out = document.createElement("canvas");
        out.width = w;
        out.height = h;
        out.getContext("2d").drawImage(canvas, minX, minY, w, h, 0, 0, w, h);
        return out.toDataURL("image/png");
    }
}
