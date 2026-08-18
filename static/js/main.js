// Main JavaScript entry point.

function getCookie(name) {
    const cookie = document.cookie
        .split(";")
        .map((value) => value.trim())
        .find((value) => value.startsWith(`${name}=`));

    return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : null;
}

document.body.addEventListener("htmx:configRequest", (event) => {
    const csrfToken = getCookie("csrftoken");
    if (csrfToken) {
        event.detail.headers["X-CSRFToken"] = csrfToken;
    }
});

document.querySelectorAll("[data-print-page]").forEach((button) => {
    button.addEventListener("click", () => window.print());
});

function focusFirstInvalidField(container = document) {
    const field = container.querySelector(
        '[aria-invalid="true"], input:invalid, select:invalid, textarea:invalid',
    );
    if (field) {
        field.focus({ preventScroll: true });
        field.scrollIntoView({ block: "center" });
    }
}

const autoShowModal = document.querySelector("[data-auto-show-modal]");
if (autoShowModal && window.bootstrap) {
    const modal = document.getElementById(autoShowModal.dataset.autoShowModal);
    if (modal) {
        modal.addEventListener(
            "shown.bs.modal",
            () => focusFirstInvalidField(modal),
            { once: true },
        );
        window.bootstrap.Modal.getOrCreateInstance(modal).show();
    }
}

if (document.querySelector("[data-focus-first-error]")) {
    window.requestAnimationFrame(() => focusFirstInvalidField());
}
