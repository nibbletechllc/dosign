/** @odoo-module **/

import { Component } from "@odoo/owl";

const MIN_W = 0.03;
const MIN_H = 0.02;

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

export class DosignFieldChip extends Component {
    static template = "dosign.FieldChip";
    static props = {
        item: Object,
        pageW: Number,
        pageH: Number,
        color: String,
        label: String,
        value: { type: [Object, { value: null }], optional: true },
        editable: { type: Boolean, optional: true },
        onUpdate: Function,
        onRemove: Function,
    };

    setup() {
        this._onMove = this._onMove.bind(this);
        this._onUp = this._onUp.bind(this);
        this._mode = null; // "move" | "resize"
    }

    get style() {
        const i = this.props.item;
        const color = this.props.color;
        const filled = !!this.props.value;
        const bg = filled ? "#ffffff" : `${color}22`;
        const cursor = this.props.editable === false ? "default" : "move";
        return `left:${i.pos_x * 100}%;top:${i.pos_y * 100}%;` +
            `width:${i.width * 100}%;height:${i.height * 100}%;` +
            `border-color:${color};background-color:${bg};` +
            `color:${color};cursor:${cursor};`;
    }

    onPointerDown(ev, mode) {
        if (this.props.editable === false) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this._mode = mode;
        this._startX = ev.clientX;
        this._startY = ev.clientY;
        const i = this.props.item;
        this._origin = { x: i.pos_x, y: i.pos_y, w: i.width, h: i.height };
        document.addEventListener("pointermove", this._onMove);
        document.addEventListener("pointerup", this._onUp);
    }

    _onMove(ev) {
        if (!this._mode) {
            return;
        }
        const dx = (ev.clientX - this._startX) / this.props.pageW;
        const dy = (ev.clientY - this._startY) / this.props.pageH;
        const o = this._origin;
        if (this._mode === "move") {
            this.props.onUpdate({
                pos_x: clamp(o.x + dx, 0, 1 - o.w),
                pos_y: clamp(o.y + dy, 0, 1 - o.h),
            });
        } else {
            this.props.onUpdate({
                width: clamp(o.w + dx, MIN_W, 1 - o.x),
                height: clamp(o.h + dy, MIN_H, 1 - o.y),
            });
        }
    }

    _onUp() {
        this._mode = null;
        document.removeEventListener("pointermove", this._onMove);
        document.removeEventListener("pointerup", this._onUp);
    }
}
