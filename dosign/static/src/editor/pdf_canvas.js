/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted } from "@odoo/owl";
import { loadPDFJSAssets } from "@web/core/utils/pdfjs";
import { signerColor } from "@dosign/editor/colors";
import { DosignFieldChip } from "@dosign/editor/field_chip";

export class DosignPdfCanvas extends Component {
    static template = "dosign.PdfCanvas";
    static components = { DosignFieldChip };
    static props = {
        pdfUrl: String,
        items: Array,
        fieldTypes: Array,
        signers: Array,
        activeSignerId: { type: [Number, { value: null }], optional: true },
        editable: { type: Boolean, optional: true },
        participantField: { type: String, optional: true },
        onAddItem: Function,
        onUpdateItem: Function,
        onRemoveItem: Function,
    };

    setup() {
        this.rootRef = useRef("root");
        this.state = useState({ pages: [], zoom: 1, loading: true });
        this.pdf = null;

        onWillStart(async () => {
            await loadPDFJSAssets();
            const pdfjsLib = window.pdfjsLib;
            pdfjsLib.GlobalWorkerOptions.workerSrc = "/web/static/lib/pdfjs/build/pdf.worker.js";
            this.pdf = await pdfjsLib.getDocument(this.props.pdfUrl).promise;
            this.state.pages = Array.from({ length: this.pdf.numPages }, (_, n) => ({
                number: n + 1,
                w: 0,
                h: 0,
            }));
            this.state.loading = false;
        });

        onMounted(() => this.renderAll());
    }

    async renderAll() {
        if (!this.pdf || !this.rootRef.el) {
            return;
        }
        const containerWidth = Math.max(320, this.rootRef.el.clientWidth - 32);
        const dpr = window.devicePixelRatio || 1;
        for (const pg of this.state.pages) {
            const page = await this.pdf.getPage(pg.number);
            const base = page.getViewport({ scale: 1 });
            const cssWidth = containerWidth * this.state.zoom;
            const cssHeight = (cssWidth * base.height) / base.width;
            const canvas = this.rootRef.el.querySelector(`canvas[data-page="${pg.number}"]`);
            if (!canvas) {
                continue;
            }
            const viewport = page.getViewport({ scale: (cssWidth / base.width) * dpr });
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            canvas.style.width = `${cssWidth}px`;
            canvas.style.height = `${cssHeight}px`;
            await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
            pg.w = cssWidth;
            pg.h = cssHeight;
        }
    }

    setZoom(delta) {
        this.state.zoom = Math.max(0.5, Math.min(2.5, this.state.zoom + delta));
        this.renderAll();
    }

    resetZoom() {
        this.state.zoom = 1;
        this.renderAll();
    }

    itemsForPage(pageNumber) {
        return this.props.items.filter((it) => it.page === pageNumber);
    }

    fieldTypeOf(item) {
        const ftId = Array.isArray(item.field_type_id) ? item.field_type_id[0] : item.field_type_id;
        return this.props.fieldTypes.find((ft) => ft.id === ftId);
    }

    labelOf(item) {
        const ft = this.fieldTypeOf(item);
        return ft ? ft.name : "Field";
    }

    signerOf(item) {
        const signerId = Array.isArray(item.signer_id) ? item.signer_id[0] : item.signer_id;
        return this.props.signers.find((s) => s.id === signerId);
    }

    // Captured value to render, or null to fall back to the placeholder label.
    valueOf(item) {
        const ft = this.fieldTypeOf(item);
        const type = ft ? ft.item_type : null;
        const signer = this.signerOf(item);
        if (type === "signature" && signer && signer.signature_image) {
            return { image: signer.signature_image };
        }
        if (type === "initials" && signer && signer.initials_image) {
            return { image: signer.initials_image };
        }
        if (item.value_text) {
            return { text: item.value_text };
        }
        return null;
    }

    colorOf(item) {
        const ref = item[this.props.participantField || "signer_id"];
        const id = Array.isArray(ref) ? ref[0] : ref;
        const signer = this.props.signers.find((s) => s.id === id);
        return signer ? signerColor(signer.color) : "#888888";
    }

    onDragOver(ev) {
        if (this.props.editable === false) {
            return;
        }
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "copy";
    }

    onDrop(ev, pageNumber) {
        if (this.props.editable === false) {
            return;
        }
        ev.preventDefault();
        const ftId = parseInt(ev.dataTransfer.getData("application/dosign-field"), 10);
        if (!ftId) {
            return;
        }
        const rect = ev.currentTarget.getBoundingClientRect();
        const x = (ev.clientX - rect.left) / rect.width;
        const y = (ev.clientY - rect.top) / rect.height;
        this.props.onAddItem(ftId, pageNumber, x, y);
    }
}
