/** @odoo-module **/

// Per-signer palette (index -> hex). Mirrors the editor chip colors in the
// UI mock. Index comes from dosign.signer.color (0..7).
export const SIGNER_COLORS = [
    "#714B67", // 0 - Odoo purple
    "#1F6FB2", // 1 - blue
    "#28A745", // 2 - green
    "#E8730C", // 3 - orange
    "#C0392B", // 4 - red
    "#8E44AD", // 5 - violet
    "#16A085", // 6 - teal
    "#D4A017", // 7 - gold
];

export function signerColor(colorIndex) {
    const idx = ((colorIndex || 0) % SIGNER_COLORS.length + SIGNER_COLORS.length)
        % SIGNER_COLORS.length;
    return SIGNER_COLORS[idx];
}
