/** @odoo-module **/

const replacements = [
    [
        "Odoo's chat helps employees collaborate efficiently. I'm here to help you discover its features.",
        "Dreamwarez chat helps employees collaborate efficiently. I'm here to help you discover its features.",
    ],
    [
        "Dreamwarez's chat helps employees collaborate efficiently. I'm here to help you discover its features.",
        "Dreamwarez chat helps employees collaborate efficiently. I'm here to help you discover its features.",
    ],
];

function debrandText(value) {
    if (!value) {
        return value;
    }
    return replacements.reduce(
        (text, [source, target]) => text.replaceAll(source, target),
        value
    );
}

function debrandTextNode(node) {
    const nextValue = debrandText(node.nodeValue);
    if (nextValue !== node.nodeValue) {
        node.nodeValue = nextValue;
    }
}

function debrandNode(root) {
    if (!root) {
        return;
    }
    if (root.nodeType === Node.TEXT_NODE) {
        debrandTextNode(root);
        return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) {
        return;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
        debrandTextNode(node);
        node = walker.nextNode();
    }
}

function startDebranding() {
    if (!document.body) {
        return;
    }
    debrandNode(document.body);

    new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                debrandNode(node);
            }
            if (mutation.type === "characterData") {
                debrandTextNode(mutation.target);
            }
        }
    }).observe(document.body, {
        childList: true,
        characterData: true,
        subtree: true,
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startDebranding, { once: true });
} else {
    startDebranding();
}
