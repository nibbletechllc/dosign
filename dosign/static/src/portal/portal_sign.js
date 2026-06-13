/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadPDFJSAssets } from "@web/core/utils/pdfjs";
import { SignaturePad } from "@dosign/portal/signature_pad";

export class DosignSignPortal extends Component {
    static template = "dosign.SignPortal";
    static components = { SignaturePad };
    static props = { data: Object, csrf: String };

    setup() {
        this.data = this.props.data;
        this.rootRef = useRef("root");
        this.state = useState({
            pages: [],
            loading: true,
            values: {},
            signature: null,
            initials: null,
            padFor: null,
            submitting: false,
            done: false,
            error: null,
        });
        for (const item of this.data.items) {
            if (!["signature", "initials"].includes(item.type)) {
                this.state.values[item.id] = item.value || "";
            }
        }
        this.pdf = null;

        onWillStart(async () => {
            await loadPDFJSAssets();
            const pdfjsLib = window.pdfjsLib;
            pdfjsLib.GlobalWorkerOptions.workerSrc = "/web/static/lib/pdfjs/build/pdf.worker.js";
            this.pdf = await pdfjsLib.getDocument(this.data.pdf_url).promise;
            this.state.pages = Array.from({ length: this.pdf.numPages }, (_, n) => ({
                number: n + 1, w: 0, h: 0,
            }));
            this.state.loading = false;
        });
        onMounted(() => this.renderPages());
    }

    async renderPages() {
        if (!this.pdf || !this.rootRef.el) {
            return;
        }
        const containerWidth = Math.min(820, this.rootRef.el.clientWidth - 8);
        const dpr = window.devicePixelRatio || 1;
        for (const pg of this.state.pages) {
            const page = await this.pdf.getPage(pg.number);
            const base = page.getViewport({ scale: 1 });
            const cssWidth = containerWidth;
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

    itemsForPage(pageNumber) {
        return this.data.items.filter((i) => i.page === pageNumber);
    }

    chipStyle(item) {
        return `left:${item.pos_x * 100}%;top:${item.pos_y * 100}%;` +
            `width:${item.width * 100}%;height:${item.height * 100}%;`;
    }

    imageFor(item) {
        if (item.type === "signature") {
            return this.state.signature;
        }
        if (item.type === "initials") {
            return this.state.initials;
        }
        return null;
    }

    // --- Signature pad --------------------------------------------------

    openPad(kind) {
        this.state.padFor = kind;
    }

    onPadConfirm(dataUrl) {
        if (this.state.padFor === "initials") {
            this.state.initials = dataUrl;
        } else {
            this.state.signature = dataUrl;
        }
        this.state.padFor = null;
    }

    onPadCancel() {
        this.state.padFor = null;
    }

    // --- Field input ----------------------------------------------------

    setValue(itemId, value) {
        this.state.values[itemId] = value;
    }

    onCheckbox(itemId, ev) {
        this.state.values[itemId] = ev.target.checked ? "1" : "";
    }

    get missingRequired() {
        for (const item of this.data.items) {
            if (!item.required) {
                continue;
            }
            if (item.type === "signature" && !this.state.signature) {
                return true;
            }
            if (item.type === "initials" && !this.state.initials) {
                return true;
            }
            if (!["signature", "initials"].includes(item.type) && !this.state.values[item.id]) {
                return true;
            }
        }
        return false;
    }

    // --- Submit / decline ----------------------------------------------

    async submit() {
        if (this.missingRequired || this.state.submitting) {
            return;
        }
        this.state.submitting = true;
        this.state.error = null;
        try {
            const res = await fetch(this.data.submit_url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    values: this.state.values,
                    signature: this.state.signature,
                    initials: this.state.initials,
                }),
            });
            const json = await res.json();
            if (!res.ok || json.error) {
                throw new Error(json.error || "Submission failed.");
            }
            this.state.done = true;
        } catch (error) {
            this.state.error = error.message;
        } finally {
            this.state.submitting = false;
        }
    }

    async decline() {
        const reason = window.prompt("Reason for declining (optional):", "");
        if (reason === null) {
            return;
        }
        try {
            await fetch(this.data.decline_url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ reason }),
            });
            this.state.done = true;
            this.state.declined = true;
        } catch (error) {
            this.state.error = error.message;
        }
    }
}

registry.category("public_components").add("dosign.sign_portal", DosignSignPortal);
